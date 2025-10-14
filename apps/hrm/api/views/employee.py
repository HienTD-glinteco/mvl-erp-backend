from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter, SearchFilter

from apps.audit_logging import AuditLoggingMixin
from apps.hrm.api.filtersets import EmployeeFilterSet
from apps.hrm.api.serializers import EmployeeSerializer
from apps.hrm.models import Employee
from libs import BaseModelViewSet


@extend_schema_view(
    list=extend_schema(
        summary="List all employees",
        description="Retrieve a paginated list of all employees with support for filtering by code and name",
        tags=["Employee"],
        examples=[
            OpenApiExample(
                "List employees success",
                description="Example response when listing employees",
                value={
                    "success": True,
                    "data": {
                        "count": 2,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": "550e8400-e29b-41d4-a716-446655440001",
                                "code": "EMP001",
                                "name": "John Doe",
                                "user": "user-uuid-1",
                                "email": "john.doe@example.com",
                                "phone": "+84901234567",
                                "is_active": True,
                                "created_at": "2025-01-01T00:00:00Z",
                                "updated_at": "2025-01-01T00:00:00Z",
                            },
                            {
                                "id": "550e8400-e29b-41d4-a716-446655440002",
                                "code": "EMP002",
                                "name": "Jane Smith",
                                "user": "user-uuid-2",
                                "email": "jane.smith@example.com",
                                "phone": "+84907654321",
                                "is_active": True,
                                "created_at": "2025-01-02T10:00:00Z",
                                "updated_at": "2025-01-02T10:00:00Z",
                            },
                        ],
                    },
                },
                response_only=True,
            )
        ],
    ),
    create=extend_schema(
        summary="Create a new employee",
        description="Create a new employee in the system",
        tags=["Employee"],
        examples=[
            OpenApiExample(
                "Create employee request",
                description="Example request to create a new employee",
                value={
                    "name": "Michael Johnson",
                    "email": "michael.johnson@example.com",
                    "phone": "+84901111111",
                    "is_active": True,
                },
                request_only=True,
            ),
            OpenApiExample(
                "Create employee success",
                description="Success response when creating an employee",
                value={
                    "success": True,
                    "data": {
                        "id": "550e8400-e29b-41d4-a716-446655440003",
                        "code": "EMP003",
                        "name": "Michael Johnson",
                        "user": "user-uuid-3",
                        "email": "michael.johnson@example.com",
                        "phone": "+84901111111",
                        "is_active": True,
                        "created_at": "2025-01-15T14:30:00Z",
                        "updated_at": "2025-01-15T14:30:00Z",
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Create employee validation error",
                description="Error response when validation fails",
                value={"success": False, "error": {"email": ["Employee with this email already exists"]}},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get employee details",
        description="Retrieve detailed information about a specific employee",
        tags=["Employee"],
        examples=[
            OpenApiExample(
                "Get employee success",
                description="Example response when retrieving an employee",
                value={
                    "success": True,
                    "data": {
                        "id": "550e8400-e29b-41d4-a716-446655440001",
                        "code": "EMP001",
                        "name": "John Doe",
                        "user": "user-uuid-1",
                        "email": "john.doe@example.com",
                        "phone": "+84901234567",
                        "is_active": True,
                        "created_at": "2025-01-01T00:00:00Z",
                        "updated_at": "2025-01-01T00:00:00Z",
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Get employee not found",
                description="Error response when employee is not found",
                value={"success": False, "error": "Employee not found"},
                response_only=True,
                status_codes=["404"],
            ),
        ],
    ),
    update=extend_schema(
        summary="Update employee",
        description="Update employee information",
        tags=["Employee"],
        examples=[
            OpenApiExample(
                "Update employee request",
                description="Example request to update an employee",
                value={
                    "name": "John Michael Doe",
                    "email": "john.doe@example.com",
                    "phone": "+84901234567",
                    "is_active": True,
                },
                request_only=True,
            ),
            OpenApiExample(
                "Update employee success",
                description="Success response when updating an employee",
                value={
                    "success": True,
                    "data": {
                        "id": "550e8400-e29b-41d4-a716-446655440001",
                        "code": "EMP001",
                        "name": "John Michael Doe",
                        "user": "user-uuid-1",
                        "email": "john.doe@example.com",
                        "phone": "+84901234567",
                        "is_active": True,
                        "created_at": "2025-01-01T00:00:00Z",
                        "updated_at": "2025-01-16T09:15:00Z",
                    },
                },
                response_only=True,
            ),
        ],
    ),
    partial_update=extend_schema(
        summary="Partially update employee",
        description="Partially update employee information",
        tags=["Employee"],
        examples=[
            OpenApiExample(
                "Partial update request",
                description="Example request to partially update an employee",
                value={"phone": "+84902222222"},
                request_only=True,
            ),
            OpenApiExample(
                "Partial update success",
                description="Success response when partially updating an employee",
                value={
                    "success": True,
                    "data": {
                        "id": "550e8400-e29b-41d4-a716-446655440001",
                        "code": "EMP001",
                        "name": "John Doe",
                        "user": "user-uuid-1",
                        "email": "john.doe@example.com",
                        "phone": "+84902222222",
                        "is_active": True,
                        "created_at": "2025-01-01T00:00:00Z",
                        "updated_at": "2025-01-16T11:30:00Z",
                    },
                },
                response_only=True,
            ),
        ],
    ),
    destroy=extend_schema(
        summary="Delete employee",
        description="Remove an employee from the system",
        tags=["Employee"],
        examples=[
            OpenApiExample(
                "Delete employee success",
                description="Success response when deleting an employee",
                value=None,
                response_only=True,
                status_codes=["204"],
            ),
            OpenApiExample(
                "Delete employee error",
                description="Error response when employee cannot be deleted (e.g., has related records)",
                value={"success": False, "error": "Cannot delete employee with existing records"},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
)
class EmployeeViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for Employee model"""

    queryset = Employee.objects.select_related("user").all()
    serializer_class = EmployeeSerializer
    filterset_class = EmployeeFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["code", "name"]
    ordering_fields = ["code", "name", "created_at"]
    ordering = ["code"]

    # Permission registration attributes
    module = "HRM"
    submodule = "Employee Management"
    permission_prefix = "employee"
