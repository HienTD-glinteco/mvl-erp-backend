from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter, SearchFilter

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets import EmployeeDependentFilterSet
from apps.hrm.api.serializers import EmployeeDependentSerializer
from apps.hrm.models import EmployeeDependent
from libs import BaseModelViewSet


@extend_schema_view(
    list=extend_schema(
        summary="List employee dependents",
        description="Retrieve a paginated list of employee dependents with support for filtering and search",
        tags=["Employee Dependent"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "count": 1,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": 1,
                                "employee": {"id": 1, "code": "EMP001", "fullname": "John Doe"},
                                "dependent_name": "Jane Doe",
                                "relationship": "CHILD",
                                "relationship_display": "Child",
                                "date_of_birth": "2010-05-12",
                                "citizen_id": "123456789",
                                "attachment": None,
                                "note": "Primary dependent",
                                "is_active": True,
                                "created_by": 1,
                                "created_at": "2025-10-31T05:00:00Z",
                                "updated_at": "2025-10-31T05:00:00Z",
                            }
                        ],
                    },
                },
                response_only=True,
            )
        ],
    ),
    create=extend_schema(
        summary="Create employee dependent",
        description="Create a new employee dependent record with optional file attachment",
        tags=["Employee Dependent"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "employee": {"id": 1, "code": "EMP001", "fullname": "John Doe"},
                        "dependent_name": "Jane Doe",
                        "relationship": "CHILD",
                        "relationship_display": "Child",
                        "date_of_birth": "2010-05-12",
                        "citizen_id": "123456789",
                        "attachment": None,
                        "note": "Primary dependent",
                        "is_active": True,
                        "created_by": 1,
                        "created_at": "2025-10-31T05:00:00Z",
                        "updated_at": "2025-10-31T05:00:00Z",
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Success with attachment",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "employee": {"id": 1, "code": "EMP001", "fullname": "John Doe"},
                        "dependent_name": "Jane Doe",
                        "relationship": "CHILD",
                        "relationship_display": "Child",
                        "date_of_birth": "2010-05-12",
                        "citizen_id": "123456789",
                        "attachment": {
                            "id": 1,
                            "purpose": "dependent",
                            "file_name": "birth_certificate.pdf",
                            "file_path": "uploads/dependent/1/birth_certificate.pdf",
                            "size": 245678,
                            "is_confirmed": True,
                            "view_url": "https://example.com/view/...",
                            "download_url": "https://example.com/download/...",
                        },
                        "note": "Primary dependent",
                        "is_active": True,
                        "created_by": 1,
                        "created_at": "2025-10-31T05:00:00Z",
                        "updated_at": "2025-10-31T05:00:00Z",
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error",
                value={"success": False, "error": {"employee": ["This field is required."]}},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Retrieve employee dependent",
        description="Get detailed information about a specific employee dependent",
        tags=["Employee Dependent"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "employee": {"id": 1, "code": "EMP001", "fullname": "John Doe"},
                        "dependent_name": "Jane Doe",
                        "relationship": "CHILD",
                        "relationship_display": "Child",
                        "date_of_birth": "2010-05-12",
                        "citizen_id": "123456789",
                        "attachment": None,
                        "note": "Primary dependent",
                        "is_active": True,
                        "created_by": 1,
                        "created_at": "2025-10-31T05:00:00Z",
                        "updated_at": "2025-10-31T05:00:00Z",
                    },
                },
                response_only=True,
            )
        ],
    ),
    update=extend_schema(
        summary="Update employee dependent",
        description="Update an existing employee dependent record",
        tags=["Employee Dependent"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "employee": {"id": 1, "code": "EMP001", "fullname": "John Doe"},
                        "dependent_name": "Jane Doe",
                        "relationship": "CHILD",
                        "relationship_display": "Child",
                        "date_of_birth": "2010-05-12",
                        "citizen_id": "123456789012",
                        "attachment": None,
                        "note": "Updated note",
                        "is_active": True,
                        "created_by": 1,
                        "created_at": "2025-10-31T05:00:00Z",
                        "updated_at": "2025-10-31T06:00:00Z",
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error",
                value={"success": False, "error": {"citizen_id": ["Invalid: must be exactly 9 or 12 digits."]}},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    partial_update=extend_schema(
        summary="Partially update employee dependent",
        description="Partially update an existing employee dependent record",
        tags=["Employee Dependent"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "employee": {"id": 1, "code": "EMP001", "fullname": "John Doe"},
                        "dependent_name": "Jane Doe",
                        "relationship": "CHILD",
                        "relationship_display": "Child",
                        "date_of_birth": "2010-05-12",
                        "citizen_id": "123456789",
                        "attachment": None,
                        "note": "Partially updated note",
                        "is_active": True,
                        "created_by": 1,
                        "created_at": "2025-10-31T05:00:00Z",
                        "updated_at": "2025-10-31T06:00:00Z",
                    },
                },
                response_only=True,
            )
        ],
    ),
    destroy=extend_schema(
        summary="Delete employee dependent",
        description="Soft delete an employee dependent record (sets is_active to False)",
        tags=["Employee Dependent"],
        examples=[
            OpenApiExample(
                "Success",
                value={"success": True, "data": None},
                response_only=True,
            ),
            OpenApiExample(
                "Error - Not Found",
                value={"success": False, "error": "Not found."},
                response_only=True,
                status_codes=["404"],
            ),
        ],
    ),
)
class EmployeeDependentViewSet(AuditLoggingMixin, BaseModelViewSet):
    """
    ViewSet for EmployeeDependent model.

    Provides CRUD operations for employee dependents with:
    - List: Paginated list with filtering and search
    - Create: Create new dependent with file attachment support
    - Retrieve: Get detailed information
    - Update/Partial Update: Modify existing dependent
    - Delete: Soft delete (sets is_active to False)

    Filtering:
        - employee: Filter by employee ID
        - relationship: Filter by relationship type
        - is_active: Filter by active status
        - search: Search across employee code, employee name, dependent name, and relationship

    Ordering:
        - Default: -created_at (newest first)
        - Available fields: created_at, dependent_name, relationship
    """

    queryset = EmployeeDependent.objects.select_related("employee", "attachment", "created_by").all()
    serializer_class = EmployeeDependentSerializer
    filterset_class = EmployeeDependentFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["dependent_name", "relationship", "employee__code", "employee__fullname"]
    ordering_fields = ["created_at", "dependent_name", "relationship"]
    ordering = ["-created_at"]

    def perform_destroy(self, instance):
        """Soft delete by setting is_active to False."""
        instance.is_active = False
        instance.save(update_fields=["is_active"])
