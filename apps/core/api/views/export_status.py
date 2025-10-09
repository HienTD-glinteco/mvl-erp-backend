"""
API view for checking export task status.
"""

from celery.result import AsyncResult

from django.utils.translation import gettext as _

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import OpenApiParameter, extend_schema


class ExportStatusView(APIView):
    """
    API view to check the status of an async export task.
    """

    @extend_schema(
        summary="Check export task status",
        description="Check the status of an asynchronous export task using the task ID.",
        parameters=[
            OpenApiParameter(
                name="task_id",
                description="Celery task ID returned from async export",
                required=True,
                type=str,
            ),
        ],
        tags=["Export"],
    )
    def get(self, request):
        """
        Check export task status.

        Query parameters:
            task_id: Celery task ID

        Returns:
            dict: Task status with keys:
                - status: Task status (PENDING, SUCCESS, FAILURE)
                - file_url: Download URL (if SUCCESS)
                - error: Error message (if FAILURE)
        """
        task_id = request.query_params.get("task_id")

        if not task_id:
            return Response(
                {"error": _("task_id parameter is required")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get task result
        task_result = AsyncResult(task_id)

        response_data = {
            "task_id": task_id,
            "status": task_result.state,
        }

        if task_result.state == "SUCCESS":
            result = task_result.result
            response_data.update(
                {
                    "file_url": result.get("file_url"),
                    "file_path": result.get("file_path"),
                }
            )
        elif task_result.state == "FAILURE":
            response_data["error"] = str(task_result.result)

        return Response(response_data, status=status.HTTP_200_OK)
