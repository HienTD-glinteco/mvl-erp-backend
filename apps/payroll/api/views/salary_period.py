"""ViewSet for SalaryPeriod model."""

from django.db.models import Q
from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.core.api.permissions import DataScopePermission, RoleBasedPermission
from apps.hrm.utils.filters import RoleDataScopeFilterBackend
from apps.payroll.api.filtersets import PayrollSlipFilterSet, SalaryPeriodFilterSet
from apps.payroll.api.serializers import (
    PayrollSlipExportSerializer,
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
        summary="Export payroll slips to XLSX",
        description="Export all payroll slips for this salary period to XLSX format with filtering support",
        tags=["10.6: Salary Periods"],
        parameters=[
            OpenApiParameter(
                name="search",
                description="Search query (searches employee code, employee name, code)",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="ordering",
                description="Order by field(s). Prefix with '-' for descending order",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="employee_code",
                description="Filter by employee code",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="department_name",
                description="Filter by department name",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="position_name",
                description="Filter by position name",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="status",
                description="Filter by status",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="has_unpaid_penalty",
                description="Filter by unpaid penalty status",
                required=False,
                type=bool,
            ),
        ],
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
                "Success - Export link",
                value={
                    "success": True,
                    "data": {
                        "url": "https://s3.amazonaws.com/...",
                        "filename": "salary_period_payroll_slips.xlsx",
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
        """Export payroll slips for this salary period to XLSX."""
        from django.conf import settings

        from libs.export_xlsx.constants import STORAGE_S3
        from libs.export_xlsx.generator import XLSXGenerator
        from libs.export_xlsx.storage import get_storage_backend

        period = self.get_object()

        # Get queryset of payroll slips for this period
        slips = period.payroll_slips.select_related("employee", "salary_period").all()

        # Apply search filter if provided
        search = request.query_params.get("search")
        if search:
            slips = slips.filter(
                Q(employee_code__icontains=search) | Q(employee_name__icontains=search) | Q(code__icontains=search)
            )

        # Apply field filters
        employee_code = request.query_params.get("employee_code")
        if employee_code:
            slips = slips.filter(employee_code__icontains=employee_code)

        department_name = request.query_params.get("department_name")
        if department_name:
            slips = slips.filter(department_name__icontains=department_name)

        position_name = request.query_params.get("position_name")
        if position_name:
            slips = slips.filter(position_name__icontains=position_name)

        status_filter = request.query_params.get("status")
        if status_filter:
            slips = slips.filter(status=status_filter)

        has_unpaid_penalty = request.query_params.get("has_unpaid_penalty")
        if has_unpaid_penalty is not None:
            slips = slips.filter(has_unpaid_penalty=has_unpaid_penalty.lower() == "true")

        # Apply ordering
        ordering = request.query_params.get("ordering", "-calculated_at")
        slips = slips.order_by(ordering)

        # Serialize data using export serializer
        serializer = PayrollSlipExportSerializer(slips, many=True)

        # Prepare export data
        headers = [str(field.label) for field in serializer.child.fields.values()]
        data = serializer.data
        field_names = list(serializer.child.fields.keys())

        schema = {
            "sheets": [
                {
                    "name": f"Payroll Slips - {period.code}",
                    "headers": headers,
                    "field_names": field_names,
                    "data": data,
                }
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
    """ViewSet for ready payroll slips."""

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
            "name_template": _("View Ready Payroll Slips"),
            "description_template": _("View ready payroll slips"),
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
        """Get queryset based on salary period status."""
        pk = self.kwargs.get("pk")
        if not pk:
            return PayrollSlip.objects.none()

        try:
            period = SalaryPeriod.objects.get(pk=pk)
        except SalaryPeriod.DoesNotExist:
            return PayrollSlip.objects.none()

        if period.status == SalaryPeriod.Status.ONGOING:
            # Get all READY slips from this period and all previous periods
            queryset = PayrollSlip.objects.filter(
                Q(salary_period=period, status=PayrollSlip.Status.READY)
                | Q(salary_period__month__lt=period.month, status=PayrollSlip.Status.READY)
            ).select_related("employee", "salary_period")
        else:  # COMPLETED
            # Get all DELIVERED slips from this period only
            queryset = PayrollSlip.objects.filter(
                salary_period=period, status=PayrollSlip.Status.DELIVERED
            ).select_related("employee", "salary_period")

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
    """ViewSet for not-ready payroll slips."""

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
            "name_template": _("View Not-Ready Payroll Slips"),
            "description_template": _("View not-ready payroll slips"),
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
        """Get queryset based on salary period status."""
        pk = self.kwargs.get("pk")
        if not pk:
            return PayrollSlip.objects.none()

        try:
            period = SalaryPeriod.objects.get(pk=pk)
        except SalaryPeriod.DoesNotExist:
            return PayrollSlip.objects.none()

        if period.status == SalaryPeriod.Status.ONGOING:
            # Get all PENDING/HOLD slips from this period and all previous periods
            queryset = PayrollSlip.objects.filter(
                Q(salary_period=period, status__in=[PayrollSlip.Status.PENDING, PayrollSlip.Status.HOLD])
                | Q(
                    salary_period__month__lt=period.month,
                    status__in=[PayrollSlip.Status.PENDING, PayrollSlip.Status.HOLD],
                )
            ).select_related("employee", "salary_period")
        else:  # COMPLETED
            # Get all PENDING/HOLD slips from this period only
            queryset = PayrollSlip.objects.filter(
                salary_period=period, status__in=[PayrollSlip.Status.PENDING, PayrollSlip.Status.HOLD]
            ).select_related("employee", "salary_period")

        return queryset
