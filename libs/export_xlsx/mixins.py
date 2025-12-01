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

from .constants import (
    DELIVERY_DIRECT,
    DELIVERY_LINK,
    ERROR_MISSING_MODEL,
    ERROR_MISSING_QUERYSET,
    STORAGE_S3,
)
from .generator import XLSXGenerator
from .schema_builder import SchemaBuilder
from .serializers import ExportAsyncResponseSerializer, ExportS3DeliveryResponseSerializer
from .storage import get_storage_backend
from .tasks import generate_xlsx_from_queryset_task, generate_xlsx_from_viewset_task


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
        "By default, returns a presigned S3 URL. Use delivery=direct for direct file download. "
        "For async export, use async=true (requires EXPORTER_CELERY_ENABLED=true).",
        parameters=[
            OpenApiParameter(
                name="async",
                description="If 'true', process export in background using Celery (requires EXPORTER_CELERY_ENABLED=true)",
                required=False,
                type=bool,
            ),
            OpenApiParameter(
                name="delivery",
                description="Delivery mode for synchronous export. "
                "'link' (default) returns a presigned S3 link; "
                "'direct' returns the file as an HTTP attachment.",
                required=False,
                type=str,
                enum=["link", "direct"],
            ),
        ],
        responses={
            200: ExportS3DeliveryResponseSerializer,
            202: ExportAsyncResponseSerializer,
            206: OpenApiResponse(description="returns the file as an HTTP attachment."),
            400: OpenApiResponse(description="Bad request (invalid parameters or S3 not configured)"),
            500: OpenApiResponse(description="Internal server error (generation or upload failure)"),
        },
        tags=["0.2: Export"],
    )
    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request, *args, **kwargs):
        """
        Export action to download data as XLSX.

        Query parameters:
            async: If 'true', process in background (requires Celery)
            delivery: Delivery mode ('link' for presigned URL, 'direct' for file download)

        Returns:
            - Synchronous link (200): JSON with presigned URL and metadata
            - Synchronous direct (200): XLSX file download
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

        # Get delivery mode (only relevant for synchronous exports)
        delivery = request.query_params.get("delivery", getattr(settings, "EXPORTER_DEFAULT_DELIVERY", "link")).lower()

        # Validate delivery parameter
        if delivery not in (DELIVERY_LINK, DELIVERY_DIRECT):
            return Response(
                {"error": _("Invalid delivery parameter; allowed: link, direct")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if use_async:
            # For async export, defer schema building to the task
            # Pass delivery parameter to determine storage backend
            return self._async_export(request, delivery)
        else:
            # For synchronous export, build schema immediately
            schema = self.get_export_data(request)
            return self._sync_export(schema, delivery)

    def _async_export(self, request, delivery=None):
        """
        Handle async export by deferring data fetching to Celery task.

        Args:
            request: HTTP request object
            delivery: Delivery mode ('s3' or 'direct') to determine storage backend

        Returns:
            Response: 202 response with task information
        """
        # Determine storage backend based on delivery parameter
        storage_backend = self._get_storage_backend_from_delivery(delivery)

        # Check if using default schema generation (from model)
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
            # Custom export - use ViewSet-based task to defer get_export_data to worker
            viewset_class_path = f"{self.__class__.__module__}.{self.__class__.__name__}"
            request_data = {
                "query_params": dict(request.query_params),
                "user_id": request.user.id if hasattr(request, "user") and request.user.is_authenticated else None,
            }
            filename = self._get_export_filename()

            task = generate_xlsx_from_viewset_task.delay(
                viewset_class_path=viewset_class_path,
                request_data=request_data,
                filename=filename,
                storage_backend=storage_backend,
            )

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

    def _sync_export(self, schema, delivery=DELIVERY_LINK):
        """
        Handle synchronous export.

        Args:
            schema: Export schema
            delivery: Delivery mode ('link' or 'direct')

        Returns:
            Response: JSON response with S3 link or HttpResponse with file
        """
        filename = self._get_export_filename()

        # Generate file synchronously
        generator = XLSXGenerator()
        file_content = generator.generate(schema)

        # Handle delivery mode
        if delivery == DELIVERY_DIRECT:
            # Direct download - return file as HTTP response
            return self._direct_file_response(file_content, filename)
        else:
            # Link delivery - upload and return presigned URL
            return self._s3_delivery_response(file_content, filename)

    def _direct_file_response(self, file_content, filename):
        """
        Create HTTP response for direct file download.

        Args:
            file_content: File content (BytesIO)
            filename: Filename for download

        Returns:
            HttpResponse: File download response
        """
        response = HttpResponse(
            file_content.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            status=status.HTTP_206_PARTIAL_CONTENT,
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    def _s3_delivery_response(self, file_content, filename):
        """
        Upload to S3 and return presigned URL response.

        Args:
            file_content: File content (BytesIO)
            filename: Filename for upload

        Returns:
            Response: JSON response with presigned URL and metadata
        """
        try:
            # Get S3 storage backend
            storage = get_storage_backend(STORAGE_S3)

            # Save file to S3
            file_path = storage.save(file_content, filename)

            # Generate presigned URL
            presigned_url = storage.get_url(file_path)

            # Get file size
            file_size = storage.get_file_size(file_path)

            # Get expiration time from settings
            expires_in = getattr(
                settings,
                "EXPORTER_PRESIGNED_URL_EXPIRES",
                getattr(settings, "EXPORTER_S3_SIGNED_URL_EXPIRE", 3600),
            )

            # Return JSON response
            response_data = {
                "url": presigned_url,
                "filename": filename,
                "expires_in": expires_in,
                "storage_backend": "s3",
            }

            if file_size is not None:
                response_data["size_bytes"] = file_size

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            # Handle S3 upload errors
            return Response(
                {"error": _("Failed to upload file to S3: {error}").format(error=str(e))},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _get_storage_backend_from_delivery(self, delivery):
        """
        Determine storage backend from delivery mode.

        Args:
            delivery: Delivery mode ('link' or 'direct')

        Returns:
            str: Storage backend type ('s3' or 'local')
        """
        # Map delivery mode to storage backend
        # Only use configured EXPORTER_STORAGE_BACKEND if no delivery parameter provided
        # Otherwise, delivery parameter takes precedence
        if delivery is not None:
            if delivery == DELIVERY_LINK:
                return STORAGE_S3
            elif delivery == DELIVERY_DIRECT:
                return "local"

        # Fallback to configured storage backend
        configured_backend = getattr(settings, "EXPORTER_STORAGE_BACKEND", None)
        if configured_backend:
            return configured_backend

        # Default to s3
        return STORAGE_S3

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
