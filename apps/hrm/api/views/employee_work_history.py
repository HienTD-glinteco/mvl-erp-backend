from django.utils import timezone
from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.core.api.permissions import DataScopePermission, RoleBasedPermission
from apps.hrm.api.filtersets import EmployeeWorkHistoryFilterSet
from apps.hrm.api.serializers import EmployeeWorkHistorySerializer
from apps.hrm.models import EmployeeWorkHistory
from apps.hrm.utils.filters import RoleDataScopeFilterBackend
from libs import BaseModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter


@extend_schema_view(
    list=extend_schema(
        summary="List employee work histories",
        description="Retrieve a paginated list of employee work histories with support for filtering and search",
        tags=["5.6: Employee Work History"],
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
                                "code": "EWH001",
                                "date": "2024-01-15",
                                "name": "Promotion to Senior Developer",
                                "detail": "Promoted due to excellent performance",
                                "employee": {"id": 1, "code": "MV001", "fullname": "John Doe"},
                                "branch": {"id": 1, "code": "CN001", "name": "Main Branch"},
                                "block": {"id": 1, "code": "KH001", "name": "Main Block"},
                                "department": {"id": 1, "code": "PB001", "name": "Engineering Department"},
                                "position": {"id": 1, "code": "CV001", "name": "Senior Developer"},
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
    retrieve=extend_schema(
        summary="Retrieve employee work history",
        description="Get detailed information about a specific employee work history record",
        tags=["5.6: Employee Work History"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "EWH001",
                        "date": "2024-01-15",
                        "name": "Promotion to Senior Developer",
                        "detail": "Promoted due to excellent performance",
                        "employee": {"id": 1, "code": "MV001", "fullname": "John Doe"},
                        "branch": {"id": 1, "code": "CN001", "name": "Main Branch"},
                        "block": {"id": 1, "code": "KH001", "name": "Main Block"},
                        "department": {"id": 1, "code": "PB001", "name": "Engineering Department"},
                        "position": {"id": 1, "code": "CV001", "name": "Senior Developer"},
                        "created_at": "2025-10-31T05:00:00Z",
                        "updated_at": "2025-10-31T05:00:00Z",
                    },
                },
                response_only=True,
            )
        ],
    ),
    update=extend_schema(
        tags=["5.6: Employee Work History"],
    ),
    create=extend_schema(exclude=True),
    partial_update=extend_schema(
        tags=["5.6: Employee Work History"],
    ),
    destroy=extend_schema(
        tags=["5.6: Employee Work History"],
    ),
)
class EmployeeWorkHistoryViewSet(AuditLoggingMixin, BaseModelViewSet):
    """
    ViewSet for EmployeeWorkHistory model.

    Note: This ViewSet is read-only. Create, update, and delete operations are not available.

    Filtering:
        - employee: Filter by employee ID
        - branch: Filter by branch ID
        - block: Filter by block ID
        - department: Filter by department ID
        - position: Filter by position ID
        - date_from: Filter by date (greater than or equal)
        - date_to: Filter by date (less than or equal)
        - search: Search across employee code, employee name, event name, and details

    Ordering:
        - Default: -date (most recent first)
        - Available fields: date, name, created_at
    """

    queryset = EmployeeWorkHistory.objects.select_related(
        "employee", "branch", "block", "department", "position"
    ).all()
    serializer_class = EmployeeWorkHistorySerializer
    filterset_class = EmployeeWorkHistoryFilterSet
    filter_backends = [RoleDataScopeFilterBackend, DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    search_fields = ["name", "detail", "employee__code", "employee__fullname"]
    ordering_fields = ["date", "name", "created_at"]
    ordering = ["-date", "-created_at"]
    permission_classes = [RoleBasedPermission, DataScopePermission]

    # Data scope configuration for role-based filtering
    data_scope_config = {
        "branch_field": "employee__branch",
        "block_field": "employee__block",
        "department_field": "employee__department",
    }

    module = _("HRM")
    submodule = _("Employee Management")
    permission_prefix = "employee_work_history"

    def create(self, request, *args, **kwargs):
        raise NotFound("This endpoint does not support creation of employee work history records.")

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        latest_record = EmployeeWorkHistory.objects.filter(employee=instance.employee).only("id").first()
        if latest_record and instance.id != latest_record.id:
            return Response(
                "Only the latest employee work history record can be deleted.", status=status.HTTP_400_BAD_REQUEST
            )

        # Check deletion restriction for Employee Type change records
        if instance.name == EmployeeWorkHistory.EventType.CHANGE_EMPLOYEE_TYPE:
            today = timezone.localdate()
            start_of_month = today.replace(day=1)
            if instance.date < start_of_month:
                return Response(
                    _("Cannot delete employee type change record with effective date in previous months."),
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return super().destroy(request, *args, **kwargs)
