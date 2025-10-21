"""
API view for checking export task status.
"""

from celery.result import AsyncResult
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.api.permissions import RoleBasedPermission
from apps.core.utils.permissions import register_permission
from libs.export_xlsx.progress import get_progress
from libs.export_xlsx.serializers import ExportStatusResponseSerializer


class ExportStatusView(APIView):
    """
    API view to check the status of an async export task with progress information.
    """

    permission_classes = [RoleBasedPermission]

    @extend_schema(
        summary="Check export task status",
        description="Check the status of an asynchronous export task using the task ID. "
        "Returns progress information including percentage, processed/total rows, speed, and ETA.",
        parameters=[
            OpenApiParameter(
                name="task_id",
                description="Celery task ID returned from async export",
                required=True,
                type=str,
            ),
        ],
        responses={
            200: ExportStatusResponseSerializer,
            400: OpenApiResponse(description="Bad request (missing task_id parameter)"),
        },
        tags=["Export"],
    )
    @register_permission("export.check_status", _("Check export status"))
    def get(self, request):
        """
        Check export task status with progress information.

        Query parameters:
            task_id: Celery task ID

        Returns:
            dict: Task status with keys:
                - status: Task status (PENDING, PROGRESS, SUCCESS, FAILURE)
                - percent: Progress percentage (0-100)
                - processed_rows: Number of rows processed
                - total_rows: Total number of rows
                - speed_rows_per_sec: Processing speed
                - eta_seconds: Estimated time to completion
                - file_url: Download URL (if SUCCESS)
                - error: Error message (if FAILURE)
        """
        task_id = request.query_params.get("task_id")

        if not task_id:
            return Response(
                {"error": _("task_id parameter is required")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get task result from Celery
        task_result = AsyncResult(task_id)

        response_data = {
            "task_id": task_id,
            "status": task_result.state,
        }

        # Try to get progress from Redis first (faster and more up-to-date)
        progress_data = get_progress(task_id)
        if progress_data:
            response_data.update(progress_data)
        # Fall back to Celery task meta if Redis data not available
        elif task_result.state == "PROGRESS" and task_result.info:
            response_data.update(task_result.info)

        # Handle SUCCESS state
        if task_result.state == "SUCCESS":
            result = task_result.result
            if isinstance(result, dict):
                response_data.update(
                    {
                        "file_url": result.get("file_url"),
                        "file_path": result.get("file_path"),
                        "percent": 100,
                    }
                )
        # Handle FAILURE state
        elif task_result.state == "FAILURE":
            # Only set error from Celery if not already present from Redis
            if "error" not in response_data:
                response_data["error"] = str(task_result.result)

        return Response(response_data, status=status.HTTP_200_OK)
