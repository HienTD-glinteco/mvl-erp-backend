"""API views for import status checking."""

from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.api.permissions import RoleBasedPermission
from apps.core.utils.permissions import register_permission
from apps.imports.constants import ERROR_TASK_ID_REQUIRED
from apps.imports.models import ImportJob
from apps.imports.progress import get_import_progress

from .serializers import ImportJobSerializer


class ImportStatusView(APIView):
    """
    API view to check the status of an async import task with progress information.

    This is the unified status endpoint for all import jobs, similar to /export/status/.
    """

    permission_classes = [RoleBasedPermission]
    serializer_class = ImportJobSerializer

    @extend_schema(
        summary="Check import task status",
        description=(
            "Check the status of an asynchronous import task using the import_job_id. "
            "Returns progress information including percentage, processed/total rows, "
            "success/failure counts, and result file URLs."
        ),
        parameters=[
            OpenApiParameter(
                name="task_id",
                description="Import job ID (UUID) returned from POST /import/",
                required=True,
                type=str,
            ),
        ],
        responses={
            200: ImportJobSerializer,
            400: OpenApiResponse(description="Bad request (missing task_id parameter)"),
            404: OpenApiResponse(description="Import job not found"),
        },
        tags=["0.3: Import"],
    )
    @register_permission(
        "import.check_status",
        description=_("Check import status"),
        module=_("Imports"),
        submodule=_("Status"),
        name=_("Import Check Status"),
    )
    def get(self, request):
        """
        Check import task status with progress information.

        Query parameters:
            task_id: Import job ID (UUID)

        Returns:
            dict: Task status with keys:
                - id: Import job ID
                - file_id: Source file ID
                - status: Job status
                - celery_task_id: Celery task ID
                - created_by_id: User ID who created the job
                - created_at: Creation timestamp
                - started_at: Start timestamp
                - finished_at: Completion timestamp
                - total_rows: Total rows to process
                - processed_rows: Rows processed so far
                - success_count: Successfully processed rows
                - failure_count: Failed rows
                - percentage: Progress percentage (0-100)
                - result_files: URLs for success and failed result files
                - error_message: Error message if failed
        """
        task_id = request.query_params.get("task_id")

        if not task_id:
            return Response(
                {"error": _(ERROR_TASK_ID_REQUIRED)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get import job from database
        try:
            import_job = ImportJob.objects.select_related(
                "file",
                "created_by",
                "result_success_file",
                "result_failed_file",
            ).get(id=task_id)
        except ImportJob.DoesNotExist:
            return Response(
                {"error": _("Import job not found")},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get Redis progress data (fresher than DB)
        redis_progress = get_import_progress(str(import_job.id))

        # Serialize job data
        serializer = ImportJobSerializer(import_job)
        response_data = serializer.data

        # Merge Redis progress if available (prefer Redis for real-time data)
        if redis_progress:
            response_data["processed_rows"] = redis_progress.get("processed_rows", import_job.processed_rows)
            response_data["success_count"] = redis_progress.get("success_count", import_job.success_count)
            response_data["failure_count"] = redis_progress.get("failure_count", import_job.failure_count)
            if "percentage" in redis_progress:
                response_data["percentage"] = redis_progress["percentage"]

        return Response(response_data, status=status.HTTP_200_OK)
