from datetime import date

from django.db import transaction
from django.db.models import Count, Q
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.payroll.api.serializers import (
    KPIAssessmentPeriodFinalizeResponseSerializer,
    KPIAssessmentPeriodGenerateSerializer,
    KPIAssessmentPeriodSerializer,
    KPIAssessmentPeriodSummarySerializer,
)
from apps.payroll.models import (
    DepartmentKPIAssessment,
    EmployeeKPIAssessment,
    KPIAssessmentPeriod,
    KPIConfig,
)
from apps.payroll.utils import update_department_assessment_status
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
                                "month": "12/2025",
                                "kpi_config_snapshot": {
                                    "name": "2025 KPI Configuration",
                                    "description": "Standard KPI grading configuration for 2025",
                                    "ambiguous_assignment": "auto_prefer_default",
                                    "grade_thresholds": [
                                        {
                                            "min": 90.0,
                                            "max": 100.0,
                                            "possible_codes": ["A"],
                                            "label": "Excellent",
                                            "default_code": "A",
                                        },
                                        {
                                            "min": 75.0,
                                            "max": 90.0,
                                            "possible_codes": ["B"],
                                            "label": "Good",
                                            "default_code": "B",
                                        },
                                        {
                                            "min": 50.0,
                                            "max": 75.0,
                                            "possible_codes": ["C"],
                                            "label": "Average",
                                            "default_code": "C",
                                        },
                                        {
                                            "min": 0.0,
                                            "max": 50.0,
                                            "possible_codes": ["D"],
                                            "label": "Below Average",
                                            "default_code": "D",
                                        },
                                    ],
                                    "unit_control": {
                                        "department": {
                                            "A": {"min": 0.0, "max": 0.3, "target": 0.2},
                                            "B": {"min": 0.2, "max": 0.5, "target": 0.4},
                                            "C": {"min": 0.2, "max": 0.6, "target": 0.3},
                                            "D": {"min": 0.0, "max": 0.2, "target": 0.1},
                                        }
                                    },
                                    "meta": {},
                                },
                                "finalized": False,
                                "employee_count": 50,
                                "department_count": 10,
                                "employee_self_assessed_count": 35,
                                "manager_assessed_count": 30,
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
                        "month": "12/2025",
                        "kpi_config_snapshot": {
                            "name": "2025 KPI Configuration",
                            "description": "Standard KPI grading configuration for 2025",
                            "ambiguous_assignment": "auto_prefer_default",
                            "grade_thresholds": [
                                {
                                    "min": 90.0,
                                    "max": 100.0,
                                    "possible_codes": ["A"],
                                    "label": "Excellent",
                                    "default_code": "A",
                                },
                                {
                                    "min": 75.0,
                                    "max": 90.0,
                                    "possible_codes": ["B"],
                                    "label": "Good",
                                    "default_code": "B",
                                },
                                {
                                    "min": 50.0,
                                    "max": 75.0,
                                    "possible_codes": ["C"],
                                    "label": "Average",
                                    "default_code": "C",
                                },
                                {
                                    "min": 0.0,
                                    "max": 50.0,
                                    "possible_codes": ["D"],
                                    "label": "Below Average",
                                    "default_code": "D",
                                },
                            ],
                            "unit_control": {
                                "department": {
                                    "A": {"min": 0.0, "max": 0.3, "target": 0.2},
                                    "B": {"min": 0.2, "max": 0.5, "target": 0.4},
                                    "C": {"min": 0.2, "max": 0.6, "target": 0.3},
                                    "D": {"min": 0.0, "max": 0.2, "target": 0.1},
                                }
                            },
                            "meta": {},
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
        summary="Generate KPI assessments for a month (async)",
        description=(
            "Generate employee and department KPI assessments for the specified month asynchronously. "
            "Creates a new period if it doesn't exist. Only allows creating periods for current or past months.\n\n"
            "Returns a task_id that can be used to check the generation progress via the task-status endpoint."
        ),
        tags=["8.6: KPI Assessment Periods"],
        request=KPIAssessmentPeriodGenerateSerializer,
        responses={
            202: {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "status": {"type": "string"},
                    "message": {"type": "string"},
                },
            },
            400: {"type": "object", "properties": {"detail": {"type": "string"}}},
        },
        examples=[
            OpenApiExample(
                "Request",
                value={"month": "2025-12"},
                request_only=True,
            ),
            OpenApiExample(
                "Success - Task Created",
                value={
                    "task_id": "abc123-def456-ghi789",
                    "status": "Task created",
                    "message": "KPI assessment period generation started. Use task_status endpoint to check progress.",
                },
                response_only=True,
                status_codes=["202"],
            ),
            OpenApiExample(
                "Error - Future month",
                value={
                    "detail": "Cannot create assessment period for future months",
                },
                response_only=True,
                status_codes=["400"],
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
    summary=extend_schema(
        summary="Get assessment summary statistics",
        description="Get summary statistics for a period including finished/unfinished departments and unit control validation status",
        tags=["8.6: KPI Assessment Periods"],
        request=None,
        responses={
            200: KPIAssessmentPeriodSummarySerializer,
        },
        examples=[
            OpenApiExample(
                "Success Response",
                value={
                    "success": True,
                    "data": {
                        "total_departments": 10,
                        "departments_finished": 7,
                        "departments_not_finished": 3,
                        "departments_not_valid_control": 2,
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    ),
)
class KPIAssessmentPeriodViewSet(BaseReadOnlyModelViewSet):
    """ViewSet for KPIAssessmentPeriod model.

    Provides CRUD operations for KPI assessment periods.
    """

    module = "Payroll"
    submodule = "KPI Period Management"
    permission_prefix = "kpi_assessment_period"
    operation = "KPI-Assessment-Period"

    queryset = KPIAssessmentPeriod.objects.all().order_by("-month")
    serializer_class = KPIAssessmentPeriodSerializer
    filter_backends = [PhraseSearchFilter]
    search_fields = ["note"]
    http_method_names = ["get", "post", "delete"]  # GET for list/retrieve, POST for actions, DELETE for destroy
    PERMISSION_REGISTERED_ACTIONS = {
        "generate": {
            "name_template": _("Generate KPI assessments"),
            "description_template": _("Generate employee and department KPI assessments for a specified month"),
        },
        "finalize": {
            "name_template": _("Finalize KPI assessments"),
            "description_template": _("Finalize all assessments in the specified period"),
        },
        "summary": {
            "name_template": _("Get summary statistics for KPI assessments"),
            "description_template": _("Get summary statistics for the specified assessment period"),
        },
    }

    def get_queryset(self):
        """Optimize queryset with annotations."""
        queryset = super().get_queryset()

        queryset = queryset.annotate(
            employee_assessments_count=Count("employee_assessments", distinct=True),
            department_assessments_count=Count("department_assessments", distinct=True),
            employee_self_evaluated_count=Count(
                "employee_assessments",
                filter=Q(employee_assessments__total_employee_score__isnull=False),
                distinct=True,
            ),
            manager_evaluated_count=Count(
                "employee_assessments",
                filter=Q(employee_assessments__total_manager_score__isnull=False)
                | Q(employee_assessments__grade_manager__isnull=False),
                distinct=True,
            ),
        )

        return queryset

    def get_serializer_class(self):
        """Return appropriate serializer class based on action."""
        return KPIAssessmentPeriodSerializer

    @action(detail=False, methods=["post"], url_path="generate")
    def generate(self, request):
        """Generate KPI assessments for a specific month asynchronously."""
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

        # Check if month is in the future
        today = date.today()
        current_month_start = date(today.year, today.month, 1)
        if month_date > current_month_start:
            return Response(
                {"detail": _("Cannot create assessment period for future months")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if period already exists
        if KPIAssessmentPeriod.objects.filter(month=month_date).exists():
            return Response(
                {"detail": _("Assessment period for {month_str} already exists").format(month_str=month_str)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get latest KPIConfig
        kpi_config = KPIConfig.objects.first()
        if not kpi_config:
            return Response(
                {"detail": _("No KPI configuration found. Please create one first.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Launch async task
        from apps.payroll.tasks import generate_kpi_period_task

        task = generate_kpi_period_task.delay(month_str)

        return Response(
            {
                "task_id": task.id,
                "status": "Task created",
                "message": "KPI assessment period generation started. Use task_status endpoint to check progress.",
            },
            status=status.HTTP_202_ACCEPTED,
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
            # Process employee assessments - set default grade for ungraded employees
            employees_set_to_c = 0
            employee_assessments = EmployeeKPIAssessment.objects.filter(period=period)

            # First pass: set default grades without triggering signals
            employees_to_update = []
            for assessment in employee_assessments:
                # If not assessed (no scores), set grade_hrm = 'C'
                if (
                    assessment.total_employee_score is None
                    and assessment.total_manager_score is None
                    and not assessment.grade_hrm
                    and not assessment.grade_manager
                ):
                    assessment.grade_hrm = "C"
                    employees_set_to_c += 1
                    employees_to_update.append(assessment)

            # Bulk update to avoid triggering signal for each save
            if employees_to_update:
                EmployeeKPIAssessment.objects.bulk_update(employees_to_update, ["grade_hrm"], batch_size=100)

            # Second pass: finalize all employee assessments
            for assessment in employee_assessments:
                assessment.finalized = True

            EmployeeKPIAssessment.objects.bulk_update(employee_assessments, ["finalized"], batch_size=100)

            # Process department assessments - update all department statuses
            departments_validated = 0
            departments_invalid = 0
            department_assessments = DepartmentKPIAssessment.objects.filter(period=period)

            for dept_assessment in department_assessments:
                # Update department status (is_finished and is_valid_unit_control)
                # This will check all employees in the department and validate unit control
                update_department_assessment_status(dept_assessment)

                # Refresh from db to get updated values
                dept_assessment.refresh_from_db()

                # Finalize the department assessment
                dept_assessment.finalized = True
                dept_assessment.save(update_fields=["finalized"])

                if dept_assessment.is_valid_unit_control:
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

    @action(detail=True, methods=["get"], url_path="summary")
    def summary(self, request, pk=None):
        """Get summary statistics for the assessment period."""
        period = self.get_object()

        # Get all department assessments for this period
        department_assessments = DepartmentKPIAssessment.objects.filter(period=period)

        total_departments = department_assessments.count()

        # Count departments with at least one employee assessed by manager
        departments_with_manager_assessment = set()
        departments_without_manager_assessment = set()

        for dept_assessment in department_assessments:
            # Check if at least one employee in this department has grade_manager
            has_manager_grade = EmployeeKPIAssessment.objects.filter(
                period=period,
                department_snapshot=dept_assessment.department,
                grade_manager__isnull=False,
            ).exists()

            if has_manager_grade:
                departments_with_manager_assessment.add(dept_assessment.id)
            else:
                departments_without_manager_assessment.add(dept_assessment.id)

        departments_finished = len(departments_with_manager_assessment)
        departments_not_finished = len(departments_without_manager_assessment)
        departments_not_valid_control = department_assessments.filter(is_valid_unit_control=False).count()

        return Response(
            {
                "total_departments": total_departments,
                "departments_finished": departments_finished,
                "departments_not_finished": departments_not_finished,
                "departments_not_valid_control": departments_not_valid_control,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Check KPI generation task status",
        description=(
            "Check the status of a KPI assessment period generation task.\n\n"
            "Task states:\n"
            "- PENDING: Task is waiting to be executed\n"
            "- PROGRESS: Task is currently running\n"
            "- SUCCESS: Task completed successfully (result contains period details)\n"
            "- FAILURE: Task failed (error contains error message)"
        ),
        tags=["8.6: KPI Assessment Periods"],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "state": {"type": "string", "enum": ["PENDING", "PROGRESS", "SUCCESS", "FAILURE"]},
                    "status": {"type": "string"},
                    "result": {"type": "object"},
                    "meta": {"type": "object"},
                    "error": {"type": "string"},
                },
            },
        },
        examples=[
            OpenApiExample(
                "Success - Task Completed",
                value={
                    "task_id": "abc123-def456",
                    "state": "SUCCESS",
                    "status": "Task completed successfully",
                    "result": {
                        "period_id": 42,
                        "month": "2025-12",
                        "employee_assessments_created": 150,
                        "department_assessments_created": 10,
                        "status": "completed",
                    },
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Progress - Task Running",
                value={
                    "task_id": "abc123-def456",
                    "state": "PROGRESS",
                    "status": "Task is in progress",
                    "meta": {"status": "Generating employee assessments"},
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Pending - Task Queued",
                value={
                    "task_id": "abc123-def456",
                    "state": "PENDING",
                    "status": "Task is waiting to be executed",
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Failure - Task Failed",
                value={
                    "task_id": "abc123-def456",
                    "state": "FAILURE",
                    "status": "Task failed",
                    "error": "No KPI configuration found. Please create one first.",
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    )
    @action(detail=False, methods=["get"], url_path="task-status/(?P<task_id>[^/.]+)")
    def task_status(self, request, task_id=None):
        """Check status of a Celery task."""
        from celery.result import AsyncResult

        task = AsyncResult(task_id)

        response_data = {
            "task_id": task_id,
            "state": task.state,
        }

        if task.state == "PENDING":
            response_data["status"] = "Task is waiting to be executed"
        elif task.state == "PROGRESS":
            response_data["status"] = "Task is in progress"
            response_data["meta"] = task.info
        elif task.state == "SUCCESS":
            response_data["status"] = "Task completed successfully"
            response_data["result"] = task.result
        elif task.state == "FAILURE":
            response_data["status"] = "Task failed"
            response_data["error"] = str(task.info)

        return Response(response_data)


@extend_schema_view(
    list=extend_schema(
        summary="List KPI assessment periods for manager",
        description="Retrieve a list of KPI assessment periods with counts for current manager's employees only",
        tags=["8.8: Manager Periods"],
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
                                "month": "12/2025",
                                "kpi_config_snapshot": {
                                    "name": "2025 KPI Configuration",
                                    "description": "Standard KPI grading configuration for 2025",
                                    "ambiguous_assignment": "auto_prefer_default",
                                    "grade_thresholds": [
                                        {
                                            "min": 90.0,
                                            "max": 100.0,
                                            "possible_codes": ["A"],
                                            "label": "Excellent",
                                            "default_code": "A",
                                        },
                                        {
                                            "min": 75.0,
                                            "max": 90.0,
                                            "possible_codes": ["B"],
                                            "label": "Good",
                                            "default_code": "B",
                                        },
                                        {
                                            "min": 50.0,
                                            "max": 75.0,
                                            "possible_codes": ["C"],
                                            "label": "Average",
                                            "default_code": "C",
                                        },
                                        {
                                            "min": 0.0,
                                            "max": 50.0,
                                            "possible_codes": ["D"],
                                            "label": "Below Average",
                                            "default_code": "D",
                                        },
                                    ],
                                    "unit_control": {
                                        "department": {
                                            "A": {"min": 0.0, "max": 0.3, "target": 0.2},
                                            "B": {"min": 0.2, "max": 0.5, "target": 0.4},
                                            "C": {"min": 0.2, "max": 0.6, "target": 0.3},
                                            "D": {"min": 0.0, "max": 0.2, "target": 0.1},
                                        }
                                    },
                                    "meta": {},
                                },
                                "finalized": False,
                                "employee_count": 10,
                                "department_count": 2,
                                "employee_self_assessed_count": 8,
                                "manager_assessed_count": 6,
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
        summary="Get KPI assessment period details for manager",
        description="Retrieve details of a specific KPI assessment period with counts for current manager's employees",
        tags=["8.8: Manager Periods"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "month": "12/2025",
                        "kpi_config_snapshot": {
                            "name": "2025 KPI Configuration",
                            "description": "Standard KPI grading configuration for 2025",
                            "ambiguous_assignment": "auto_prefer_default",
                            "grade_thresholds": [
                                {
                                    "min": 90.0,
                                    "max": 100.0,
                                    "possible_codes": ["A"],
                                    "label": "Excellent",
                                    "default_code": "A",
                                },
                                {
                                    "min": 75.0,
                                    "max": 90.0,
                                    "possible_codes": ["B"],
                                    "label": "Good",
                                    "default_code": "B",
                                },
                                {
                                    "min": 50.0,
                                    "max": 75.0,
                                    "possible_codes": ["C"],
                                    "label": "Average",
                                    "default_code": "C",
                                },
                                {
                                    "min": 0.0,
                                    "max": 50.0,
                                    "possible_codes": ["D"],
                                    "label": "Below Average",
                                    "default_code": "D",
                                },
                            ],
                            "unit_control": {
                                "department": {
                                    "A": {"min": 0.0, "max": 0.3, "target": 0.2},
                                    "B": {"min": 0.2, "max": 0.5, "target": 0.4},
                                    "C": {"min": 0.2, "max": 0.6, "target": 0.3},
                                    "D": {"min": 0.0, "max": 0.2, "target": 0.1},
                                }
                            },
                            "meta": {},
                        },
                        "finalized": False,
                        "employee_count": 10,
                        "department_count": 2,
                        "employee_self_assessed_count": 8,
                        "manager_assessed_count": 6,
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
)
class KPIAssessmentPeriodManagerViewSet(BaseReadOnlyModelViewSet):
    """ViewSet for KPIAssessmentPeriod model - manager view.

    Provides read-only operations for KPI assessment periods filtered for current manager.
    """

    module = "Payroll"
    submodule = "KPI Period Management"
    permission_prefix = "kpi_assessment_period_manager"
    operation = "KPI-Assessment-Period-Manager"

    queryset = KPIAssessmentPeriod.objects.all().order_by("-month")
    serializer_class = KPIAssessmentPeriodSerializer
    filter_backends = [PhraseSearchFilter]
    search_fields = ["note"]
    http_method_names = ["get"]

    def get_queryset(self):
        """Filter queryset with annotations for current manager."""
        queryset = super().get_queryset()
        current_user = self.request.user

        if not hasattr(current_user, "employee"):
            return queryset.none()

        current_employee = current_user.employee

        queryset = queryset.annotate(
            employee_assessments_count=Count(
                "employee_assessments",
                filter=Q(employee_assessments__manager=current_employee),
                distinct=True,
            ),
            department_assessments_count=Count(
                "employee_assessments__employee__department",
                filter=Q(employee_assessments__manager=current_employee),
                distinct=True,
            ),
            employee_self_evaluated_count=Count(
                "employee_assessments",
                filter=Q(employee_assessments__manager=current_employee)
                & Q(employee_assessments__total_employee_score__isnull=False),
                distinct=True,
            ),
            manager_evaluated_count=Count(
                "employee_assessments",
                filter=Q(employee_assessments__manager=current_employee)
                & (
                    Q(employee_assessments__total_manager_score__isnull=False)
                    | Q(employee_assessments__grade_manager__isnull=False)
                ),
                distinct=True,
            ),
        )

        return queryset
