"""ViewSet for SalaryPeriod model."""

from django.db.models import Count, Q, Sum
from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.payroll.api.serializers import (
    SalaryPeriodCreateSerializer,
    SalaryPeriodListSerializer,
    SalaryPeriodSerializer,
    SalaryPeriodStatisticsSerializer,
)
from apps.payroll.models import PayrollSlip, SalaryPeriod
from libs import BaseModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter


@extend_schema_view(
    list=extend_schema(
        summary="List all salary periods",
        description="Retrieve a paginated list of salary periods with filtering and ordering support",
        tags=["10.5: Salary Periods"],
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
        description="Retrieve detailed information about a specific salary period including config snapshot",
        tags=["10.5: Salary Periods"],
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
        summary="Create a new salary period",
        description="Create a new salary period for a specific month. Automatically snapshots current salary config.",
        tags=["10.5: Salary Periods"],
        examples=[
            OpenApiExample(
                "Request - Create salary period",
                value={"month": "2024-01-01"},
                request_only=True,
            ),
            OpenApiExample(
                "Success - Created salary period",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "SP-202401",
                        "month": "2024-01-01",
                        "salary_config_snapshot": {},
                        "status": "ONGOING",
                        "standard_working_days": "23.00",
                        "total_employees": 0,
                        "completed_at": None,
                        "completed_by": None,
                        "created_at": "2024-01-01T00:00:00Z",
                        "updated_at": "2024-01-01T00:00:00Z",
                        "created_by": None,
                        "updated_by": None,
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["201"],
            ),
        ],
    ),
)
class SalaryPeriodViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for managing salary periods.
    
    Provides CRUD operations and custom actions for salary period management:
    - List, create, retrieve salary periods
    - Get period statistics
    - Recalculate all payroll slips in period
    - Complete period (mark as finished)
    - Send email notifications
    """
    
    queryset = SalaryPeriod.objects.all()
    serializer_class = SalaryPeriodSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter, PhraseSearchFilter]
    filterset_fields = ["status", "month"]
    ordering_fields = ["month", "created_at", "total_employees"]
    ordering = ["-month"]
    search_fields = ["code"]
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == "list":
            return SalaryPeriodListSerializer
        elif self.action == "create":
            return SalaryPeriodCreateSerializer
        elif self.action == "statistics":
            return SalaryPeriodStatisticsSerializer
        return SalaryPeriodSerializer
    
    @extend_schema(
        summary="Get salary period statistics",
        description="Get statistical summary of payroll slips in this period",
        tags=["10.5: Salary Periods"],
        responses={200: SalaryPeriodStatisticsSerializer},
        examples=[
            OpenApiExample(
                "Success - Period statistics",
                value={
                    "success": True,
                    "data": {
                        "pending_count": 5,
                        "ready_count": 40,
                        "hold_count": 3,
                        "delivered_count": 2,
                        "total_gross_income": 5000000000,
                        "total_net_salary": 3800000000,
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    )
    @action(detail=True, methods=["get"])
    def statistics(self, request, pk=None):
        """Get statistics for this salary period."""
        period = self.get_object()
        
        # Count by status
        stats = period.payroll_slips.aggregate(
            pending_count=Count("id", filter=Q(status=PayrollSlip.Status.PENDING)),
            ready_count=Count("id", filter=Q(status=PayrollSlip.Status.READY)),
            hold_count=Count("id", filter=Q(status=PayrollSlip.Status.HOLD)),
            delivered_count=Count("id", filter=Q(status=PayrollSlip.Status.DELIVERED)),
            total_gross_income=Sum("gross_income"),
            total_net_salary=Sum("net_salary"),
        )
        
        serializer = SalaryPeriodStatisticsSerializer(stats)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Recalculate all payroll slips",
        description="Trigger recalculation for all payroll slips in this period",
        tags=["10.5: Salary Periods"],
        examples=[
            OpenApiExample(
                "Success - Recalculation started",
                value={
                    "success": True,
                    "data": {
                        "message": "Recalculation started for 50 payroll slips"
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    )
    @action(detail=True, methods=["post"])
    def recalculate(self, request, pk=None):
        """Recalculate all payroll slips in this period."""
        period = self.get_object()
        
        # Import here to avoid circular import
        from apps.payroll.services.payroll_calculation import PayrollCalculationService
        
        # Get all slips in this period
        slips = period.payroll_slips.all()
        
        for slip in slips:
            calculator = PayrollCalculationService(slip)
            calculator.calculate()
        
        return Response({
            "message": f"Recalculation started for {slips.count()} payroll slips"
        })
    
    @extend_schema(
        summary="Complete salary period",
        description="Mark period as completed and set all READY slips to DELIVERED",
        tags=["10.5: Salary Periods"],
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
        
        if not period.can_complete():
            return Response(
                {"error": _("Cannot complete period with pending or hold payroll slips")},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Complete the period
        period.complete(user=request.user)
        
        return Response({
            "id": period.id,
            "status": period.status,
            "completed_at": period.completed_at,
            "delivered_count": period.payroll_slips.filter(status=PayrollSlip.Status.DELIVERED).count(),
        })
    
    @extend_schema(
        summary="Send email notifications",
        description="Send payroll slip emails to employees",
        tags=["10.5: Salary Periods"],
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
        
        return Response({
            "sent_count": slips.count(),
            "failed_count": 0,
            "failed_emails": [],
        })
