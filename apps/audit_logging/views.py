import logging

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .exceptions import AuditLogException
from .opensearch_client import get_opensearch_client
from .serializers import (
    AuditLogSearchResponseSerializer,
    AuditLogSearchSerializer,
    AuditLogSerializer,
)

logger = logging.getLogger(__name__)


class AuditLogViewSet(viewsets.GenericViewSet):
    """ViewSet for audit log operations."""

    permission_classes = [IsAuthenticated]

    # TODO: Add proper permission check to verify user has access to audit logs

    @extend_schema(
        summary="Search audit logs",
        description="Search audit logs with filters. Returns a list of logs with summary fields.",
        request=AuditLogSearchSerializer,
        responses={
            200: AuditLogSearchResponseSerializer,
            400: OpenApiResponse(description="Invalid parameters"),
            401: OpenApiResponse(description="Not authenticated"),
            500: OpenApiResponse(description="Failed to search audit logs"),
        },
    )
    @action(detail=False, methods=["get"], url_path="search")
    def search(self, request):
        """
        Search audit logs using OpenSearch.

        Returns summary fields only (log_id, timestamp, user_id, username, action,
        object_type, object_id, object_repr).

        Query parameters are validated using AuditLogSearchSerializer.
        """
        # Validate input
        serializer = AuditLogSearchSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Execute search using serializer
            response_data = serializer.search()
            return Response(response_data)

        except AuditLogException as e:
            logger.error(f"Audit log search failed: {e}")
            return Response(
                {"error": "Failed to search audit logs"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            logger.error(f"Unexpected error in audit log search: {e}", exc_info=True)
            return Response(
                {"error": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        summary="Get audit log details",
        description="Get full details of an audit log by log_id",
        parameters=[
            OpenApiParameter(
                name="log_id",
                type=str,
                location=OpenApiParameter.PATH,
                description="Unique identifier of the audit log",
                required=True,
            ),
        ],
        responses={
            200: AuditLogSerializer,
            400: OpenApiResponse(description="Invalid log_id"),
            401: OpenApiResponse(description="Not authenticated"),
            404: OpenApiResponse(description="Log not found"),
            500: OpenApiResponse(description="Failed to retrieve audit log"),
        },
    )
    @action(detail=False, methods=["get"], url_path="detail/(?P<log_id>[^/.]+)")
    def get_detail(self, request, log_id=None):
        """
        Retrieve a specific audit log by its log_id.

        Returns all fields for the requested log.

        Args:
            log_id: The unique identifier of the audit log

        Returns:
            Full audit log data with all fields
        """
        if not log_id:
            return Response({"error": "log_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            opensearch_client = get_opensearch_client()
            log_data = opensearch_client.get_log_by_id(log_id)
            return Response(log_data)

        except AuditLogException as e:
            if "not found" in str(e).lower():
                return Response(
                    {"error": f"Log with id {log_id} not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            logger.error(f"Failed to retrieve audit log {log_id}: {e}")
            return Response(
                {"error": "Failed to retrieve audit log"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            logger.error(f"Unexpected error retrieving audit log {log_id}: {e}", exc_info=True)
            return Response(
                {"error": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
