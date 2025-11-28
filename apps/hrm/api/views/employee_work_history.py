from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets import EmployeeWorkHistoryFilterSet
from apps.hrm.api.serializers import EmployeeWorkHistorySerializer
from apps.hrm.models import EmployeeWorkHistory
from libs import BaseReadOnlyModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter


@extend_schema_view(
    list=extend_schema(
        summary="List employee work histories",
        description="Retrieve a paginated list of employee work histories with support for filtering and search",
        tags=["5.6 Employee Work History"],
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
        tags=["5.6 Employee Work History"],
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
)
class EmployeeWorkHistoryViewSet(AuditLoggingMixin, BaseReadOnlyModelViewSet):
    """
    ViewSet for EmployeeWorkHistory model (read-only).

    Provides read-only operations for employee work histories with:
    - List: Paginated list with filtering and search
    - Retrieve: Get detailed information

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
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    search_fields = ["name", "detail", "employee__code", "employee__fullname"]
    ordering_fields = ["date", "name", "created_at"]
    ordering = ["-date", "-created_at"]

    module = "HRM"
    submodule = "Employee Management"
    permission_prefix = "employee_work_history"
