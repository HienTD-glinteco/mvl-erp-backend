"""DRF ViewSet mixin for async import functionality."""

from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.files.models import FileModel
from apps.imports.constants import (
    API_MESSAGE_CANNOT_CANCEL,
    API_MESSAGE_CANCELLED_SUCCESS,
    API_MESSAGE_IMPORT_STARTED,
    ERROR_MISSING_HANDLER,
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
)


class AsyncImportProgressMixin:
    """
    Mixin for DRF ViewSets to add async import functionality with progress tracking.

    This mixin adds an /import/ action that:
    - Accepts a confirmed FileModel ID
    - Creates an ImportJob record
    - Enqueues a Celery task to process the import
    - Returns job information for status tracking

    Usage:
        class MyViewSet(AsyncImportProgressMixin, ModelViewSet):
            # Define the import handler
            import_row_handler = "apps.myapp.handlers.my_import_handler"

            # Or override get_import_handler_path()
            def get_import_handler_path(self):
                return "apps.myapp.handlers.my_import_handler"
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
        if not handler_path:
            return Response(
                {"error": _(ERROR_MISSING_HANDLER)},
                status=status.HTTP_400_BAD_REQUEST,
            )

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

    def get_import_handler_path(self) -> str:
        """
        Get the import handler path.

        Override this method to provide dynamic handler path.

        Returns:
            str: Dotted path to import handler function
        """
        return self.import_row_handler


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
