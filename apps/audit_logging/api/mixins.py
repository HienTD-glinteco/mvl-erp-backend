"""
Mixins for Django REST Framework ViewSets to enable audit logging.

These mixins automatically set up the audit context for API requests,
ensuring that model changes made during the request are properly logged.
"""

from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..exceptions import AuditLogException
from ..middleware import audit_context
from ..opensearch_client import get_opensearch_client
from .serializers import AuditLogSearchResponseSerializer, AuditLogSearchSerializer, AuditLogSerializer


class AuditLoggingMixin:
    """
    Mixin for DRF ViewSets to enable automatic audit logging and history viewing.

    This mixin provides:
    1. Automatic audit logging - Sets up audit context for model changes
    2. History viewing - Adds endpoints to view audit log history

    Add this mixin to any ViewSet where you want model changes to be
    automatically logged with user context and provide history endpoints.

    Usage:
        class CustomerViewSet(AuditLoggingMixin, viewsets.ModelViewSet):
            queryset = Customer.objects.all()
            serializer_class = CustomerSerializer

    This mixin overrides the initial() method to set up audit context
    for the entire request lifecycle, and adds history viewing actions.

    Automatically adds:
        - GET /{resource}/{id}/histories/ endpoint
        - GET /{resource}/{id}/history/{log_id}/ endpoint
        - {prefix}.histories permission
        - {prefix}.history_detail permission
    """

    def initial(self, request, *args, **kwargs):
        """
        Runs anything that needs to occur prior to calling the method handler.

        Wraps the parent initial() call with audit context to enable logging.
        """
        # Set up audit context for this request
        self._audit_context = audit_context(request)
        self._audit_context.__enter__()

        try:
            super().initial(request, *args, **kwargs)
        except Exception:
            # Clean up audit context on error
            self._audit_context.__exit__(None, None, None)
            raise

    def finalize_response(self, request, response, *args, **kwargs):
        """
        Finalizes the response.

        Cleans up the audit context after the response is generated.
        """
        response = super().finalize_response(request, response, *args, **kwargs)

        # Clean up audit context
        if hasattr(self, "_audit_context"):
            self._audit_context.__exit__(None, None, None)

        return response

    @extend_schema(
        summary="Get object histories",
        description="Retrieve the audit log history for this object, showing all changes made over time",
        tags=["0.0: History"],
        responses={200: AuditLogSearchResponseSerializer},
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
                name="page",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Page for pagination (default: 1)",
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
                        "count": 2,
                        "next": 0,
                        "previous": 0,
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
    @action(detail=True, methods=["get"], url_path="histories")
    def histories(self, request, pk=None):
        """
        Get the audit log history for a specific object.

        Returns a list of all audit log entries for this object,
        including create, update, and delete actions.
        """
        # Get the object to ensure it exists and get its model info
        try:
            obj = self.get_object()
        except Exception:
            return Response({"error": "Object not found"}, status=status.HTTP_404_NOT_FOUND)

        # Get model metadata
        model_class = obj.__class__
        object_type = model_class._meta.model_name
        object_id = str(obj.pk)
        object_name = getattr(obj, "name", str(obj))

        # Build search parameters
        search_params = {
            "object_types": [object_type],
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
        if request.query_params.get("page"):
            search_params["page"] = request.query_params["page"]

        # Use the audit log search serializer
        serializer = AuditLogSearchSerializer(data=search_params, context={"object_name": object_name})
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

    @extend_schema(
        summary="Get history detail",
        description="Retrieve detailed information about a specific audit log entry",
        tags=["0.0: History"],
        responses={
            200: AuditLogSerializer,
        },
        parameters=[
            OpenApiParameter(
                name="id",
                type=str,
                location=OpenApiParameter.PATH,
                description="ID of the object",
                required=True,
            ),
            OpenApiParameter(
                name="log_id",
                type=str,
                location=OpenApiParameter.PATH,
                description="ID of the specific audit log entry",
                required=True,
            ),
        ],
        examples=[
            OpenApiExample(
                "Success - History detail",
                description="Example response showing detailed information about a specific history entry",
                value={
                    "success": True,
                    "data": {
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
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error - History entry not found",
                description="Error response when history entry doesn't exist",
                value={"success": False, "error": "History entry not found"},
                response_only=True,
                status_codes=["404"],
            ),
        ],
    )
    @action(detail=True, methods=["get"], url_path="history/(?P<log_id>[^/.]+)")
    def history_detail(self, request, pk=None, log_id=None):
        """
        Get detailed information about a specific audit log entry.

        Returns detailed information about a single audit log entry
        for this object.
        """
        # Get the object to ensure it exists and get its model info
        try:
            obj = self.get_object()
        except Exception:
            return Response({"error": "Object not found"}, status=status.HTTP_404_NOT_FOUND)

        # Get model metadata
        model_class = obj.__class__
        object_type = model_class._meta.model_name
        object_id = str(obj.pk)
        object_name = getattr(obj, "name", str(obj))

        # Ensure log_id provided
        if not log_id:
            return Response({"error": "log_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            opensearch_client = get_opensearch_client()
            log_data = opensearch_client.get_log_by_id(log_id)

            # Verify the log belongs to the requested object
            if not log_data:
                return Response({"error": "History entry not found"}, status=status.HTTP_404_NOT_FOUND)

            # Compare object_type and object_id from the log with the current object
            log_object_type = str(log_data.get("object_type", ""))
            log_object_id = str(log_data.get("object_id", ""))

            if log_object_type.lower() != str(object_type).lower() or log_object_id != object_id:
                return Response({"error": "History entry not found"}, status=status.HTTP_404_NOT_FOUND)

            log_data["object_name"] = object_name

            serializer = AuditLogSerializer(log_data)
            return Response(serializer.data)

        except AuditLogException as e:
            # Treat not-found as 404, other errors as 500
            if "not found" in str(e).lower():
                return Response({"error": "History entry not found"}, status=status.HTTP_404_NOT_FOUND)
            return Response(
                {"error": f"Failed to retrieve history detail: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response({"error": "Internal server error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
