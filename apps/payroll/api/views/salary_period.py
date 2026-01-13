"""ViewSet for SalaryPeriod model."""

from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.core.api.permissions import DataScopePermission, RoleBasedPermission
from apps.hrm.utils.filters import RoleDataScopeFilterBackend
from apps.payroll.api.filtersets import PayrollSlipFilterSet, SalaryPeriodFilterSet
from apps.payroll.api.serializers import (
    PayrollSlipSerializer,
    SalaryPeriodCreateAsyncSerializer,
    SalaryPeriodCreateResponseSerializer,
    SalaryPeriodListSerializer,
    SalaryPeriodRecalculateResponseSerializer,
    SalaryPeriodSerializer,
    SalaryPeriodUpdateDeadlinesSerializer,
    TaskStatusSerializer,
)
from apps.payroll.models import PayrollSlip, SalaryPeriod
from libs import BaseModelViewSet, BaseReadOnlyModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter
from libs.drf.pagination import PageNumberWithSizePagination


@extend_schema_view(
    list=extend_schema(
        summary="List all salary periods",
        description="Retrieve a paginated list of salary periods with filtering and ordering support",
        tags=["10.6: Salary Periods"],
        examples=[
            OpenApiExample(
                "Success - List of salary periods",
                value={
                    "success": True,
                    "data": {
                        "count": 2,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": 1,
                                "code": "SP-202401",
                                "month": "2024-01-01",
                                "status": "ONGOING",
                                "standard_working_days": "23.00",
                                "total_employees": 50,
                                "pending_count": 5,
                                "ready_count": 40,
                                "hold_count": 3,
                                "delivered_count": 2,
                                "created_at": "2024-01-01T00:00:00Z",
                                "updated_at": "2024-01-15T10:00:00Z",
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
        summary="Get salary period details",
        description="Retrieve detailed information about a specific salary period including config snapshot and statistics",
        tags=["10.6: Salary Periods"],
        examples=[
            OpenApiExample(
                "Success - Single salary period",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "SP-202401",
                        "month": "2024-01-01",
                        "salary_config_snapshot": {
                            "insurance_contributions": {},
                            "personal_income_tax": {},
                            "kpi_salary": {},
                            "overtime_multipliers": {},
                            "business_progressive_salary": {},
                        },
                        "status": "ONGOING",
                        "standard_working_days": "23.00",
                        "total_employees": 50,
                        "pending_count": 5,
                        "ready_count": 40,
                        "hold_count": 3,
                        "delivered_count": 2,
                        "total_gross_income": 5000000000,
                        "total_net_salary": 3800000000,
                        "completed_at": None,
                        "completed_by": None,
                        "created_at": "2024-01-01T00:00:00Z",
                        "updated_at": "2024-01-15T10:00:00Z",
                        "created_by": None,
                        "updated_by": None,
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    ),
    create=extend_schema(
        summary="Create new salary period",
        description="Create a new salary period for a specific month. This operation runs asynchronously and generates payroll slips for all employees.",
        tags=["10.6: Salary Periods"],
        request=SalaryPeriodCreateAsyncSerializer,
        responses={
            202: SalaryPeriodCreateResponseSerializer,
            400: {
                "type": "object",
                "properties": {
                    "month": {
                        "type": "array",
                        "items": {"type": "string"},
                    }
                },
            },
        },
        examples=[
            OpenApiExample(
                "Request - Create period",
                value={
                    "month": "1/2025",
                    "proposal_deadline": "2025-02-02",
                    "kpi_assessment_deadline": "2025-02-05",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success - Period creation started",
                value={
                    "success": True,
                    "data": {
                        "task_id": "abc123-def456-ghi789",
                        "status": "Task created",
                        "message": "Salary period creation started. Use task_status endpoint to check progress.",
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["202"],
            ),
            OpenApiExample(
                "Error - Period already exists",
                value={
                    "success": False,
                    "data": None,
                    "error": {"month": ["Salary period already exists for this month"]},
                },
                response_only=True,
                status_codes=["400"],
            ),
            OpenApiExample(
                "Error - Previous period not completed",
                value={
                    "success": False,
                    "data": None,
                    "error": {"month": ["Previous period 12/2024 is not completed yet"]},
                },
                response_only=True,
                status_codes=["400"],
            ),
            OpenApiExample(
                "Error - Invalid month format",
                value={
                    "success": False,
                    "data": None,
                    "error": {"month": ["Invalid month format. Use n/YYYY (e.g., 1/2025, 12/2025)"]},
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    partial_update=extend_schema(
        summary="Update salary period deadlines",
        description="Update proposal deadline and/or KPI assessment deadline for a salary period. Only these fields can be modified.",
        tags=["10.6: Salary Periods"],
        request=SalaryPeriodUpdateDeadlinesSerializer,
        responses={
            200: SalaryPeriodSerializer,
            400: {
                "type": "object",
                "properties": {
                    "proposal_deadline": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "kpi_assessment_deadline": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        },
        examples=[
            OpenApiExample(
                "Request - Update both deadlines",
                value={
                    "proposal_deadline": "2025-02-05",
                    "kpi_assessment_deadline": "2025-02-10",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Request - Update proposal deadline only",
                value={
                    "proposal_deadline": "2025-02-03",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Request - Clear deadline",
                value={
                    "proposal_deadline": None,
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success - Deadlines updated",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "SP-202501",
                        "month": "1/2025",
                        "salary_config_snapshot": {},
                        "status": "ONGOING",
                        "standard_working_days": "23.00",
                        "total_employees": 50,
                        "pending_count": 5,
                        "ready_count": 40,
                        "hold_count": 3,
                        "delivered_count": 2,
                        "total_gross_income": 5000000000,
                        "total_net_salary": 3800000000,
                        "proposal_deadline": "2025-02-05",
                        "kpi_assessment_deadline": "2025-02-10",
                        "employees_need_recovery": 0,
                        "employees_with_penalties": 0,
                        "employees_paid_penalties": 0,
                        "employees_with_travel": 0,
                        "employees_need_email": 0,
                        "completed_at": None,
                        "completed_by": None,
                        "created_at": "2025-01-01T00:00:00Z",
                        "updated_at": "2025-01-15T10:30:00Z",
                        "created_by": None,
                        "updated_by": None,
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Error - Invalid date format",
                value={
                    "success": False,
                    "data": None,
                    "error": {
                        "proposal_deadline": ["Date has wrong format. Use one of these formats instead: YYYY-MM-DD."]
                    },
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    task_status=extend_schema(
        tags=["10.6: Salary Periods"],
    ),
)
class SalaryPeriodViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for managing salary periods.

    Provides CRUD operations and custom actions for salary period management:
    - List, create, retrieve salary periods (with statistics included)
    - Recalculate all payroll slips in period
    - Complete period (mark as finished)
    - Send email notifications
    """

    queryset = SalaryPeriod.objects.all()
    serializer_class = SalaryPeriodSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter, PhraseSearchFilter]
    filterset_class = SalaryPeriodFilterSet
    ordering_fields = ["month", "created_at", "updated_at", "total_employees"]
    ordering = ["-month"]
    search_fields = ["code"]

    # Permission registration attributes
    module = "Payroll"
    submodule = "Salary Periods"
    permission_prefix = "salary_period"

    http_method_names = ["get", "post", "patch"]

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == "list":
            return SalaryPeriodListSerializer
        elif self.action == "create":
            return SalaryPeriodCreateAsyncSerializer
        elif self.action in ["update", "partial_update"]:
            return SalaryPeriodUpdateDeadlinesSerializer
        elif self.action == "task_status":
            return TaskStatusSerializer
        return SalaryPeriodSerializer

    @extend_schema(
        summary="Recalculate all payroll slips",
        description="Trigger recalculation for all payroll slips in this period. This operation runs asynchronously.",
        tags=["10.6: Salary Periods"],
        request=None,
        responses={
            202: SalaryPeriodRecalculateResponseSerializer,
            400: {
                "type": "object",
                "properties": {
                    "error": {"type": "string"},
                },
            },
        },
        examples=[
            OpenApiExample(
                "Success - Recalculation started",
                value={
                    "success": True,
                    "data": {
                        "task_id": "xyz789-abc123-def456",
                        "status": "Task created",
                        "message": "Salary period recalculation started. Use task_status endpoint to check progress.",
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["202"],
            ),
            OpenApiExample(
                "Error - Period already completed",
                value={
                    "success": False,
                    "data": None,
                    "error": "Cannot recalculate completed salary period",
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    @action(detail=True, methods=["post"])
    def recalculate(self, request, pk=None):
        """Recalculate all payroll slips in the period asynchronously."""
        period = self.get_object()

        if period.status == SalaryPeriod.Status.COMPLETED:
            return Response(
                {"error": "Cannot recalculate completed salary period"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Launch async task
        from apps.payroll.tasks import recalculate_salary_period_task

        task = recalculate_salary_period_task.delay(period.id)

        return Response(
            {
                "task_id": task.id,
                "status": "Task created",
                "message": "Salary period recalculation started. Use task_status endpoint to check progress.",
            },
            status=status.HTTP_202_ACCEPTED,
        )

    @extend_schema(
        summary="Complete salary period",
        description="Mark period as completed and set all READY slips to DELIVERED",
        tags=["10.6: Salary Periods"],
        examples=[
            OpenApiExample(
                "Success - Period completed",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "status": "COMPLETED",
                        "completed_at": "2024-02-01T10:00:00Z",
                        "delivered_count": 45,
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    )
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """Complete the salary period."""
        period = self.get_object()

        # Complete the period (can be executed at any time without checking)
        period.complete(user=request.user)

        return Response(
            {
                "id": period.id,
                "status": period.status,
                "completed_at": period.completed_at,
                "delivered_count": period.payroll_slips.filter(status=PayrollSlip.Status.DELIVERED).count(),
            }
        )

    @extend_schema(
        summary="Uncomplete salary period",
        description="Unlock a completed salary period. Only allowed if no newer periods exist.",
        tags=["10.6: Salary Periods"],
        request=None,
        responses={
            200: {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "status": {"type": "string"},
                    "uncompleted_at": {"type": "string", "format": "date-time"},
                    "message": {"type": "string"},
                },
            },
            400: {
                "type": "object",
                "properties": {
                    "error": {"type": "string"},
                },
            },
        },
        examples=[
            OpenApiExample(
                "Success - Period uncompleted",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "status": "ONGOING",
                        "uncompleted_at": "2024-02-15T10:00:00Z",
                        "message": "Period successfully uncompleted",
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Error - Newer periods exist",
                value={
                    "success": False,
                    "data": None,
                    "error": "Cannot uncomplete: newer salary periods exist",
                },
                response_only=True,
                status_codes=["400"],
            ),
            OpenApiExample(
                "Error - Period not completed",
                value={
                    "success": False,
                    "data": None,
                    "error": "Period is not completed",
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    @action(detail=True, methods=["post"])
    def uncomplete(self, request, pk=None):
        """Uncomplete/unlock the salary period."""
        period = self.get_object()

        can, reason = period.can_uncomplete()
        if not can:
            return Response({"error": reason}, status=status.HTTP_400_BAD_REQUEST)

        period.uncomplete(user=request.user)

        return Response(
            {
                "id": period.id,
                "status": period.status,
                "uncompleted_at": period.uncompleted_at,
                "message": "Period successfully uncompleted",
            }
        )

    @extend_schema(
        summary="Send email notifications",
        description="Send payroll slip emails to employees asynchronously. Returns task ID for tracking progress.",
        tags=["10.6: Salary Periods"],
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "filter_status": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["READY", "DELIVERED", "PENDING", "HOLD"]},
                        "description": "Filter slips by status (default: [READY, DELIVERED])",
                    }
                },
            }
        },
        responses={
            202: SalaryPeriodRecalculateResponseSerializer,
            400: {
                "type": "object",
                "properties": {
                    "error": {"type": "string"},
                },
            },
        },
        examples=[
            OpenApiExample(
                "Request - Send to READY and DELIVERED",
                value={"filter_status": ["READY", "DELIVERED"]},
                request_only=True,
            ),
            OpenApiExample(
                "Request - Send to all statuses",
                value={"filter_status": ["READY", "DELIVERED", "PENDING", "HOLD"]},
                request_only=True,
            ),
            OpenApiExample(
                "Success - Email sending started",
                value={
                    "success": True,
                    "data": {
                        "task_id": "xyz789-abc123-def456",
                        "status": "Task created",
                        "message": "Payroll email sending started. Use task_status endpoint to check progress.",
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["202"],
            ),
        ],
    )
    @action(detail=True, methods=["post"])
    def send_emails(self, request, pk=None):
        """Send email notifications for payroll slips asynchronously."""
        period = self.get_object()

        # Get filter status from request body
        filter_status = request.data.get("filter_status", [PayrollSlip.Status.READY, PayrollSlip.Status.DELIVERED])

        # Launch async task
        from apps.payroll.tasks import send_emails_for_period_task

        task = send_emails_for_period_task.delay(period.id, filter_status)

        return Response(
            {
                "task_id": task.id,
                "status": "Task created",
                "message": "Payroll email sending started. Use task_status endpoint to check progress.",
            },
            status=status.HTTP_202_ACCEPTED,
        )

    def create(self, request, *args, **kwargs):
        """Create salary period asynchronously and return task ID."""
        serializer = SalaryPeriodCreateAsyncSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Launch async task
        from apps.payroll.tasks import create_salary_period_task

        month = serializer.validated_data["month"]
        proposal_deadline = serializer.validated_data.get("proposal_deadline")
        kpi_assessment_deadline = serializer.validated_data.get("kpi_assessment_deadline")

        # Convert dates to ISO format strings for Celery
        proposal_deadline_str = proposal_deadline.isoformat() if proposal_deadline else None
        kpi_assessment_deadline_str = kpi_assessment_deadline.isoformat() if kpi_assessment_deadline else None

        task = create_salary_period_task.delay(month, proposal_deadline_str, kpi_assessment_deadline_str)

        return Response(
            {
                "task_id": task.id,
                "status": "Task created",
                "message": "Salary period creation started. Use task_status endpoint to check progress.",
            },
            status=status.HTTP_202_ACCEPTED,
        )

    def update(self, request, *args, **kwargs):
        """Update salary period deadlines."""
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = SalaryPeriodUpdateDeadlinesSerializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        # Update only the deadline fields
        if "proposal_deadline" in serializer.validated_data:
            instance.proposal_deadline = serializer.validated_data["proposal_deadline"]
        if "kpi_assessment_deadline" in serializer.validated_data:
            instance.kpi_assessment_deadline = serializer.validated_data["kpi_assessment_deadline"]

        instance.save()

        response_serializer = SalaryPeriodSerializer(instance)
        return Response(response_serializer.data)

    def partial_update(self, request, *args, **kwargs):
        """Partial update salary period deadlines."""
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

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

    @extend_schema(
        summary="Export payroll slips to XLSX (2 sheets)",
        description=(
            "Export payroll slips for this salary period to XLSX format with 2 sheets:\n"
            "- Sheet 1 'Ready Slips': READY slips (ONGOING) or DELIVERED slips (COMPLETED)\n"
            "- Sheet 2 'Not Ready Slips': PENDING/HOLD slips\n\n"
            "Each sheet contains detailed salary breakdown including position income, "
            "working days, overtime, insurance contributions, tax calculations, and bank account.\n\n"
            "Headers include grouped columns for: Position Income (9 cols), Working Days (4 cols), "
            "Overtime (10 cols), Employer Contributions (5 cols), Employee Deductions (4 cols), "
            "and Tax Information (5 cols)."
        ),
        tags=["10.6: Salary Periods"],
        parameters=[],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "filename": {"type": "string"},
                    "expires_in": {"type": "integer"},
                    "storage_backend": {"type": "string"},
                },
            },
        },
        examples=[
            OpenApiExample(
                "Success - Export link with 2 sheets",
                value={
                    "success": True,
                    "data": {
                        "url": "https://s3.amazonaws.com/...",
                        "filename": "salary_period_SP-202501_payroll_slips.xlsx",
                        "expires_in": 3600,
                        "storage_backend": "s3",
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    )
    @action(detail=True, methods=["get"], url_path="payrollslips-export")
    def payrollslips_export(self, request, pk=None):
        """Export payroll slips for this salary period to XLSX with 2 sheets (Ready and Not Ready)."""
        from django.conf import settings

        from libs.export_xlsx.constants import STORAGE_S3
        from libs.export_xlsx.generator import XLSXGenerator
        from libs.export_xlsx.storage import get_storage_backend

        period = self.get_object()

        # Define detailed headers structure for both sheets
        # Row 1: Group headers (with colspan)
        # Row 2: Column headers (sub-headers for groups with span > 1, empty for span = 1)

        # For groups with span=1, leave the second row header empty to avoid duplication
        headers = [
            "",  # A: STT - already in group
            "",  # B: Employee code - already in group
            "",  # C: Full name - already in group
            "",  # D: Department - already in group
            "",  # E: Position - already in group
            "",  # F: Employment status - already in group
            "",  # G: Email - already in group
            "",  # H: Sales revenue - already in group
            "",  # I: Transaction count - already in group
            # Position income (9 columns) - need sub-headers
            _("Base salary"),  # J
            _("Lunch allowance"),  # K
            _("Phone allowance"),  # L
            _("Travel allowance"),  # M
            _("KPI salary"),  # N
            _("KPI grade"),  # O - Changed from KPI percentage
            _("KPI bonus"),  # P
            _("Business bonus"),  # Q
            _("Total"),  # R
            # Working days (4 columns) - need sub-headers
            _("Standard"),  # S
            _("Actual"),  # T
            _("Probation"),  # U
            _("Official"),  # V
            # Income by working days
            "",  # W: Already in group
            # Overtime (10 columns) - need sub-headers
            _("Weekday/Saturday"),  # X
            _("Sunday"),  # Y
            _("Holiday"),  # Z
            _("Total"),  # AA
            _("Hourly rate"),  # AB
            _("Reference overtime pay"),  # AC
            _("Progress allowance"),  # AD
            _("Hours for calculation"),  # AE
            _("Taxable overtime"),  # AF
            _("Non-taxable overtime"),  # AG
            # Total income
            "",  # AH: Already in group
            # Insurance base
            "",  # AI: Already in group
            # Employer contributions (5 columns) - need sub-headers
            _("Social insurance (17%)"),  # AJ
            _("Health insurance (3%)"),  # AK
            _("Accident insurance (0.5%)"),  # AL
            _("Unemployment insurance (1%)"),  # AM
            _("Union fee (2%)"),  # AN
            # Employee deductions (4 columns) - need sub-headers
            _("Social insurance (8%)"),  # AO
            _("Health insurance (1.5%)"),  # AP
            _("Unemployment insurance (1%)"),  # AQ
            _("Union fee (1%)"),  # AR
            # Tax (6 columns) - need sub-headers
            _("Tax code"),  # AS
            _("Dependents count"),  # AT
            _("Total deduction"),  # AU
            _("Non-taxable allowance"),  # AV
            _("Taxable income"),  # AW
            _("Personal income tax"),  # AX
            # Adjustments
            "",  # AY: Back pay - already in group
            "",  # AZ: Recovery - already in group
            # Net salary
            "",  # BA: Already in group
            # Bank account
            "",  # BB: Already in group
        ]

        # Define groups for colspan headers
        groups = [
            {"title": _("No."), "span": 1},
            {"title": _("Employee code"), "span": 1},
            {"title": _("Full name"), "span": 1},
            {"title": _("Department"), "span": 1},
            {"title": _("Position"), "span": 1},
            {"title": _("Employment status"), "span": 1},
            {"title": _("Email"), "span": 1},
            {"title": _("Sales revenue"), "span": 1},
            {"title": _("Transaction count"), "span": 1},
            {"title": _("Position income"), "span": 9},
            {"title": _("Working days"), "span": 4},
            {"title": _("Actual working days income"), "span": 1},
            {"title": _("Overtime"), "span": 10},
            {"title": _("Gross income"), "span": 1},
            {"title": _("Insurance base"), "span": 1},
            {"title": _("Employer contributions"), "span": 5},
            {"title": _("Employee deductions"), "span": 4},
            {"title": _("Tax information"), "span": 6},  # Changed from 5 to 6
            {"title": _("Back pay"), "span": 1},
            {"title": _("Recovery"), "span": 1},
            {"title": _("Net salary"), "span": 1},
            {"title": _("Bank account"), "span": 1},
        ]

        field_names = [
            "stt",  # A
            "employee_code",  # B
            "employee_name",  # C
            "department_name",  # D
            "position_name",  # E
            "employment_status",  # F
            "employee_email",  # G
            "sales_revenue",  # H
            "sales_transaction_count",  # I
            # Position income (9 fields)
            "base_salary",  # J
            "lunch_allowance",  # K
            "phone_allowance",  # L
            "travel_expense_by_working_days",  # M
            "kpi_salary",  # N
            "kpi_grade",  # O
            "kpi_bonus",  # P
            "business_progressive_salary",  # Q
            "total_position_income",  # R
            # Working days (4 fields)
            "standard_working_days",  # S
            "total_working_days",  # T
            "probation_working_days",  # U
            "official_working_days",  # V
            # Income by working days (1 field)
            "actual_working_days_income",  # W
            # Overtime (10 fields)
            "tc1_overtime_hours",  # X
            "tc2_overtime_hours",  # Y
            "tc3_overtime_hours",  # Z
            "total_overtime_hours",  # AA
            "hourly_rate",  # AB
            "overtime_pay_reference",  # AC - Reference overtime pay
            "overtime_progress_allowance",  # AD
            "overtime_hours_for_calculation",  # AE
            "taxable_overtime_salary",  # AF
            "non_taxable_overtime_salary",  # AG
            # Total income (1 field)
            "gross_income",  # AH
            # Insurance base (1 field)
            "social_insurance_base",  # AI
            # Employer contributions (5 fields)
            "employer_social_insurance",  # AJ
            "employer_health_insurance",  # AK
            "employer_accident_insurance",  # AL
            "employer_unemployment_insurance",  # AM
            "employer_union_fee",  # AN
            # Employee deductions (4 fields)
            "employee_social_insurance",  # AO
            "employee_health_insurance",  # AP
            "employee_unemployment_insurance",  # AQ
            "employee_union_fee",  # AR
            # Tax (5 fields)
            "tax_code",  # AS
            "dependent_count",  # AT
            "total_deduction",  # AU
            "non_taxable_allowance",  # AV
            "taxable_income",  # AW
            "personal_income_tax",  # AX
            # Adjustments (2 fields)
            "back_pay_amount",  # AY
            "recovery_amount",  # AZ
            # Net salary (1 field)
            "net_salary",  # BA
            # Bank account (1 field)
            "bank_account",  # BB
        ]

        # Sheet 1: Ready slips (based on SalaryPeriodReadySlipsViewSet logic)
        if period.status == SalaryPeriod.Status.ONGOING:
            ready_slips = (
                PayrollSlip.objects.filter(status=PayrollSlip.Status.READY)
                .select_related("employee", "salary_period")
                .prefetch_related("employee__bank_accounts")
            )
        else:  # COMPLETED
            ready_slips = (
                PayrollSlip.objects.filter(payment_period=period, status=PayrollSlip.Status.DELIVERED)
                .select_related("employee", "salary_period")
                .prefetch_related("employee__bank_accounts")
            )

        # Sheet 2: Not ready slips (based on SalaryPeriodNotReadySlipsViewSet logic)
        if period.status == SalaryPeriod.Status.ONGOING:
            not_ready_slips = (
                PayrollSlip.objects.filter(
                    salary_period=period, status__in=[PayrollSlip.Status.PENDING, PayrollSlip.Status.HOLD]
                )
                .select_related("employee", "salary_period")
                .prefetch_related("employee__bank_accounts")
            )
        else:  # COMPLETED
            not_ready_slips = (
                PayrollSlip.objects.filter(
                    salary_period=period,
                    status__in=[PayrollSlip.Status.PENDING, PayrollSlip.Status.HOLD, PayrollSlip.Status.READY],
                )
                .select_related("employee", "salary_period")
                .prefetch_related("employee__bank_accounts")
            )

        # Build data for both sheets
        def build_sheet_data(slips):
            """Build sheet data with Excel formulas for calculated fields."""
            data = []

            # Get insurance config percentages from period's salary config
            insurance_config = period.salary_config_snapshot.get("insurance_contributions", {})
            employer_si_rate = insurance_config.get("employer_social_insurance", 17) / 100
            employer_hi_rate = insurance_config.get("employer_health_insurance", 3) / 100
            employer_ai_rate = insurance_config.get("employer_accident_insurance", 0.5) / 100
            employer_ui_rate = insurance_config.get("employer_unemployment_insurance", 1) / 100
            employer_uf_rate = insurance_config.get("employer_union_fee", 2) / 100
            employee_si_rate = insurance_config.get("employee_social_insurance", 8) / 100
            employee_hi_rate = insurance_config.get("employee_health_insurance", 1.5) / 100
            employee_ui_rate = insurance_config.get("employee_unemployment_insurance", 1) / 100
            employee_uf_rate = insurance_config.get("employee_union_fee", 1) / 100

            # Get tax config
            tax_config = period.salary_config_snapshot.get("personal_income_tax", {})
            personal_deduction = tax_config.get("personal_deduction", 11000000)
            dependent_deduction = tax_config.get("dependent_deduction", 4400000)

            # Employment status constants (English values used in formulas)
            from apps.hrm.constants import EmployeeType

            probation_status = EmployeeType.PROBATION.value  # "PROBATION"
            official_status = EmployeeType.OFFICIAL.value  # "OFFICIAL"

            for idx, slip in enumerate(slips, start=1):
                # Row number in Excel (accounting for header rows: 1 group + 1 header = 2 rows)
                excel_row = idx + 2

                row = {
                    # A: STT
                    "stt": idx,
                    # B: Employee code
                    "employee_code": slip.employee_code or "",
                    # C: Full name
                    "employee_name": slip.employee_name or "",
                    # D: Department
                    "department_name": slip.department_name or "",
                    # E: Position
                    "position_name": slip.position_name or "",
                    # F: Employment status
                    "employment_status": slip.employment_status or "",
                    # G: Email
                    "employee_email": slip.employee_email or "",
                    # H: Sales revenue
                    "sales_revenue": slip.sales_revenue or 0,
                    # I: Transaction count
                    "sales_transaction_count": slip.sales_transaction_count or 0,
                    # Position income (J-R)
                    "base_salary": slip.base_salary or 0,  # J
                    "lunch_allowance": slip.lunch_allowance or 0,  # K
                    "phone_allowance": slip.phone_allowance or 0,  # L
                    "travel_expense_by_working_days": slip.travel_expense_by_working_days or 0,  # M
                    "kpi_salary": slip.kpi_salary or 0,  # N
                    "kpi_grade": slip.kpi_grade or "",  # O
                    "kpi_bonus": slip.kpi_bonus or 0,  # P
                    "business_progressive_salary": slip.business_progressive_salary or 0,  # Q
                    # R: Total position income = J+K+L+M+N+P+Q
                    "total_position_income": f"=J{excel_row}+K{excel_row}+L{excel_row}+M{excel_row}+N{excel_row}+P{excel_row}+Q{excel_row}",
                    # Working days (S-V)
                    "standard_working_days": slip.standard_working_days or 0,  # S
                    "total_working_days": slip.total_working_days or 0,  # T
                    "probation_working_days": slip.probation_working_days or 0,  # U
                    "official_working_days": slip.official_working_days or 0,  # V
                    # W: Actual working days income
                    # Formula: IF(E{row}="NVKD",(V{row}*R{row}+U{row}*R{row})/S{row},(V{row}*R{row}+U{row}*R{row}*0.85)/S{row})
                    "actual_working_days_income": f'=IF(E{excel_row}="NVKD",(V{excel_row}*R{excel_row}+U{excel_row}*R{excel_row})/S{excel_row},(V{excel_row}*R{excel_row}+U{excel_row}*R{excel_row}*0.85)/S{excel_row})',
                    # Overtime (X-AG)
                    "tc1_overtime_hours": slip.tc1_overtime_hours or 0,  # X
                    "tc2_overtime_hours": slip.tc2_overtime_hours or 0,  # Y
                    "tc3_overtime_hours": slip.tc3_overtime_hours or 0,  # Z
                    "total_overtime_hours": slip.total_overtime_hours or 0,  # AA - fill data, not formula
                    # AB: Hourly rate = IF(F="PROBATION",R*0.85/S/8,R/S/8)
                    "hourly_rate": f'=IF(F{excel_row}="{probation_status}",R{excel_row}*0.85/S{excel_row}/8,R{excel_row}/S{excel_row}/8)',
                    # AC: Reference overtime pay = (X*1.5+Y*2+Z*3)*AB
                    "overtime_pay_reference": f"=(X{excel_row}*1.5+Y{excel_row}*2+Z{excel_row}*3)*AB{excel_row}",
                    # AD: Progress allowance = AC-AF
                    "overtime_progress_allowance": f"=AC{excel_row}-AF{excel_row}",
                    # AE: Hours for calculation = AA
                    "overtime_hours_for_calculation": f"=AA{excel_row}",
                    # AF: Taxable overtime = AE*AB
                    "taxable_overtime_salary": f"=AE{excel_row}*AB{excel_row}",
                    # AG: Non-taxable overtime = IF(AD>AF*2,AF*2,AC-AF)
                    "non_taxable_overtime_salary": f"=IF(AD{excel_row}>AF{excel_row}*2,AF{excel_row}*2,AC{excel_row}-AF{excel_row})",
                    # AH: Gross income = W+AF+AG
                    "gross_income": f"=W{excel_row}+AF{excel_row}+AG{excel_row}",
                    # AI: Insurance base = IF(F="OFFICIAL",J,0)
                    "social_insurance_base": f'=IF(F{excel_row}="{official_status}",J{excel_row},0)',
                    # Employer contributions (AJ-AN)
                    "employer_social_insurance": f"=AI{excel_row}*{employer_si_rate}",  # AJ
                    "employer_health_insurance": f"=AI{excel_row}*{employer_hi_rate}",  # AK
                    "employer_accident_insurance": f"=AI{excel_row}*{employer_ai_rate}",  # AL
                    "employer_unemployment_insurance": f"=AI{excel_row}*{employer_ui_rate}",  # AM
                    "employer_union_fee": f"=AI{excel_row}*{employer_uf_rate}",  # AN
                    # Employee deductions (AO-AR)
                    "employee_social_insurance": f"=AI{excel_row}*{employee_si_rate}",  # AO
                    "employee_health_insurance": f"=AI{excel_row}*{employee_hi_rate}",  # AP
                    "employee_unemployment_insurance": f"=AI{excel_row}*{employee_ui_rate}",  # AQ
                    "employee_union_fee": f"=AI{excel_row}*{employee_uf_rate}",  # AR
                    # Tax information (AS-AX)
                    "tax_code": slip.tax_code or "",  # AS
                    "dependent_count": slip.dependent_count or 0,  # AT
                    # AU: Total deduction = personal_deduction + dependent_count * dependent_deduction
                    "total_deduction": f"={personal_deduction}+AT{excel_row}*{dependent_deduction}",
                    # AV: Non-taxable allowance = SUM(K:L)/S*(U*0.85+V)
                    "non_taxable_allowance": f"=SUM(K{excel_row}:L{excel_row})/S{excel_row}*(U{excel_row}*0.85+V{excel_row})",
                    # AW: Taxable income - depends on employment status
                    # If F="OFFICIAL": =IF(AH-SUM(AO:AQ)-AU-AG-AV>0,AH-SUM(AO:AQ)-AU-AG-AV,0)
                    # Else: =AH
                    "taxable_income": f'=IF(F{excel_row}="{official_status}",IF(AH{excel_row}-SUM(AO{excel_row}:AQ{excel_row})-AU{excel_row}-AG{excel_row}-AV{excel_row}>0,AH{excel_row}-SUM(AO{excel_row}:AQ{excel_row})-AU{excel_row}-AG{excel_row}-AV{excel_row},0),AH{excel_row})',
                    # AX: Personal income tax
                    # If F="OFFICIAL": Progressive tax brackets
                    # Else: =IF(AW>=2000000,AW*10%,0)
                    "personal_income_tax": f'=IF(F{excel_row}="{official_status}",IF(AW{excel_row}<=5000000,AW{excel_row}*0.05,IF(AW{excel_row}<=10000000,AW{excel_row}*0.1-250000,IF(AW{excel_row}<=18000000,AW{excel_row}*0.15-750000,IF(AW{excel_row}<=32000000,AW{excel_row}*0.2-1650000,IF(AW{excel_row}<=52000000,AW{excel_row}*0.25-3250000,IF(AW{excel_row}<=80000000,AW{excel_row}*0.3-5850000,AW{excel_row}*0.35-9850000)))))),IF(AW{excel_row}>=2000000,AW{excel_row}*0.1,0))',
                    # Adjustments (AY-AZ)
                    "back_pay_amount": slip.back_pay_amount or 0,  # AY
                    "recovery_amount": slip.recovery_amount or 0,  # AZ
                    # BA: Net salary = ROUND(AH-SUM(AO:AQ)-AR+AY-AZ-AX,0)
                    "net_salary": f"=ROUND(AH{excel_row}-SUM(AO{excel_row}:AQ{excel_row})-AR{excel_row}+AY{excel_row}-AZ{excel_row}-AX{excel_row},0)",
                    # BB: Bank account
                    "bank_account": (
                        slip.employee.default_bank_account.account_number
                        if slip.employee and slip.employee.default_bank_account
                        else ""
                    ),
                }
                data.append(row)
            return data

        ready_data = build_sheet_data(ready_slips)
        not_ready_data = build_sheet_data(not_ready_slips)

        # Create schema with 2 sheets
        schema = {
            "sheets": [
                {
                    "name": "Ready Slips",
                    "groups": groups,
                    "headers": headers,
                    "field_names": field_names,
                    "data": ready_data,
                },
                {
                    "name": "Not Ready Slips",
                    "groups": groups,
                    "headers": headers,
                    "field_names": field_names,
                    "data": not_ready_data,
                },
            ]
        }

        # Generate XLSX file
        generator = XLSXGenerator()
        file_content = generator.generate(schema)

        # Upload to S3 and return presigned URL
        storage = get_storage_backend(STORAGE_S3)
        filename = f"salary_period_{period.code}_payroll_slips.xlsx"
        file_path = storage.save(file_content, filename)
        presigned_url = storage.get_url(file_path)
        file_size = storage.get_file_size(file_path)

        expires_in = getattr(settings, "EXPORTER_PRESIGNED_URL_EXPIRES", 3600)

        response_data = {
            "url": presigned_url,
            "filename": filename,
            "expires_in": expires_in,
            "storage_backend": "s3",
        }

        if file_size is not None:
            response_data["size_bytes"] = file_size

        return Response(response_data, status=status.HTTP_200_OK)


@extend_schema_view(
    list=extend_schema(
        summary="Get ready payroll slips",
        description=(
            "Get ready payroll slips based on period status:\n"
            "- ONGOING: Returns all READY slips from this period and all previous periods\n"
            "- COMPLETED: Returns all DELIVERED slips from this period only\n\n"
            "Supports filtering, searching, and ordering same as PayrollSlipViewSet."
        ),
        tags=["10.6: Salary Periods"],
        responses={
            200: PayrollSlipSerializer(many=True),
        },
        examples=[
            OpenApiExample(
                "Success - Ready slips",
                value={
                    "success": True,
                    "data": {
                        "count": 2,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": 1,
                                "code": "PS_202401_0001",
                                "employee_code": "E001",
                                "employee_name": "John Doe",
                                "department_name": "IT",
                                "position_name": "Developer",
                                "gross_income": "15000000.00",
                                "net_salary": "13500000.00",
                                "status": "READY",
                                "colored_status": {"value": "READY", "variant": "success"},
                            }
                        ],
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    )
)
class SalaryPeriodReadySlipsViewSet(BaseReadOnlyModelViewSet):
    """ViewSet for Table 1 (Payment Table) - slips to be paid in this period.

    Returns:
    - For ONGOING period: READY slips from this period + carried over READY slips
    - For COMPLETED period: DELIVERED slips where payment_period = this period
    """

    queryset = PayrollSlip.objects.none()
    serializer_class = PayrollSlipSerializer
    permission_classes = [RoleBasedPermission, DataScopePermission]
    module = _("Payroll")
    submodule = _("Salary Periods")
    permission_prefix = "salary_period"
    permission_action_map = {"list": "list_ready"}
    STANDARD_ACTIONS = {}
    PERMISSION_REGISTERED_ACTIONS = {
        "list_ready": {
            "name_template": _("View Payment Table (Ready Slips)"),
            "description_template": _("View payment table with ready/delivered payroll slips"),
        }
    }

    # Data scope configuration for role-based filtering
    data_scope_config = {
        "branch_field": "employee__branch",
        "block_field": "employee__block",
        "department_field": "employee__department",
    }

    pagination_class = PageNumberWithSizePagination
    filter_backends = [RoleDataScopeFilterBackend, DjangoFilterBackend, OrderingFilter, PhraseSearchFilter]
    filterset_class = PayrollSlipFilterSet
    ordering_fields = [
        "code",
        "employee_code",
        "employee_name",
        "gross_income",
        "net_salary",
        "calculated_at",
    ]
    ordering = ["-calculated_at"]
    search_fields = ["employee_code", "employee_name", "code"]
    http_method_names = ["get"]

    def get_queryset(self):
        """Get queryset based on salary period status.

        Table 1 (Payment Table):
        - ONGOING: All READY slips (regardless of which salary_period they belong to)
        - COMPLETED: DELIVERED slips where payment_period = this period
        """
        pk = self.kwargs.get("pk")
        if not pk:
            return PayrollSlip.objects.none()

        try:
            period = SalaryPeriod.objects.get(pk=pk)
        except SalaryPeriod.DoesNotExist:
            return PayrollSlip.objects.none()

        if period.status == SalaryPeriod.Status.ONGOING:
            # Table 1 for ONGOING: All READY slips (from any period)
            # This includes carry-over slips from previous completed periods
            queryset = PayrollSlip.objects.filter(status=PayrollSlip.Status.READY).select_related(
                "employee", "salary_period", "payment_period"
            )
        else:  # COMPLETED
            # Table 1 for COMPLETED: DELIVERED slips paid in this period
            queryset = PayrollSlip.objects.filter(
                payment_period=period, status=PayrollSlip.Status.DELIVERED
            ).select_related("employee", "salary_period", "payment_period")

        return queryset


@extend_schema_view(
    list=extend_schema(
        summary="Get not-ready payroll slips",
        description=(
            "Get not-ready payroll slips based on period status:\n"
            "- ONGOING: Returns all PENDING/HOLD slips from this period and all previous periods\n"
            "- COMPLETED: Returns all PENDING/HOLD slips from this period only\n\n"
            "Supports filtering, searching, and ordering same as PayrollSlipViewSet."
        ),
        tags=["10.6: Salary Periods"],
        responses={
            200: PayrollSlipSerializer(many=True),
        },
        examples=[
            OpenApiExample(
                "Success - Not ready slips",
                value={
                    "success": True,
                    "data": {
                        "count": 2,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": 2,
                                "code": "PS_202401_0002",
                                "employee_code": "E002",
                                "employee_name": "Jane Smith",
                                "department_name": "HR",
                                "position_name": "Manager",
                                "gross_income": "20000000.00",
                                "net_salary": "18000000.00",
                                "status": "PENDING",
                                "colored_status": {"value": "PENDING", "variant": "warning"},
                            }
                        ],
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    )
)
class SalaryPeriodNotReadySlipsViewSet(BaseReadOnlyModelViewSet):
    """ViewSet for Table 2 (Deferred Table) - slips not paid in this period.

    Returns:
    - For ONGOING period: PENDING/HOLD slips from this period
    - For COMPLETED period: All non-DELIVERED slips (PENDING/HOLD/READY) that belonged to this period.
      READY slips appear here if they became ready AFTER the period was completed (e.g., after penalty payment).
    """

    queryset = PayrollSlip.objects.none()
    serializer_class = PayrollSlipSerializer
    permission_classes = [RoleBasedPermission, DataScopePermission]
    module = _("Payroll")
    submodule = _("Salary Periods")
    permission_prefix = "salary_period"
    permission_action_map = {"list": "list_not_ready"}
    STANDARD_ACTIONS = {}
    PERMISSION_REGISTERED_ACTIONS = {
        "list_not_ready": {
            "name_template": _("View Deferred Table (Not Ready Slips)"),
            "description_template": _("View deferred table with pending/hold payroll slips"),
        }
    }

    # Data scope configuration for role-based filtering
    data_scope_config = {
        "branch_field": "employee__branch",
        "block_field": "employee__block",
        "department_field": "employee__department",
    }

    pagination_class = PageNumberWithSizePagination
    filter_backends = [RoleDataScopeFilterBackend, DjangoFilterBackend, OrderingFilter, PhraseSearchFilter]
    filterset_class = PayrollSlipFilterSet
    ordering_fields = [
        "code",
        "employee_code",
        "employee_name",
        "gross_income",
        "net_salary",
        "calculated_at",
    ]
    ordering = ["-calculated_at"]
    search_fields = ["employee_code", "employee_name", "code"]
    http_method_names = ["get"]

    def get_queryset(self):
        """Get queryset based on salary period status.

        Table 2 (Deferred Table):
        - ONGOING: PENDING/HOLD slips from this period only
        - COMPLETED: All non-DELIVERED slips (PENDING/HOLD/READY) from this period
        """
        pk = self.kwargs.get("pk")
        if not pk:
            return PayrollSlip.objects.none()

        try:
            period = SalaryPeriod.objects.get(pk=pk)
        except SalaryPeriod.DoesNotExist:
            return PayrollSlip.objects.none()

        if period.status == SalaryPeriod.Status.ONGOING:
            # Table 2 for ONGOING: PENDING/HOLD slips only
            queryset = PayrollSlip.objects.filter(
                salary_period=period, status__in=[PayrollSlip.Status.PENDING, PayrollSlip.Status.HOLD]
            ).select_related("employee", "salary_period", "payment_period")
        else:  # COMPLETED
            # Table 2 for COMPLETED: All non-DELIVERED slips (PENDING/HOLD/READY)
            # READY slips here are those that became ready after period completion
            queryset = PayrollSlip.objects.filter(
                salary_period=period,
                status__in=[PayrollSlip.Status.PENDING, PayrollSlip.Status.HOLD, PayrollSlip.Status.READY],
            ).select_related("employee", "salary_period", "payment_period")

        return queryset
