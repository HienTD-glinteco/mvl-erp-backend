from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.payroll.api.filtersets import EmployeeKPIAssessmentFilterSet
from apps.payroll.api.serializers import (
    EmployeeKPIAssessmentListSerializer,
    EmployeeKPIAssessmentSerializer,
    EmployeeKPIAssessmentUpdateSerializer,
)
from apps.payroll.models import EmployeeKPIAssessment
from libs import BaseModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter


@extend_schema_view(
    list=extend_schema(
        summary="List employee KPI assessments",
        description="Retrieve a paginated list of employee KPI assessments with support for filtering",
        tags=["10.3: Employee KPI Assessments"],
        examples=[
            OpenApiExample(
                "Success - List of assessments",
                value={
                    "success": True,
                    "data": {
                        "count": 1,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": 1,
                                "employee": 1,
                                "employee_username": "john.doe",
                                "employee_fullname": "John Doe",
                                "month": "2025-12-01",
                                "kpi_config_snapshot": {},
                                "total_possible_score": "100.00",
                                "total_manager_score": "80.00",
                                "grade_manager": "B",
                                "grade_manager_overridden": None,
                                "plan_tasks": "Complete Q4 targets",
                                "extra_tasks": "Handle urgent client requests",
                                "proposal": "Suggest new workflow improvement",
                                "grade_hrm": "A",
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
            )
        ],
    ),
    retrieve=extend_schema(
        summary="Get employee KPI assessment details",
        description="Retrieve detailed information about a specific employee KPI assessment including all items",
        tags=["10.3: Employee KPI Assessments"],
        examples=[
            OpenApiExample(
                "Success - Assessment with items",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "employee": 1,
                        "employee_username": "john.doe",
                        "employee_fullname": "John Doe",
                        "month": "2025-12-01",
                        "kpi_config_snapshot": {},
                        "total_possible_score": "100.00",
                        "total_manager_score": "80.00",
                        "grade_manager": "B",
                        "grade_manager_overridden": None,
                        "plan_tasks": "Complete Q4 targets",
                        "extra_tasks": "Handle urgent client requests",
                        "proposal": "Suggest new workflow improvement",
                        "grade_hrm": "A",
                        "finalized": False,
                        "department_assignment_source": None,
                        "created_by": 1,
                        "updated_by": None,
                        "created_at": "2025-12-01T00:00:00Z",
                        "updated_at": "2025-12-01T00:00:00Z",
                        "note": "",
                        "items": [
                            {
                                "id": 1,
                                "assessment": 1,
                                "criterion_id": 1,
                                "criterion": "Revenue Achievement",
                                "evaluation_type": "work_performance",
                                "description": "Monthly revenue target",
                                "component_total_score": "70.00",
                                "ordering": 1,
                                "employee_score": "90.00",
                                "manager_score": "85.00",
                                "note": "",
                                "created_at": "2025-12-01T00:00:00Z",
                                "updated_at": "2025-12-01T00:00:00Z",
                            }
                        ],
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            )
        ],
    ),
    partial_update=extend_schema(
        summary="Update employee KPI assessment",
        description="Update specific fields of an employee KPI assessment (HRM grade and note only)",
        tags=["10.3: Employee KPI Assessments"],
        examples=[
            OpenApiExample(
                "Request - Update HRM grade",
                value={"grade_hrm": "A", "note": "Exceptional performance this month"},
                request_only=True,
            )
        ],
    ),
)
class EmployeeKPIAssessmentViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for EmployeeKPIAssessment model.

    Provides CRUD operations and custom actions for:
    - Generating assessments
    - Updating item scores
    - Resyncing with current criteria
    - Finalizing assessments with unit control validation
    """

    queryset = EmployeeKPIAssessment.objects.select_related(
        "period",
        "employee",
        "department_assignment_source",
        "created_by",
        "updated_by",
    ).prefetch_related("items")
    filterset_class = EmployeeKPIAssessmentFilterSet
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    search_fields = ["employee__username", "employee__first_name", "employee__last_name"]
    ordering_fields = ["period__month", "employee__username", "grade_manager", "total_manager_score", "created_at"]
    ordering = ["-period__month", "-created_at"]
    http_method_names = ["get", "patch"]  # Only allow GET and PATCH

    # Permission registration attributes
    module = "Payroll"
    submodule = "KPI Management"
    permission_prefix = "employee_kpi_assessment"

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == "list":
            return EmployeeKPIAssessmentListSerializer
        elif self.action in ["partial_update"]:
            return EmployeeKPIAssessmentUpdateSerializer
        return EmployeeKPIAssessmentSerializer

    def perform_update(self, serializer):
        """Set updated_by when updating."""
        serializer.save(updated_by=self.request.user)
