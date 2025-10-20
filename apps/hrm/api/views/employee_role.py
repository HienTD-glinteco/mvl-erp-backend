from django.db import transaction
from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.audit_logging import AuditLoggingMixin, LogAction, batch_audit_context
from apps.audit_logging.history_mixin import HistoryMixin
from apps.core.models import User
from apps.hrm.api.filtersets.employee_role import EmployeeRoleFilterSet
from apps.hrm.api.serializers.employee_role import BulkUpdateRoleSerializer, EmployeeRoleListSerializer
from libs import BaseReadOnlyModelViewSet


@extend_schema_view(
    list=extend_schema(
        summary="List employees by role",
        description="Retrieve list of employees with role and organization information. Supports searching and filtering by branch, block, department, position, and role.",
        tags=["Employee Role Management"],
        parameters=[
            OpenApiParameter(
                name="search",
                description="Search by employee name or role name (case-insensitive)",
                type=str,
            ),
            OpenApiParameter(name="branch", description="Filter by branch", type=str),
            OpenApiParameter(name="block", description="Filter by block", type=str),
            OpenApiParameter(name="department", description="Filter by department", type=str),
            OpenApiParameter(name="position", description="Filter by position", type=str),
            OpenApiParameter(name="role", description="Filter by role", type=str),
            OpenApiParameter(
                name="ordering",
                description="Sort by field (default: -username). Add '-' prefix for descending order.",
                type=str,
            ),
        ],
        examples=[
            OpenApiExample(
                "List employees by role success",
                description="Example response when listing employees with role information",
                value={
                    "success": True,
                    "data": {
                        "count": 2,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": "user-uuid-1",
                                "username": "john.doe@example.com",
                                "full_name": "John Doe",
                                "role": {"id": 5, "code": "VT005", "name": "Project Manager"},
                                "branch_name": "Chi nhánh Hà Nội",
                                "block_name": "Khối Kinh doanh",
                                "department_name": "Phòng Kinh doanh 1",
                                "position_name": "Manager",
                            },
                            {
                                "id": "user-uuid-2",
                                "username": "jane.smith@example.com",
                                "full_name": "Jane Smith",
                                "role": {"id": 3, "code": "VT003", "name": "Employee"},
                                "branch_name": "Chi nhánh TP.HCM",
                                "block_name": "Khối Hỗ trợ",
                                "department_name": "Phòng Nhân sự",
                                "position_name": "HR Staff",
                            },
                        ],
                    },
                },
                response_only=True,
            )
        ],
    ),
)
class EmployeeRoleViewSet(HistoryMixin, AuditLoggingMixin, BaseReadOnlyModelViewSet):
    """
    ViewSet for managing employees by role.

    Provides listing and filtering of employees with their role information.
    Supports bulk updating of employee roles.
    """

    queryset = User.objects.select_related("role").prefetch_related(
        "organization_positions__department__block__branch",
        "organization_positions__position",
    )
    serializer_class = EmployeeRoleListSerializer
    filterset_class = EmployeeRoleFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["username", "first_name", "last_name", "role__name"]
    ordering_fields = ["username", "first_name", "last_name", "role__name", "created_at"]
    ordering = ["-username"]  # Default ordering: descending by employee code

    # Permission registration attributes
    module = "HRM"
    submodule = "Employee Management"
    permission_prefix = "employee_role"

    def get_queryset(self):
        """
        Filter to only active users with organization positions.
        Returns only users who have active organization positions.
        """
        queryset = super().get_queryset()
        # Filter to active users
        queryset = queryset.filter(is_active=True)
        # Only include users with at least one organization position
        queryset = queryset.filter(organization_positions__isnull=False).distinct()
        return queryset

    @extend_schema(
        summary="Bulk update employee roles",
        description="Update roles for multiple employees at once (maximum 25 employees). "
        "When an employee's role changes, the system will log them out.",
        tags=["Employee Role Management"],
        request=BulkUpdateRoleSerializer,
        examples=[
            OpenApiExample(
                "Bulk update roles request",
                description="Example request to update roles for multiple employees",
                value={"employee_ids": ["user-uuid-1", "user-uuid-2", "user-uuid-3"], "new_role_id": 5},
                request_only=True,
            ),
            OpenApiExample(
                "Bulk update success",
                description="Success response when updating roles",
                value={"success": True, "data": {"message": "Update successful", "updated_count": 3}},
                response_only=True,
            ),
            OpenApiExample(
                "Bulk update error - no employees",
                description="Error when no employees are selected",
                value={"success": False, "error": {"employee_ids": ["Please select at least one employee."]}},
                response_only=True,
                status_codes=["400"],
            ),
            OpenApiExample(
                "Bulk update error - too many",
                description="Error when more than 25 employees are selected",
                value={"success": False, "error": {"employee_ids": ["Cannot update more than 25 employees at once."]}},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    @action(detail=False, methods=["post"], url_path="bulk-update-roles")
    def bulk_update_roles(self, request):
        """
        Bulk update roles for multiple employees.

        Business rules:
        - Maximum 25 employees per update
        - New role must be selected
        - Invalidates all active sessions for users whose roles changed
        """
        serializer = BulkUpdateRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        employee_ids = serializer.validated_data["employee_ids"]
        new_role = serializer.validated_data["new_role_id"]

        # Use transaction to ensure atomicity
        with transaction.atomic():
            # Get employees whose role will actually change
            employees_to_update = User.objects.filter(id__in=employee_ids).exclude(role=new_role)

            # Wrap in batch audit log to track all role changes together
            with batch_audit_context(
                action=LogAction.CHANGE,
                model_class=User,
                user=request.user,
                request=request,
                bulk_operation="role_update",
                new_role_id=new_role.id,
                new_role_name=new_role.name,
            ) as batch:
                updated_count = 0
                for employee in employees_to_update:
                    employee.role = new_role
                    employee.active_session_key = ""
                    employee.save(update_fields=["role", "active_session_key"])
                    updated_count += 1
                    batch.increment_count()

        return Response(
            {
                "success": True,
                "message": _("Update successful"),
                "updated_count": updated_count,
            },
            status=status.HTTP_200_OK,
        )
