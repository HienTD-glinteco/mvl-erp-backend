"""ViewSet for PayrollSlip model."""

from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.payroll.api.filtersets import PayrollSlipFilterSet
from apps.payroll.api.serializers import (
    PayrollSlipExportSerializer,
    PayrollSlipHoldSerializer,
    PayrollSlipSerializer,
    PayrollSlipStatusUpdateSerializer,
)
from apps.payroll.models import PayrollSlip
from libs import BaseReadOnlyModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter
from libs.export_xlsx import ExportXLSXMixin


@extend_schema_view(
    list=extend_schema(
        summary="List all payroll slips",
        description="Retrieve a paginated list of payroll slips with filtering and search support",
        tags=["10.7: Payroll Slips"],
        examples=[
            OpenApiExample(
                "Success - List of payroll slips",
                value={
                    "success": True,
                    "data": {
                        "count": 50,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": 1,
                                "code": "PS-202401-0001",
                                "salary_period": {
                                    "id": 1,
                                    "code": "SP-202401",
                                    "month": "2024-01-01",
                                    "status": "ONGOING",
                                },
                                "employee": {
                                    "id": 101,
                                    "code": "NV001",
                                    "fullname": "John Doe",
                                },
                                "employee_code": "NV001",
                                "employee_name": "John Doe",
                                "department_name": "Sales",
                                "position_name": "Sales Manager",
                                "gross_income": 50000000,
                                "net_salary": 38000000,
                                "status": "READY",
                                "has_unpaid_penalty": False,
                                "unpaid_penalty_count": 0,
                                "need_resend_email": False,
                                "calculated_at": "2024-01-15T10:00:00Z",
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
        summary="Get payroll slip details",
        description="Retrieve detailed calculation breakdown for a specific payroll slip",
        tags=["10.7: Payroll Slips"],
        examples=[
            OpenApiExample(
                "Success - Single payroll slip",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "PS-202401-0001",
                        "employee_code": "NV001",
                        "employee_name": "John Doe",
                        "base_salary": 20000000,
                        "kpi_bonus": 2000000,
                        "business_progressive_salary": 7000000,
                        "overtime_pay": 3000000,
                        "total_travel_expense": 5000000,
                        "gross_income": 50000000,
                        "employee_social_insurance": 1600000,
                        "personal_income_tax": 8000000,
                        "net_salary": 38000000,
                        "status": "READY",
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    ),
    export=extend_schema(
        tags=["10.7: Payroll Slips"],
    ),
)
class PayrollSlipViewSet(ExportXLSXMixin, AuditLoggingMixin, BaseReadOnlyModelViewSet):
    """ViewSet for managing payroll slips.

    Provides CRUD operations and custom actions for payroll slip management:
    - List, retrieve payroll slips
    - Recalculate individual slip
    - Hold/release slip
    - Change status (ready, deliver)
    """

    queryset = PayrollSlip.objects.select_related(
        "employee", "salary_period", "delivered_by", "created_by", "updated_by"
    ).all()
    serializer_class = PayrollSlipSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter, PhraseSearchFilter]
    filterset_class = PayrollSlipFilterSet
    ordering_fields = [
        "code",
        "employee_code",
        "employee_name",
        "gross_income",
        "net_salary",
        "calculated_at",
        "created_at",
    ]
    ordering = ["-calculated_at"]
    search_fields = ["employee_code", "employee_name", "code"]

    # Permission registration attributes
    module = "Payroll"
    submodule = "Payroll Slips"
    permission_prefix = "payroll_slip"

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == "hold":
            return PayrollSlipHoldSerializer
        elif self.action in ["ready", "deliver"]:
            return PayrollSlipStatusUpdateSerializer
        elif self.action == "export":
            return PayrollSlipExportSerializer
        return PayrollSlipSerializer

    def get_export_data(self, request):
        """Generate export data with flattened nested objects."""
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)

        headers = [str(field.label) for field in serializer.child.fields.values()]
        data = serializer.data
        field_names = list(serializer.child.fields.keys())

        return {
            "sheets": [
                {
                    "name": "Payroll Slips",
                    "headers": headers,
                    "field_names": field_names,
                    "data": data,
                }
            ]
        }

    @extend_schema(
        summary="Recalculate payroll slip",
        description="Recalculate salary for this payroll slip based on current data",
        tags=["10.7: Payroll Slips"],
        examples=[
            OpenApiExample(
                "Success - Recalculated",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "net_salary": 38500000,
                        "changed": True,
                        "need_resend_email": True,
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
        """Recalculate this payroll slip."""
        slip = self.get_object()

        # Store old net salary for comparison
        old_net_salary = slip.net_salary

        # Import here to avoid circular import
        from apps.payroll.services.payroll_calculation import PayrollCalculationService

        calculator = PayrollCalculationService(slip)
        calculator.calculate()

        # Check if changed
        changed = old_net_salary != slip.net_salary
        if changed:
            slip.need_resend_email = True
            slip.save(update_fields=["need_resend_email"])

        return Response(
            {
                "id": slip.id,
                "net_salary": slip.net_salary,
                "changed": changed,
                "need_resend_email": slip.need_resend_email,
            }
        )

    @extend_schema(
        summary="Hold payroll slip",
        description="Put payroll slip on hold with a reason",
        tags=["10.7: Payroll Slips"],
        request=PayrollSlipHoldSerializer,
        responses={200: PayrollSlipStatusUpdateSerializer},
        examples=[
            OpenApiExample(
                "Request - Hold slip",
                value={"reason": "Pending verification"},
                request_only=True,
            ),
            OpenApiExample(
                "Success - Slip on hold",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "status": "HOLD",
                        "status_note": "Pending verification",
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    )
    @action(detail=True, methods=["post"])
    def hold(self, request, pk=None):
        """Hold the payroll slip."""
        slip = self.get_object()
        serializer = PayrollSlipHoldSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        slip.status = PayrollSlip.Status.HOLD
        slip.status_note = serializer.validated_data["reason"]
        slip.save(update_fields=["status", "status_note", "updated_at"])

        response_serializer = PayrollSlipStatusUpdateSerializer(
            {
                "id": slip.id,
                "status": slip.status,
                "status_note": slip.status_note,
            }
        )
        return Response(response_serializer.data)

    @extend_schema(
        summary="Mark payroll slip as ready",
        description="Change slip status from HOLD to READY",
        tags=["10.7: Payroll Slips"],
        responses={200: PayrollSlipStatusUpdateSerializer},
        examples=[
            OpenApiExample(
                "Success - Slip ready",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "status": "READY",
                        "status_note": "",
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    )
    @action(detail=True, methods=["post"])
    def ready(self, request, pk=None):
        """Mark the payroll slip as ready."""
        slip = self.get_object()

        # Can only change to READY from HOLD or if already READY
        if slip.status not in [PayrollSlip.Status.HOLD, PayrollSlip.Status.READY]:
            return Response({"error": _("Can only mark HOLD slips as READY")}, status=status.HTTP_400_BAD_REQUEST)

        # Check if has unpaid penalties
        if slip.has_unpaid_penalty:
            return Response(
                {"error": _("Cannot mark as READY - employee has unpaid penalty tickets")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        slip.status = PayrollSlip.Status.READY
        slip.status_note = ""
        slip.save(update_fields=["status", "status_note", "updated_at"])

        response_serializer = PayrollSlipStatusUpdateSerializer(
            {
                "id": slip.id,
                "status": slip.status,
                "status_note": slip.status_note,
            }
        )
        return Response(response_serializer.data)

    @extend_schema(
        summary="Deliver payroll slip",
        description="Mark slip as delivered to accounting",
        tags=["10.7: Payroll Slips"],
        responses={200: PayrollSlipStatusUpdateSerializer},
        examples=[
            OpenApiExample(
                "Success - Slip delivered",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "status": "DELIVERED",
                        "status_note": "",
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    )
    @action(detail=True, methods=["post"])
    def deliver(self, request, pk=None):
        """Mark the payroll slip as delivered."""
        from django.utils import timezone

        slip = self.get_object()

        # Can only deliver READY slips
        if slip.status != PayrollSlip.Status.READY:
            return Response({"error": _("Can only deliver READY slips")}, status=status.HTTP_400_BAD_REQUEST)

        slip.status = PayrollSlip.Status.DELIVERED
        slip.delivered_at = timezone.now()
        slip.delivered_by = request.user
        slip.save(update_fields=["status", "delivered_at", "delivered_by", "updated_at"])

        response_serializer = PayrollSlipStatusUpdateSerializer(
            {
                "id": slip.id,
                "status": slip.status,
                "status_note": slip.status_note,
            }
        )
        return Response(response_serializer.data)
