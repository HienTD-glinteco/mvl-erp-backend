from datetime import date

from django.db import transaction
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.payroll.api.serializers import (
    KPIAssessmentPeriodFinalizeResponseSerializer,
    KPIAssessmentPeriodGenerateResponseSerializer,
    KPIAssessmentPeriodGenerateSerializer,
    KPIAssessmentPeriodListSerializer,
    KPIAssessmentPeriodSerializer,
)
from apps.payroll.models import (
    DepartmentKPIAssessment,
    EmployeeKPIAssessment,
    KPIAssessmentPeriod,
    KPIConfig,
)
from apps.payroll.utils import (
    generate_department_assessments_for_period,
    generate_employee_assessments_for_period,
    validate_unit_control,
)
from libs import BaseReadOnlyModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter


@extend_schema_view(
    list=extend_schema(
        summary="List KPI assessment periods",
        description="Retrieve a list of all KPI assessment periods with counts",
        tags=["8.6: KPI Assessment Periods"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "count": 2,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": 1,
                                "month": "2025-12",
                                "finalized": False,
                                "employee_count": 50,
                                "department_count": 10,
                                "note": "",
                                "created_at": "2025-11-20T10:00:00Z",
                                "updated_at": "2025-11-20T10:00:00Z",
                            }
                        ],
                    },
                    "error": None,
                },
                response_only=True,
            )
        ],
    ),
    retrieve=extend_schema(
        summary="Get KPI assessment period details",
        description="Retrieve details of a specific KPI assessment period",
        tags=["8.6: KPI Assessment Periods"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "month": "2025-12",
                        "kpi_config_snapshot": {
                            "name": "2025 KPI Config",
                            "grade_thresholds": [],
                            "unit_control": {},
                        },
                        "finalized": False,
                        "created_by": None,
                        "updated_by": None,
                        "note": "",
                        "created_at": "2025-11-20T10:00:00Z",
                        "updated_at": "2025-11-20T10:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            )
        ],
    ),
    destroy=extend_schema(
        summary="Delete KPI assessment period",
        description="Delete a KPI assessment period (use with caution)",
        tags=["8.6: KPI Assessment Periods"],
    ),
    generate=extend_schema(
        summary="Generate KPI assessments for a month",
        description="Generate employee and department KPI assessments for the specified month. Creates a new period if it doesn't exist.",
        tags=["8.6: KPI Assessment Periods"],
        request=KPIAssessmentPeriodGenerateSerializer,
        responses={
            201: KPIAssessmentPeriodGenerateResponseSerializer,
            400: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
        examples=[
            OpenApiExample(
                "Request",
                value={"month": "2025-12"},
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "message": "Assessment generation completed successfully",
                    "period_id": 1,
                    "month": "2025-12",
                    "employee_assessments_created": 50,
                    "department_assessments_created": 10,
                },
                response_only=True,
                status_codes=["201"],
            ),
            OpenApiExample(
                "Error - Period exists",
                value={
                    "detail": "Assessment period for 2025-12 already exists",
                },
                response_only=True,
                status_codes=["400"],
            ),
            OpenApiExample(
                "Error - Invalid month format",
                value={
                    "detail": "Invalid month format. Use YYYY-MM (e.g., 2025-12)",
                },
                response_only=True,
                status_codes=["400"],
            ),
            OpenApiExample(
                "Error - No KPI config",
                value={
                    "detail": "No KPI configuration found. Please create one first.",
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    finalize=extend_schema(
        summary="Finalize KPI assessment period",
        description="Finalize all assessments in this period. Sets grade_hrm='C' for unassessed employees and validates unit control for departments.",
        tags=["8.6: KPI Assessment Periods"],
        request=None,
        responses={
            200: KPIAssessmentPeriodFinalizeResponseSerializer,
            400: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
        examples=[
            OpenApiExample(
                "Success Response",
                value={
                    "message": "Period finalized successfully",
                    "employees_set_to_c": 5,
                    "departments_validated": 10,
                    "departments_invalid": 2,
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Error - Already finalized",
                value={
                    "detail": "Period is already finalized",
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
)
class KPIAssessmentPeriodViewSet(BaseReadOnlyModelViewSet):
    """ViewSet for KPIAssessmentPeriod model.

    Provides CRUD operations for KPI assessment periods.
    """

    queryset = KPIAssessmentPeriod.objects.all().order_by("-month")
    serializer_class = KPIAssessmentPeriodSerializer
    filter_backends = [PhraseSearchFilter]
    search_fields = ["note"]
    http_method_names = ["get", "post", "delete"]  # GET for list/retrieve, POST for actions, DELETE for destroy

    def get_serializer_class(self):
        """Return appropriate serializer class based on action."""
        if self.action == "list":
            return KPIAssessmentPeriodListSerializer
        return KPIAssessmentPeriodSerializer

    @action(detail=False, methods=["post"], url_path="generate")
    def generate(self, request):
        """Generate KPI assessments for a specific month."""
        month_str = request.data.get("month")
        if not month_str:
            return Response(
                {"detail": _("Month parameter is required")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Parse month
        try:
            year, month = map(int, month_str.split("-"))
            month_date = date(year, month, 1)
        except (ValueError, AttributeError):
            return Response(
                {"detail": _("Invalid month format. Use YYYY-MM (e.g., 2025-12)")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if period already exists
        if KPIAssessmentPeriod.objects.filter(month=month_date).exists():
            return Response(
                {"detail": _(f"Assessment period for {month_str} already exists")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get latest KPIConfig
        kpi_config = KPIConfig.objects.first()
        if not kpi_config:
            return Response(
                {"detail": _("No KPI configuration found. Please create one first.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create assessment period
        with transaction.atomic():
            period = KPIAssessmentPeriod.objects.create(
                month=month_date,
                kpi_config_snapshot=kpi_config.config,
                finalized=False,
                created_by=request.user,
            )

            # Generate employee assessments for all targets
            employee_count = generate_employee_assessments_for_period(period)

            # Generate department assessments
            department_count = generate_department_assessments_for_period(period)

        return Response(
            {
                "message": _("Assessment generation completed successfully"),
                "period_id": period.id,
                "month": period.month.strftime("%Y-%m"),
                "employee_assessments_created": employee_count,
                "department_assessments_created": department_count,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="finalize")
    def finalize(self, request, pk=None):
        """Finalize all assessments in this period."""
        period = self.get_object()

        if period.finalized:
            return Response(
                {"detail": _("Period is already finalized")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            # Process employee assessments
            employees_set_to_c = 0
            employee_assessments = EmployeeKPIAssessment.objects.filter(period=period)

            for assessment in employee_assessments:
                # If not assessed (no scores), set grade_hrm = 'C'
                if (
                    assessment.total_employee_score is None
                    and assessment.total_manager_score is None
                    and not assessment.grade_hrm
                ):
                    assessment.grade_hrm = "C"
                    employees_set_to_c += 1

                # Finalize the assessment
                assessment.finalized = True
                assessment.save()

            # Process department assessments
            departments_validated = 0
            departments_invalid = 0
            department_assessments = DepartmentKPIAssessment.objects.filter(period=period).select_related("department")

            unit_control = period.kpi_config_snapshot.get("unit_control", {})

            for dept_assessment in department_assessments:
                # Get all employee assessments in this department for this period
                dept_employees = employee_assessments.filter(employee__department=dept_assessment.department)

                # Count grades
                grade_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
                for emp_assessment in dept_employees:
                    grade = emp_assessment.grade_hrm or emp_assessment.grade_manager
                    if grade in grade_counts:
                        grade_counts[grade] += 1

                # Validate unit control
                total_employees = dept_employees.count()
                is_valid, violations = validate_unit_control(
                    dept_assessment.grade,
                    grade_counts,
                    total_employees,
                    unit_control,
                )

                dept_assessment.is_valid_unit_control = is_valid
                dept_assessment.finalized = True
                dept_assessment.save()

                if is_valid:
                    departments_validated += 1
                else:
                    departments_invalid += 1

            # Finalize the period
            period.finalized = True
            period.updated_by = request.user
            period.save()

        return Response(
            {
                "message": _("Period finalized successfully"),
                "employees_set_to_c": employees_set_to_c,
                "departments_validated": departments_validated,
                "departments_invalid": departments_invalid,
            },
            status=status.HTTP_200_OK,
        )
