from django.db import transaction
from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.audit_logging import AuditLoggingMixin
from apps.core.models import User
from apps.hrm.api.filtersets.employee_role import EmployeeRoleFilterSet
from apps.hrm.api.serializers.employee_role import BulkUpdateRoleSerializer, EmployeeRoleListSerializer


@extend_schema_view(
    list=extend_schema(
        summary="Danh sách nhân viên theo vai trò",
        description="Lấy danh sách nhân viên với thông tin vai trò và tổ chức. Hỗ trợ tìm kiếm và lọc theo chi nhánh, khối, phòng ban, chức vụ, vai trò.",
        tags=["Quản lý Nhân viên theo Role"],
        parameters=[
            OpenApiParameter(
                name="search",
                description="Tìm kiếm theo tên nhân viên hoặc tên vai trò (không phân biệt chữ hoa/thường)",
                type=str,
            ),
            OpenApiParameter(name="branch", description="Lọc theo chi nhánh", type=str),
            OpenApiParameter(name="block", description="Lọc theo khối", type=str),
            OpenApiParameter(name="department", description="Lọc theo phòng ban", type=str),
            OpenApiParameter(name="position", description="Lọc theo chức vụ", type=str),
            OpenApiParameter(name="role", description="Lọc theo vai trò", type=str),
            OpenApiParameter(
                name="ordering",
                description="Sắp xếp theo trường (mặc định: -username). Thêm dấu '-' để sắp xếp giảm dần.",
                type=str,
            ),
        ],
    ),
)
class EmployeeRoleViewSet(AuditLoggingMixin, viewsets.ReadOnlyModelViewSet):
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
        summary="Chỉnh sửa vai trò hàng loạt",
        description="Cập nhật vai trò cho nhiều nhân viên cùng lúc (tối đa 25 nhân viên). "
        "Khi vai trò của nhân viên thay đổi, hệ thống sẽ đăng xuất tài khoản đó.",
        tags=["Quản lý Nhân viên theo Role"],
        request=BulkUpdateRoleSerializer,
        responses={
            200: {
                "description": "Cập nhật thành công",
                "content": {
                    "application/json": {
                        "example": {
                            "success": True,
                            "message": "Chỉnh sửa thành công",
                            "updated_count": 5,
                        }
                    }
                },
            },
            400: {
                "description": "Lỗi validation",
                "content": {
                    "application/json": {
                        "examples": {
                            "no_selection": {
                                "summary": "Chưa chọn nhân viên",
                                "value": {"employee_ids": ["Please select at least one employee."]},
                            },
                            "too_many": {
                                "summary": "Quá 25 nhân viên",
                                "value": {"employee_ids": ["Cannot update more than 25 employees at once."]},
                            },
                            "no_role": {
                                "summary": "Chưa chọn vai trò mới",
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

            # TODO: wrap in batch audit log.
            # Update roles and invalidate sessions in one operation
            updated_count = employees_to_update.update(role=new_role, active_session_key="")

        return Response(
            {
                "success": True,
                "message": _("Chỉnh sửa thành công"),
                "updated_count": updated_count,
            },
            status=status.HTTP_200_OK,
        )
