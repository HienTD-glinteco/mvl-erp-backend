"""
DRF ViewSet mixin for XLSX export functionality.
"""

from django.conf import settings
from django.http import HttpResponse
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from .constants import ERROR_MISSING_MODEL, ERROR_MISSING_QUERYSET
from .generator import XLSXGenerator
from .schema_builder import SchemaBuilder
from .serializers import ExportAsyncResponseSerializer
from .tasks import generate_xlsx_from_queryset_task, generate_xlsx_task


class ExportXLSXMixin:
    """
    Mixin for DRF ViewSets to add XLSX export functionality.

    Adds a /download/ action that exports the current queryset to XLSX format.

    Usage:
        class MyViewSet(ExportXLSXMixin, ModelViewSet):
            queryset = MyModel.objects.all()
            serializer_class = MySerializer

            # Optional: customize export
            def get_export_data(self, request):
                return {
                    "sheets": [{
                        "name": "Custom Sheet",
                        "headers": ["Field 1", "Field 2"],
                        "data": [...]
                    }]
                }
    """

    @extend_schema(
        summary="Export to XLSX",
        description="Export filtered queryset data to XLSX format. "
        "Returns file directly for synchronous export or task information for async export.",
        parameters=[
            OpenApiParameter(
                name="async",
                description="If 'true', process export in background using Celery (requires EXPORTER_CELERY_ENABLED=true)",
                required=False,
                type=bool,
            ),
        ],
        responses={
            200: OpenApiResponse(
                description="XLSX file content (synchronous export)",
                response=bytes,
            ),
            202: ExportAsyncResponseSerializer,
            400: OpenApiResponse(description="Bad request (e.g., async mode not enabled)"),
        },
        tags=["Export"],
    )
    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request, *args, **kwargs):
        """
        Export action to download data as XLSX.

        Query parameters:
            async: If 'true', process in background (requires Celery)

        Returns:
            - Synchronous (200): XLSX file download
            - Asynchronous (202): Task ID and status information
        """
        # Check if async mode is enabled
        use_async = request.query_params.get("async", "false").lower() == "true"
        celery_enabled = getattr(settings, "EXPORTER_CELERY_ENABLED", False)

        if use_async and not celery_enabled:
            return Response(
                {"error": _("Async export is not enabled")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if use_async:
            # For async export, defer schema building to the task
            # This avoids blocking the HTTP response while fetching/processing data
            return self._async_export(request)
        else:
            # For synchronous export, build schema immediately
            schema = self.get_export_data(request)
            return self._sync_export(schema)

    def _async_export(self, request):
        """
        Handle async export by deferring data fetching to Celery task.

        Args:
            request: HTTP request object

        Returns:
            Response: 202 response with task information
        """
        storage_backend = getattr(settings, "EXPORTER_STORAGE_BACKEND", "local")

        # Check if using default schema generation (from model)
        # If using custom get_export_data, we need to build schema upfront
        if self._uses_default_export():
            # Extract serializable parameters to rebuild queryset in task
            task_params = self._get_export_task_params(request)

            # Trigger background task with queryset parameters
            task = generate_xlsx_from_queryset_task.delay(
                app_label=task_params["app_label"],
                model_name=task_params["model_name"],
                queryset_filters=task_params.get("queryset_filters"),
                filename=task_params.get("filename"),
                storage_backend=storage_backend,
            )
        else:
            # Custom export - build schema upfront
            schema = self.get_export_data(request)
            filename = self._get_export_filename()
            task = generate_xlsx_task.delay(schema, filename, storage_backend)

        return Response(
            {
                "task_id": task.id,
                "status": "PENDING",
                "message": _("Export started. Check status at /api/export/status/?task_id={task_id}").format(
                    task_id=task.id
                ),
            },
            status=status.HTTP_202_ACCEPTED,
        )

    def _sync_export(self, schema):
        """
        Handle synchronous export.

        Args:
            schema: Export schema

        Returns:
            HttpResponse: XLSX file response
        """
        filename = self._get_export_filename()

        # Generate file synchronously
        generator = XLSXGenerator()
        file_content = generator.generate(schema)

        # Return as HTTP response
        response = HttpResponse(
            file_content.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    def _uses_default_export(self):
        """
        Check if ViewSet uses default export (auto-generation from model).

        Returns:
            bool: True if using default export, False if custom get_export_data is overridden
        """
        # Check if get_export_data is overridden in the ViewSet class
        # If it's the same as the mixin's method, it's using default
        return self.__class__.get_export_data == ExportXLSXMixin.get_export_data

    def _get_export_task_params(self, request):
        """
        Extract serializable parameters for async export task.

        Args:
            request: HTTP request object

        Returns:
            dict: Parameters for Celery task
        """
        # Get model info
        if not hasattr(self, "queryset") or self.queryset is None:
            raise ValueError(ERROR_MISSING_QUERYSET)

        model_class = self.queryset.model
        if not model_class:
            raise ValueError(ERROR_MISSING_MODEL)

        # Get filtered queryset to extract filter parameters
        queryset = self.filter_queryset(self.get_queryset())

        # Extract filter kwargs from queryset query
        # Note: This extracts filters but complex querysets may not serialize perfectly
        queryset_filters = {}
        if hasattr(queryset.query, "where") and queryset.query.where:
            # For simple filters, extract them
            # Complex queries will need custom handling
            try:
                # Try to get filter kwargs from queryset
                # This works for simple .filter() calls
                for child in queryset.query.where.children:
                    if hasattr(child, "lhs") and hasattr(child, "rhs"):
                        field_name = child.lhs.field.name
                        value = child.rhs
                        queryset_filters[field_name] = value
            except (AttributeError, TypeError):
                # If extraction fails, use empty filters (export all)
                pass

        return {
            "app_label": model_class._meta.app_label,
            "model_name": model_class._meta.object_name,
            "queryset_filters": queryset_filters if queryset_filters else None,
            "filename": self._get_export_filename(),
        }

    def get_export_data(self, request):
        """
        Get export data/schema.

        Override this method to customize export structure and data.

        Args:
            request: HTTP request object

        Returns:
            dict: Export schema with structure:
                {
                    "sheets": [{
                        "name": str,
                        "headers": [str, ...],
                        "data": [dict, ...]
                    }]
                }
        """
        # Auto-generate schema from model
        return self._generate_default_schema(request)

    def _generate_default_schema(self, request):
        """
        Generate default export schema from model fields.

        Args:
            request: HTTP request object

        Returns:
            dict: Auto-generated export schema
        """
        # Get model from queryset
        if not hasattr(self, "queryset") or self.queryset is None:
            raise ValueError(ERROR_MISSING_QUERYSET)

        model_class = self.queryset.model
        if not model_class:
            raise ValueError(ERROR_MISSING_MODEL)

        # Get filtered queryset
        queryset = self.filter_queryset(self.get_queryset())

        # Build schema from model
        builder = SchemaBuilder()
        schema = builder.build_from_model(model_class, queryset)

        return schema

    def _get_export_filename(self):
        """
        Generate filename for export.

        Returns:
            str: Filename for exported file
        """
        if hasattr(self, "queryset") and self.queryset is not None:
            model_name = self.queryset.model._meta.verbose_name_plural
            return f"{model_name}_export.xlsx"
        return "export.xlsx"
