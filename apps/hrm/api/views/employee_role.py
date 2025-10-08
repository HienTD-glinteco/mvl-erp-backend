from django.db import transaction
from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.audit_logging import AuditLoggingMixin, LogAction, batch_audit_context
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
    ),
)
class EmployeeRoleViewSet(AuditLoggingMixin, BaseReadOnlyModelViewSet):
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
        responses={
            200: {
                "description": "Update successful",
                "content": {
                    "application/json": {
                        "example": {
                            "success": True,
                            "message": _("Update successful"),
                            "updated_count": 5,
                        }
                    }
                },
            },
            400: {
                "description": "Validation error",
                "content": {
                    "application/json": {
                        "examples": {
                            "no_selection": {
                                "summary": "No employees selected",
                                "value": {"employee_ids": ["Please select at least one employee."]},
                            },
                            "too_many": {
                                "summary": "More than 25 employees",
                                "value": {"employee_ids": ["Cannot update more than 25 employees at once."]},
                            },
                            "no_role": {
                                "summary": "No new role selected",
                                "value": {"new_role_id": ["Please select a new role."]},
                            },
                        }
                    }
                },
            },
        },
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
