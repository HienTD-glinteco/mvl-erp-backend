"""
Mixin for adding history viewing capabilities to ViewSets.

This mixin provides an endpoint to retrieve the audit log history
of a specific object instance.
"""

from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response


class HistoryMixin:
    """
    Mixin that adds a history action to ViewSets.

    This mixin provides an endpoint to retrieve the audit log history
    of a specific object instance. It queries the audit logging system
    based on the object's type and ID.

    Requirements:
        - The ViewSet must have a queryset with a model
        - The model should be registered with @audit_logging_register
        - The ViewSet should inherit from this mixin before ModelViewSet

    Usage:
        from apps.audit_logging import HistoryMixin
        from libs import BaseModelViewSet

        class CustomerViewSet(HistoryMixin, BaseModelViewSet):
            queryset = Customer.objects.all()
            serializer_class = CustomerSerializer
            module = "CRM"
            submodule = "Customer Management"
            permission_prefix = "customer"

        This will automatically add:
            - GET /customers/{id}/history/ endpoint
            - customer.history permission
    """

    @extend_schema(
        summary="Get object history",
        description="Retrieve the audit log history for this object, showing all changes made over time",
        tags=["History"],
        parameters=[
            OpenApiParameter(
                name="id",
                type=str,
                location=OpenApiParameter.PATH,
                description="ID of the object",
                required=True,
            ),
            OpenApiParameter(
                name="from_date",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter logs from this date (YYYY-MM-DD)",
                required=False,
            ),
            OpenApiParameter(
                name="to_date",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter logs to this date (YYYY-MM-DD)",
                required=False,
            ),
            OpenApiParameter(
                name="action",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by action type (CREATE, CHANGE, DELETE)",
                required=False,
            ),
            OpenApiParameter(
                name="page_size",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Number of results per page (1-100, default: 50)",
                required=False,
            ),
            OpenApiParameter(
                name="from_offset",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Offset for pagination (default: 0)",
                required=False,
            ),
        ],
        examples=[
            OpenApiExample(
                "Success - History with changes",
                description="Example response showing object history with field-level changes",
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
                                "employee_code": "EMP001",
                                "action": "CHANGE",
                                "object_type": "customer",
                                "object_id": "123",
                                "object_repr": "John Doe",
                                "change_message": {
                                    "headers": ["field", "old_value", "new_value"],
                                    "rows": [
                                        {
                                            "field": "Email",
                                            "old_value": "old@example.com",
                                            "new_value": "new@example.com",
                                        },
                                        {"field": "Phone", "old_value": "0123456789", "new_value": "0987654321"},
                                    ],
                                },
                            },
                            {
                                "log_id": "xyz789uvw012",
                                "timestamp": "2025-10-12T10:15:00Z",
                                "user_id": "user-uuid-2",
                                "username": "john.doe@example.com",
                                "full_name": "John Doe",
                                "action": "CREATE",
                                "object_type": "customer",
                                "object_id": "123",
                                "object_repr": "John Doe",
                                "change_message": "Created new object",
                            },
                        ],
                        "total": 2,
                        "page_size": 50,
                        "from_offset": 0,
                        "has_next": False,
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error - Object not found",
                description="Error response when object doesn't exist",
                value={"success": False, "error": "Object not found"},
                response_only=True,
                status_codes=["404"],
            ),
        ],
    )
    @action(detail=True, methods=["get"], url_path="history")
    def history(self, request, pk=None):
        """
        Get the audit log history for a specific object.

        Returns a list of all audit log entries for this object,
        including create, update, and delete actions.
        """
        # Import here to avoid circular dependency
        from .api.serializers import AuditLogSearchSerializer
        from .exceptions import AuditLogException

        # Get the object to ensure it exists and get its model info
        try:
            obj = self.get_object()
        except Exception:
            return Response({"error": "Object not found"}, status=status.HTTP_404_NOT_FOUND)

        # Get model metadata
        model_class = obj.__class__
        object_type = model_class._meta.model_name
        object_id = str(obj.pk)

        # Build search parameters
        search_params = {
            "object_type": object_type,
            "object_id": object_id,
        }

        # Add optional filters from query params
        if request.query_params.get("from_date"):
            search_params["from_date"] = request.query_params["from_date"]
        if request.query_params.get("to_date"):
            search_params["to_date"] = request.query_params["to_date"]
        if request.query_params.get("action"):
            search_params["action"] = request.query_params["action"]
        if request.query_params.get("page_size"):
            search_params["page_size"] = request.query_params["page_size"]
        if request.query_params.get("from_offset"):
            search_params["from_offset"] = request.query_params["from_offset"]

        # Use the audit log search serializer
        serializer = AuditLogSearchSerializer(data=search_params)
        if not serializer.is_valid():
            return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Execute search
            result = serializer.search()
            return Response(result)
        except AuditLogException as e:
            return Response(
                {"error": f"Failed to retrieve history: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
