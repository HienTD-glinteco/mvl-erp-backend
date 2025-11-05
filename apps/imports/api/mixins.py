"""DRF ViewSet mixin for async import functionality."""

from typing import Optional

from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.files.models import FileModel
from apps.imports.constants import (
    API_MESSAGE_CANCELLED_SUCCESS,
    API_MESSAGE_CANNOT_CANCEL,
    ERROR_MISSING_HANDLER,
    ERROR_NO_TEMPLATE,
    FILE_PURPOSE_IMPORT_TEMPLATE,
    STATUS_CANCELLED,
    STATUS_QUEUED,
    STATUS_RUNNING,
)
from apps.imports.models import ImportJob
from apps.imports.tasks import import_job_task

from .serializers import (
    ImportCancelResponseSerializer,
    ImportStartResponseSerializer,
    ImportStartSerializer,
    ImportTemplateResponseSerializer,
)


class AsyncImportProgressMixin:
    """
    Mixin for DRF ViewSets to add async import functionality with progress tracking.

    This mixin adds an /import/ action that:
    - Accepts a confirmed FileModel ID
    - Creates an ImportJob record
    - Enqueues a Celery task to process the import
    - Returns job information for status tracking

    Usage Option 1 - Using a separate handler module (recommended for reusable handlers):
        class MyViewSet(AsyncImportProgressMixin, ModelViewSet):
            # Define the import handler path
            import_row_handler = "apps.myapp.handlers.my_import_handler"

    Usage Option 2 - Define handler method directly in ViewSet (for simple/specific cases):
        class MyViewSet(AsyncImportProgressMixin, ModelViewSet):
            # Define handler method in the ViewSet
            def _process_import_data_row(self, row_index, row, import_job_id, options):
                '''Process a single row from import file.'''
                # Your import logic here
                return {"ok": True, "result": {"id": created_id}}
                # or {"ok": False, "error": "error message"}

    Note: If you define _process_import_data_row method, it takes precedence over
    the import_row_handler attribute.
    """

    # Class attribute to define the import handler path
    import_row_handler = None

    @extend_schema(
        summary="Start import job",
        description=(
            "Start an asynchronous import job from a confirmed file. "
            "Returns job information for tracking via /import/status/ endpoint."
        ),
        request=ImportStartSerializer,
        responses={
            202: ImportStartResponseSerializer,
            400: OpenApiResponse(description="Bad request (file not found, not confirmed, or missing handler)"),
        },
        tags=["Import"],
    )
    @action(detail=False, methods=["post"], url_path="import")
    def start_import(self, request, *args, **kwargs):
        """
        Start an import job.

        POST /import/
        {
            "file_id": 123,
            "options": {
                "batch_size": 500,
                "count_total_first": true,
                "header_rows": 1,
                "output_format": "csv",
                "create_result_file_records": true,
                "handler_path": "apps.myapp.handlers.my_handler"  # Optional override
            },
            "async": true
        }
        """
        serializer = ImportStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        file_id = serializer.validated_data["file_id"]
        options = serializer.validated_data.get("options", {})

        # Get handler path
        handler_path = options.get("handler_path") or self.get_import_handler_path()

        # Check if using ViewSet method handler
        if handler_path is None and hasattr(self, "_process_import_data_row"):
            # Store ViewSet class path and method name for worker to reconstruct
            viewset_class_path = f"{self.__class__.__module__}.{self.__class__.__name__}"
            options["handler_path"] = None
            options["viewset_class_path"] = viewset_class_path
            options["use_viewset_method"] = True
        elif not handler_path:
            return Response(
                {"error": _(ERROR_MISSING_HANDLER)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        else:
            # Store handler_path in options
            options["handler_path"] = handler_path

        # Get file object
        try:
            file_obj = FileModel.objects.get(id=file_id)
        except FileModel.DoesNotExist:
            return Response(
                {"error": _("File not found")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create ImportJob
        import_job = ImportJob.objects.create(
            file=file_obj,
            created_by=request.user if request.user.is_authenticated else None,
            status=STATUS_QUEUED,
            options=options,
        )

        # Enqueue Celery task
        task = import_job_task.delay(str(import_job.id))
        import_job.celery_task_id = task.id
        import_job.save(update_fields=["celery_task_id"])

        # Return response
        response_data = {
            "import_job_id": str(import_job.id),
            "celery_task_id": task.id,
            "status": import_job.status,
            "created_at": import_job.created_at.isoformat(),
        }

        return Response(response_data, status=status.HTTP_202_ACCEPTED)

    def get_import_handler_path(self) -> Optional[str]:
        """
        Get the import handler path.

        Override this method to provide dynamic handler path.

        If the ViewSet defines a _process_import_data_row method, it will be used
        automatically. Otherwise, falls back to the import_row_handler attribute.

        Returns:
            str: Dotted path to import handler function, or None if using method handler
        """
        # Check if ViewSet has _process_import_data_row method defined
        if hasattr(self, "_process_import_data_row") and callable(self._process_import_data_row):
            # Return None to signal that we'll use the method directly
            # The actual method will be stored differently
            return None

        return self.import_row_handler

    def get_import_template_name(self) -> Optional[str]:
        """
        Get the template name for template lookup.

        Override this method to provide a custom template name for template files.

        Lookup priority:
        1. Check if ViewSet has `import_template_name` attribute
        2. Fall back to default format: {app}_{resource} (e.g., "hrm_employees")

        By default, constructs name from model's app_label and model name.

        Returns:
            str: Template name for lookup (e.g., "hrm_employees", "crm_customers")
        """
        # Check for explicit import_template_name attribute
        if hasattr(self, "import_template_name") and self.import_template_name:
            return self.import_template_name

        # Generate default: app_resource format
        if hasattr(self, "queryset") and self.queryset is not None:
            app_label = self.queryset.model._meta.app_label
            model_name = self.queryset.model._meta.model_name
            return f"{app_label}_{model_name}"

        return None

    @extend_schema(
        summary="Download import template",
        description=(
            "Download the import template file for this resource. "
            "The template provides the correct format and headers for importing data."
        ),
        responses={
            200: ImportTemplateResponseSerializer,
            404: OpenApiResponse(description="No template available for this resource"),
        },
        tags=["Import"],
    )
    @action(detail=False, methods=["get"], url_path="import_template")
    def import_template(self, request, *args, **kwargs):
        """
        Get the import template file for this resource.

        GET /import_template/
        """
        # Get template name for lookup
        template_name = self.get_import_template_name()
        if not template_name:
            return Response(
                {"error": _(ERROR_NO_TEMPLATE)},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Look up the most recent template file matching the template name
        try:
            template_file = (
                FileModel.objects.filter(
                    purpose=FILE_PURPOSE_IMPORT_TEMPLATE,
                    file_name__istartswith=template_name,
                    is_confirmed=True,
                )
                .order_by("-created_at")
                .first()
            )

            if not template_file:
                return Response(
                    {"error": _(ERROR_NO_TEMPLATE)},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Return template file information with download URL
            response_data = {
                "file_id": template_file.id,
                "file_name": template_file.file_name,
                "download_url": template_file.download_url,
                "size": template_file.size,
                "created_at": template_file.created_at.isoformat(),
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class AsyncImportCancelMixin:
    """
    Mixin to add import job cancellation functionality.

    Usage:
        class MyViewSet(AsyncImportCancelMixin, ModelViewSet):
            pass
    """

    @extend_schema(
        summary="Cancel import job",
        description="Cancel a running or queued import job.",
        responses={
            200: ImportCancelResponseSerializer,
            400: OpenApiResponse(description="Cannot cancel job in current status"),
            404: OpenApiResponse(description="Import job not found"),
        },
        tags=["Import"],
    )
    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel_import(self, request, pk=None, *args, **kwargs):
        """
        Cancel an import job.

        POST /imports/{job_id}/cancel/
        """
        try:
            import_job = ImportJob.objects.get(id=pk)
        except ImportJob.DoesNotExist:
            return Response(
                {"error": _("Import job not found")},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check if job can be cancelled
        if import_job.status not in [STATUS_QUEUED, STATUS_RUNNING]:
            return Response(
                {"error": _(API_MESSAGE_CANNOT_CANCEL.format(status=import_job.status))},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Revoke Celery task if exists
        if import_job.celery_task_id:
            from celery_tasks import celery_app

            celery_app.control.revoke(import_job.celery_task_id, terminate=True)

        # Update job status
        import_job.status = STATUS_CANCELLED
        import_job.save(update_fields=["status"])

        return Response(
            {
                "message": _(API_MESSAGE_CANCELLED_SUCCESS),
                "status": import_job.status,
            },
            status=status.HTTP_200_OK,
        )
