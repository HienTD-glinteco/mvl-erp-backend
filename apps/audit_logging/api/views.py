import logging

from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from libs.drf.mixin.permission import PermissionRegistrationMixin

from ..exceptions import AuditLogException
from ..opensearch_client import get_opensearch_client
from .serializers import AuditLogSearchResponseSerializer, AuditLogSearchSerializer, AuditLogSerializer

logger = logging.getLogger(__name__)


class AuditLogViewSet(PermissionRegistrationMixin, viewsets.GenericViewSet):
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
                "Get audit log detail success - CREATE action",
                description="Example response when retrieving audit log details for CREATE action",
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
                        "change_message": "Created new object",
                        "ip_address": "192.168.1.100",
                        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "session_key": "sess-67890",
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Get audit log detail success - CHANGE action with field changes",
                description="Example response for CHANGE action showing structured change_message with field-level changes",
                value={
                    "success": True,
                    "data": {
                        "log_id": "xyz789uvw012",
                        "timestamp": "2025-10-17T06:09:48Z",
                        "user_id": "user-uuid-2",
                        "username": "john.doe@example.com",
                        "full_name": "John Doe",
                        "employee_code": "EMP001",
                        "action": "CHANGE",
                        "object_type": "Employee",
                        "object_id": "789",
                        "object_repr": "Jane Smith",
                        "change_message": {
                            "headers": ["field", "old_value", "new_value"],
                            "rows": [
                                {
                                    "field": "Phone number",
                                    "old_value": "0987654321",
                                    "new_value": "1234567890",
                                },
                                {"field": "Note", "old_value": "string", "new_value": "new new"},
                            ],
                        },
                        "ip_address": "192.168.1.101",
                        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                        "session_key": "sess-12345",
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Get audit log detail - CHANGE action with array values",
                description="Example showing change_message with array values (e.g., file uploads)",
                value={
                    "success": True,
                    "data": {
                        "log_id": "def456ghi789",
                        "timestamp": "2025-10-17T08:15:30Z",
                        "user_id": "user-uuid-3",
                        "username": "admin@example.com",
                        "full_name": "Admin User",
                        "employee_code": "EMP002",
                        "action": "CHANGE",
                        "object_type": "Certificate",
                        "object_id": "123",
                        "object_repr": "Employee Certificate",
                        "change_message": {
                            "headers": ["field", "old_value", "new_value"],
                            "rows": [
                                {
                                    "field": "Ngày hết hiệu lực",
                                    "old_value": "21/09/2025",
                                    "new_value": "10/09/2025",
                                },
                                {
                                    "field": "Văn bằng chứng chỉ",
                                    "old_value": ["chứng chỉ cũ hết hạn.jpg"],
                                    "new_value": ["chứng chỉ 1.jpg", "chứng chỉ 2.jpg"],
                                },
                            ],
                        },
                        "ip_address": "192.168.1.102",
                        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "session_key": "sess-99999",
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Get audit log detail - DELETE action with null change_message",
                description="Example showing null change_message (no change details)",
                value={
                    "success": True,
                    "data": {
                        "log_id": "jkl012mno345",
                        "timestamp": "2025-10-17T09:00:00Z",
                        "user_id": "user-uuid-4",
                        "username": "manager@example.com",
                        "full_name": "Manager User",
                        "action": "DELETE",
                        "object_type": "Department",
                        "object_id": "456",
                        "object_repr": "Marketing Department",
                        "change_message": None,
                        "ip_address": "192.168.1.103",
                        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                        "session_key": "sess-11111",
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
            serializer = AuditLogSerializer(log_data)
            return Response(serializer.data)

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
