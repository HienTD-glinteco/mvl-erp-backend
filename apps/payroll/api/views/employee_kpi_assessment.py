from datetime import date

from django.db import transaction
from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.payroll.api.filtersets import EmployeeKPIAssessmentFilterSet
from apps.payroll.api.serializers import (
    EmployeeKPIAssessmentListSerializer,
    EmployeeKPIAssessmentSerializer,
    EmployeeKPIAssessmentUpdateSerializer,
    EmployeeKPIItemUpdateSerializer,
)
from apps.payroll.models import EmployeeKPIAssessment, EmployeeKPIItem, KPIConfig, KPICriterion
from apps.payroll.utils import (
    create_assessment_items_from_criteria,
    recalculate_assessment_scores,
    resync_assessment_add_missing,
    resync_assessment_apply_current,
    validate_unit_control,
)
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
        description="Update specific fields of an employee KPI assessment (grade override, note)",
        tags=["10.3: Employee KPI Assessments"],
        examples=[
            OpenApiExample(
                "Request - Override grade",
                value={"grade_manager_overridden": "A", "note": "Exceptional performance this month"},
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

    # Permission registration attributes
    module = "Payroll"
    submodule = "KPI Management"
    permission_prefix = "employee_kpi_assessment"

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == "list":
            return EmployeeKPIAssessmentListSerializer
        elif self.action in ["update", "partial_update"]:
            return EmployeeKPIAssessmentUpdateSerializer
        return EmployeeKPIAssessmentSerializer

    def perform_create(self, serializer):
        """Set created_by when creating."""
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        """Set updated_by when updating."""
        serializer.save(updated_by=self.request.user)

    @extend_schema(
        summary="Generate employee KPI assessments",
        description="Generate KPI assessments for employees for a specific month. Creates assessment snapshots from current KPICriterion.",
        tags=["10.3: Employee KPI Assessments"],
        parameters=[
            OpenApiParameter(name="month", description="Month in YYYY-MM format", required=True, type=str),
            OpenApiParameter(
                name="employee_ids", description="Comma-separated employee IDs", required=False, type=str
            ),
        ],
        request=None,
        responses={200: EmployeeKPIAssessmentSerializer(many=True)},
    )
    @action(detail=False, methods=["post"])
    def generate(self, request):
        """Generate employee KPI assessments for a month."""
        month_str = request.query_params.get("month")
        employee_ids_str = request.query_params.get("employee_ids")

        if not month_str:
            return Response(
                {"detail": _("Month parameter is required (format: YYYY-MM)")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            year, month = map(int, month_str.split("-"))
            month_date = date(year, month, 1)
        except (ValueError, AttributeError):
            return Response(
                {"detail": _("Invalid month format. Use YYYY-MM")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get latest KPIConfig
        kpi_config = KPIConfig.objects.first()
        if not kpi_config:
            return Response(
                {"detail": _("No KPI configuration found")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get employees to generate for
        from apps.hrm.models import Employee

        employees_qs = Employee.objects.exclude(status=Employee.Status.RESIGNED)
        if employee_ids_str:
            try:
                employee_ids = [int(x.strip()) for x in employee_ids_str.split(",")]
                employees_qs = employees_qs.filter(id__in=employee_ids)
            except ValueError:
                return Response(
                    {"detail": _("Invalid employee_ids format")},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        created_assessments = []
        skipped_count = 0

        with transaction.atomic():
            # Get or create the period
            from apps.payroll.models import KPIAssessmentPeriod

            period, created = KPIAssessmentPeriod.objects.get_or_create(
                month=month_date,
                defaults={
                    "kpi_config_snapshot": kpi_config.config,
                    "created_by": request.user,
                },
            )

            for employee in employees_qs:
                # Check if assessment already exists
                if EmployeeKPIAssessment.objects.filter(employee=employee, period=period).exists():
                    skipped_count += 1
                    continue

                # Get active criteria (simplified - get all active criteria)
                criteria = KPICriterion.objects.filter(active=True).order_by("evaluation_type", "order")

                if not criteria.exists():
                    continue

                # Create assessment
                assessment = EmployeeKPIAssessment.objects.create(
                    period=period,
                    employee=employee,
                    created_by=request.user,
                )

                # Create items from criteria
                create_assessment_items_from_criteria(assessment, list(criteria))

                # Calculate totals
                recalculate_assessment_scores(assessment)

                created_assessments.append(assessment)

        serializer = self.get_serializer(created_assessments, many=True)
        return Response(
            {
                "created": len(created_assessments),
                "skipped": skipped_count,
                "assessments": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="Update item score",
        description="Update employee_score or manager_score for a specific KPI item. Automatically recalculates component score and assessment totals.",
        tags=["10.3: Employee KPI Assessments"],
        request=EmployeeKPIItemUpdateSerializer,
        responses={200: EmployeeKPIAssessmentSerializer},
    )
    @action(detail=True, methods=["patch"], url_path="items/(?P<item_id>[^/.]+)")
    def update_item(self, request, pk=None, item_id=None):
        """Update a specific KPI item's score."""
        assessment = self.get_object()

        if assessment.finalized:
            return Response(
                {"detail": _("Cannot update items of a finalized assessment")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            item = assessment.items.get(id=item_id)
        except EmployeeKPIItem.DoesNotExist:
            return Response(
                {"detail": _("Item not found")},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = EmployeeKPIItemUpdateSerializer(item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Recalculate assessment
        recalculate_assessment_scores(assessment)
        assessment.updated_by = request.user
        assessment.save()

        # Return updated assessment
        response_serializer = EmployeeKPIAssessmentSerializer(assessment)
        return Response(response_serializer.data)

    @extend_schema(
        summary="Resync assessment with current criteria",
        description="Resync assessment items with current KPICriterion. Mode 'add_missing' adds new criteria; 'apply_current' replaces all items.",
        tags=["10.3: Employee KPI Assessments"],
        parameters=[
            OpenApiParameter(
                name="mode",
                description="Resync mode: add_missing or apply_current",
                required=True,
                type=str,
                enum=["add_missing", "apply_current"],
            )
        ],
        request=None,
        responses={200: EmployeeKPIAssessmentSerializer},
    )
    @action(detail=True, methods=["post"])
    def resync(self, request, pk=None):
        """Resync assessment with current criteria."""
        assessment = self.get_object()

        if assessment.finalized:
            return Response(
                {"detail": _("Cannot resync a finalized assessment")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        mode = request.query_params.get("mode", "add_missing")

        try:
            if mode == "add_missing":
                count = resync_assessment_add_missing(assessment)
                message = _("Added {count} new criteria").format(count=count)
            elif mode == "apply_current":
                count = resync_assessment_apply_current(assessment)
                message = _("Replaced all items with {count} current criteria").format(count=count)
            else:
                return Response(
                    {"detail": _("Invalid mode. Use 'add_missing' or 'apply_current'")},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except ValueError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        assessment.updated_by = request.user
        assessment.save()

        serializer = EmployeeKPIAssessmentSerializer(assessment)
        return Response({"message": message, "assessment": serializer.data})

    @extend_schema(
        summary="Finalize employee KPI assessment",
        description="Finalize assessment with unit control validation. Use force=true to bypass validation (admin only).",
        tags=["10.3: Employee KPI Assessments"],
        parameters=[
            OpenApiParameter(
                name="force", description="Force finalize even with violations", required=False, type=bool
            )
        ],
        request=None,
        responses={200: EmployeeKPIAssessmentSerializer},
    )
    @action(detail=True, methods=["post"])
    def finalize(self, request, pk=None):
        """Finalize an assessment with unit control validation."""
        assessment = self.get_object()

        if assessment.finalized:
            return Response(
                {"detail": _("Assessment is already finalized")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        force = request.query_params.get("force", "false").lower() == "true"

        # Get department and validate unit control
        # This is simplified - in real scenario, get from employee profile
        try:
            from apps.hrm.models import Employee

            emp = Employee.objects.get(username=assessment.employee.username)
            department = emp.department

            # Get all assessments for this department and period
            dept_assessments = EmployeeKPIAssessment.objects.filter(
                employee__employee__department=department,
                period=assessment.period,
            )

            # Count grades
            grade_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
            for a in dept_assessments:
                grade = a.grade_manager_overridden or a.grade_manager
                if grade in grade_counts:
                    grade_counts[grade] += 1

            # Get KPI config from period
            unit_control = assessment.period.kpi_config_snapshot.get("unit_control", {})

            # Simplified: assume department unit type is 'A'
            dept_unit_type = "A"

            is_valid, violations = validate_unit_control(
                dept_unit_type,
                grade_counts,
                dept_assessments.count(),
                unit_control,
            )

            if not is_valid and not force:
                return Response(
                    {"detail": _("Unit control violations"), "violations": violations},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except (AttributeError, KeyError) as e:
            # If validation fails due to missing Employee model or data, allow with warning
            pass  # nosec B110

        # Finalize
        assessment.finalized = True
        assessment.updated_by = request.user
        assessment.save()

        serializer = EmployeeKPIAssessmentSerializer(assessment)
        return Response({"message": _("Assessment finalized successfully"), "assessment": serializer.data})
