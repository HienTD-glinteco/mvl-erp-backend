from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.payroll.api.filtersets import DepartmentKPIAssessmentFilterSet
from apps.payroll.api.serializers import (
    DepartmentKPIAssessmentListSerializer,
    DepartmentKPIAssessmentSerializer,
    DepartmentKPIAssessmentUpdateSerializer,
)
from apps.payroll.models import DepartmentKPIAssessment
from libs import BaseModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter


@extend_schema_view(
    list=extend_schema(
        summary="List department KPI assessments",
        description="Retrieve a paginated list of department KPI assessments",
        tags=["8.4: Department KPI Assessments"],
        examples=[
            OpenApiExample(
                "Success - List of department assessments",
                value={
                    "success": True,
                    "data": {
                        "count": 1,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": 1,
                                "period": 1,
                                "department": 1,
                                "department_name": "Sales Department",
                                "department_code": "PB001",
                                "month": "2025-12-01",
                                "kpi_config_snapshot": {},
                                "grade": "B",
                                "finalized": False,
                                "created_at": "2025-12-01T00:00:00Z",
                                "updated_at": "2025-12-01T00:00:00Z",
                            }
                        ],
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get department KPI assessment details",
        description="Retrieve detailed information about a specific department KPI assessment",
        tags=["8.4: Department KPI Assessments"],
    ),
    partial_update=extend_schema(
        summary="Update department KPI assessment",
        description="Update grade or note for a department KPI assessment",
        tags=["8.4: Department KPI Assessments"],
        examples=[
            OpenApiExample(
                "Request - Update grade",
                value={"grade": "A", "note": "Excellent department performance"},
                request_only=True,
            ),
        ],
    ),
)
class DepartmentKPIAssessmentViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for DepartmentKPIAssessment model.

    Provides CRUD operations and custom actions for:
    - Generating department assessments
    - Auto-assigning grades to employees
    - Finalizing department assessments
    - Viewing assignment logs
    """

    queryset = DepartmentKPIAssessment.objects.select_related(
        "period",
        "department",
        "assigned_by",
        "created_by",
        "updated_by",
    )
    filterset_class = DepartmentKPIAssessmentFilterSet
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    search_fields = ["department__name", "department__code"]
    ordering_fields = ["period__month", "department__name", "grade", "created_at"]
    ordering = ["-period__month", "-created_at"]
    http_method_names = ["get", "patch"]  # Only allow GET and PATCH

    # Permission registration attributes
    module = "Payroll"
    submodule = "KPI Management"
    permission_prefix = "department_kpi_assessment"

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == "list":
            return DepartmentKPIAssessmentListSerializer
        elif self.action in ["partial_update"]:
            return DepartmentKPIAssessmentUpdateSerializer
        return DepartmentKPIAssessmentSerializer

    def perform_update(self, serializer):
        """Set updated_by and assigned info when updating."""
        serializer.save(
            updated_by=self.request.user,
            assigned_by=self.request.user,
            assigned_at=timezone.now(),
        )
