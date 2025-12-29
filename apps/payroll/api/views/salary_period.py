"""ViewSet for SalaryPeriod model."""

from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.payroll.api.serializers import (
    SalaryPeriodCreateAsyncSerializer,
    SalaryPeriodListSerializer,
    SalaryPeriodSerializer,
    SalaryPeriodUpdateDeadlinesSerializer,
    TaskStatusSerializer,
)
from apps.payroll.models import PayrollSlip, SalaryPeriod
from libs import BaseReadOnlyModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter


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
)
class SalaryPeriodViewSet(AuditLoggingMixin, BaseReadOnlyModelViewSet):
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
    filterset_fields = {
        "month": ["exact", "gte", "lte"],
        "status": ["exact"],
        "proposal_deadline": ["exact", "gte", "lte"],
        "kpi_assessment_deadline": ["exact", "gte", "lte"],
        "created_at": ["gte", "lte"],
        "updated_at": ["gte", "lte"],
    }
    ordering_fields = ["month", "created_at", "updated_at", "total_employees"]
    ordering = ["-month"]
    search_fields = ["code"]

    # Permission registration attributes
    module = "Payroll"
    submodule = "Salary Periods"
    permission_prefix = "salary_period"

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
        description="Trigger recalculation for all payroll slips in this period",
        tags=["10.6: Salary Periods"],
        examples=[
            OpenApiExample(
                "Success - Recalculation started",
                value={
                    "success": True,
                    "data": {"message": "Recalculation started for 50 payroll slips"},
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
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
        description="Send payroll slip emails to employees",
        tags=["10.6: Salary Periods"],
        examples=[
            OpenApiExample(
                "Success - Emails sent",
                value={
                    "success": True,
                    "data": {
                        "sent_count": 45,
                        "failed_count": 0,
                        "failed_emails": [],
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    )
    @action(detail=True, methods=["post"])
    def send_emails(self, request, pk=None):
        """Send email notifications for payroll slips."""
        period = self.get_object()

        # Filter slips to send
        filter_status = request.data.get("filter_status", [PayrollSlip.Status.READY, PayrollSlip.Status.DELIVERED])
        slips = period.payroll_slips.filter(status__in=filter_status)

        # TODO: Implement email sending logic
        # For now, just return mock data

        return Response(
            {
                "sent_count": slips.count(),
                "failed_count": 0,
                "failed_emails": [],
            }
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

    @action(detail=True, methods=["get"])
    def ready(self, request, pk=None):
        """Get ready/delivered payroll slips with filtering and search."""
        period = self.get_object()

        if period.status == SalaryPeriod.Status.ONGOING:
            # Get all READY slips from this and previous periods
            slips = PayrollSlip.objects.filter(
                salary_period__month__lte=period.month, status=PayrollSlip.Status.READY
            ).select_related("employee", "salary_period")
        else:
            # Period is COMPLETED - get only DELIVERED slips from this period
            slips = period.payroll_slips.filter(status=PayrollSlip.Status.DELIVERED).select_related(
                "employee", "salary_period"
            )

        # Apply search filter
        search = request.query_params.get("search")
        if search:
            from django.db.models import Q

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

        # Apply ordering
        ordering = request.query_params.get("ordering", "-calculated_at")
        slips = slips.order_by(ordering)

        from apps.payroll.api.serializers import PayrollSlipListSerializer

        page = self.paginate_queryset(slips)
        if page is not None:
            serializer = PayrollSlipListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = PayrollSlipListSerializer(slips, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="not-ready")
    def not_ready(self, request, pk=None):
        """Get pending/hold payroll slips with filtering and search."""
        period = self.get_object()

        if period.status == SalaryPeriod.Status.ONGOING:
            # Get all PENDING/HOLD slips from this and previous periods
            slips = PayrollSlip.objects.filter(
                salary_period__month__lte=period.month,
                status__in=[PayrollSlip.Status.PENDING, PayrollSlip.Status.HOLD],
            ).select_related("employee", "salary_period")
        else:
            # Period is COMPLETED - get only PENDING/HOLD slips from this period
            slips = period.payroll_slips.filter(
                status__in=[PayrollSlip.Status.PENDING, PayrollSlip.Status.HOLD]
            ).select_related("employee", "salary_period")

        # Apply search filter
        search = request.query_params.get("search")
        if search:
            from django.db.models import Q

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

        has_unpaid_penalty = request.query_params.get("has_unpaid_penalty")
        if has_unpaid_penalty is not None:
            slips = slips.filter(has_unpaid_penalty=has_unpaid_penalty.lower() == "true")

        # Apply ordering
        ordering = request.query_params.get("ordering", "-calculated_at")
        slips = slips.order_by(ordering)

        from apps.payroll.api.serializers import PayrollSlipListSerializer

        page = self.paginate_queryset(slips)
        if page is not None:
            serializer = PayrollSlipListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = PayrollSlipListSerializer(slips, many=True)
        return Response(serializer.data)
