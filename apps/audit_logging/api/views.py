import logging

from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..exceptions import AuditLogException
from ..opensearch_client import get_opensearch_client
from .serializers import AuditLogSearchResponseSerializer, AuditLogSearchSerializer, AuditLogSerializer

logger = logging.getLogger(__name__)


class AuditLogViewSet(viewsets.GenericViewSet):
    """ViewSet for audit log operations."""

    permission_classes = [IsAuthenticated]

    module = "Core"
    submodule = "Audit Logging"
    permission_prefix = "audit_logging"

    @extend_schema(
        summary="Search audit logs",
        description="Search audit logs with filters. Returns a list of logs with summary fields.",
        parameters=[AuditLogSearchSerializer],
        responses={
            200: OpenApiResponse(
                response=AuditLogSearchResponseSerializer,
                description="Successful response with audit logs data",
            ),
        },
        examples=[
            OpenApiExample(
                "Search audit logs success",
                description="Example response when searching audit logs",
                value={
                    "success": True,
                    "data": {
                        "results": [
                            {
                                "log_id": "abc123def456",
                                "timestamp": "2025-10-13T14:30:00Z",
                                "user_id": "user-uuid-1",
                                "username": "admin@example.com",
                                "full_name": "Admin User",
                                "action": "CREATE",
                                "object_type": "Role",
                                "object_id": "10",
                                "object_repr": "Project Manager",
                            },
                            {
                                "log_id": "xyz789uvw012",
                                "timestamp": "2025-10-13T13:15:00Z",
                                "user_id": "user-uuid-2",
                                "username": "john.doe@example.com",
                                "full_name": "John Doe",
                                "action": "UPDATE",
                                "object_type": "User",
                                "object_id": "user-uuid-3",
                                "object_repr": "jane.smith@example.com",
                            },
                        ],
                        "total": 150,
                        "page": 1,
                        "page_size": 20,
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Search audit logs validation error",
                description="Error response when validation fails",
                value={"success": False, "error": {"start_date": ["Invalid date format. Use YYYY-MM-DD."]}},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    @action(detail=False, methods=["get"], url_path="search")
    def search(self, request):
        """
        Search audit logs using OpenSearch.

        Returns summary fields only (log_id, timestamp, user_id, username, full_name,
        action, object_type, object_id, object_repr).

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
        description="Get full details of an audit log by log_id.",
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
            200: OpenApiResponse(
                response=AuditLogSerializer,
                description="Successful response with full audit log data",
            ),
        },
        examples=[
            OpenApiExample(
                "Get audit log detail success",
                description="Example response when retrieving audit log details",
                value={
                    "success": True,
                    "data": {
                        "log_id": "abc123def456",
                        "timestamp": "2025-10-13T14:30:00Z",
                        "user_id": "user-uuid-1",
                        "username": "admin@example.com",
                        "full_name": "Admin User",
                        "action": "CREATE",
                        "object_type": "Role",
                        "object_id": "10",
                        "object_repr": "Project Manager",
                        "ip_address": "192.168.1.100",
                        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "changes": {
                            "name": {"old": None, "new": "Project Manager"},
                            "description": {"old": None, "new": "Manages projects and teams"},
                            "permission_ids": {"old": None, "new": [1, 2, 5, 10]},
                        },
                        "additional_data": {"request_id": "req-12345", "session_id": "sess-67890"},
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Get audit log detail not found",
                description="Error response when audit log is not found",
                value={"success": False, "error": "Log with id abc123 not found"},
                response_only=True,
                status_codes=["404"],
            ),
        ],
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
