"""ViewSet for penalty ticket management."""

from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.core.api.permissions import RoleBasedPermission
from apps.payroll.api.filtersets import PenaltyTicketFilterSet
from apps.payroll.api.serializers import (
    BulkUpdateStatusSerializer,
    PenaltyTicketSerializer,
    PenaltyTicketUpdateSerializer,
)
from apps.payroll.models import PenaltyTicket
from libs import BaseModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter


@extend_schema_view(
    list=extend_schema(
        summary="List penalty tickets",
        description="Retrieve a paginated list of penalty tickets (uniform violations) with filtering and search support.",
        tags=["10.3: Penalty Management"],
        examples=[
            OpenApiExample(
                "Success - Penalty ticket list",
                value={
                    "success": True,
                    "data": {
                        "count": 1,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": "550e8400-e29b-41d4-a716-446655440000",
                                "code": "RVF-202511-0001",
                                "month": "11/2025",
                                "employee_id": 123,
                                "employee_code": "E0001",
                                "employee_name": "John Doe",
                                "violation_count": 1,
                                "violation_type": "UNDER_10_MINUTES",
                                "amount": 100000,
                                "status": "UNPAID",
                                "note": "Uniform violation - missing name tag",
                                "payment_date": "2025-11-20",
                                "attachments": [],
                                "created_at": "2025-11-15T10:00:00Z",
                                "updated_at": "2025-11-15T10:00:00Z",
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
        summary="Get penalty ticket details",
        description="Retrieve detailed information about a specific penalty ticket.",
        tags=["10.3: Penalty Management"],
        examples=[
            OpenApiExample(
                "Success - Penalty ticket detail",
                value={
                    "success": True,
                    "data": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "code": "RVF-202511-0001",
                        "month": "11/2025",
                        "employee_id": 123,
                        "employee_code": "E0001",
                        "employee_name": "John Doe",
                        "violation_count": 1,
                        "violation_type": "UNDER_10_MINUTES",
                        "amount": 100000,
                        "status": "UNPAID",
                        "note": "Uniform violation",
                        "attachments": [],
                        "payment_date": "2025-11-20",
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    ),
    create=extend_schema(
        summary="Create penalty ticket",
        description="Create a new penalty ticket for uniform violation. Automatically generates ticket code.",
        tags=["10.3: Penalty Management"],
        request=PenaltyTicketSerializer,
        responses={201: PenaltyTicketSerializer},
        examples=[
            OpenApiExample(
                "Request - Create ticket",
                value={
                    "month": "11/2025",
                    "employee_id": 123,
                    "violation_count": 1,
                    "violation_type": "UNDER_10_MINUTES",
                    "amount": 100000,
                    "status": "UNPAID",
                    "note": "Uniform violation - missing name tag",
                    "files": {
                        "attachments": [
                            "token_123",
                            "token_456",
                        ]
                    },
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success - Ticket created",
                value={
                    "success": True,
                    "data": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "code": "RVF-202511-0001",
                        "month": "11/2025",
                        "employee_id": 123,
                        "employee_code": "E0001",
                        "employee_name": "John Doe",
                        "violation_count": 1,
                        "violation_type": "UNDER_10_MINUTES",
                        "amount": 100000,
                        "status": "UNPAID",
                        "note": "Uniform violation - missing name tag",
                        "attachments": [],
                        "payment_date": "2025-11-20",
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["201"],
            ),
            OpenApiExample(
                "Error - Validation failed",
                value={
                    "success": False,
                    "data": None,
                    "error": {
                        "amount": ["Amount must be greater than 0"],
                        "month": [
                            "Month must be in MM/YYYY format. Error: invalid literal for int() with base 10: 'ab'"
                        ],
                    },
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    update=extend_schema(
        summary="Update penalty ticket",
        description="Update an existing penalty ticket. Code field is immutable.",
        tags=["10.3: Penalty Management"],
    ),
    partial_update=extend_schema(
        summary="Partially update penalty ticket",
        description="Partially update an existing penalty ticket.",
        tags=["10.3: Penalty Management"],
    ),
    destroy=extend_schema(
        summary="Delete penalty ticket",
        description="Delete a penalty ticket.",
        tags=["10.3: Penalty Management"],
        examples=[
            OpenApiExample(
                "Success - Ticket deleted",
                value={"success": True, "data": None, "error": None},
                response_only=True,
                status_codes=["204"],
            ),
        ],
    ),
)
class PenaltyTicketViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for managing penalty tickets (uniform violations).

    Provides full CRUD operations for penalty tickets.
    """

    queryset = PenaltyTicket.objects.all()
    serializer_class = PenaltyTicketSerializer
    permission_classes = [RoleBasedPermission]
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    filterset_class = PenaltyTicketFilterSet
    search_fields = ["code", "employee_code", "employee_name"]
    ordering_fields = ["created_at", "month", "amount", "status"]
    ordering = ["-created_at"]
    module = _("Payroll")
    submodule = _("Penalty Management")
    permission_prefix = "payroll.penalty_ticket"

    PERMISSION_REGISTERED_ACTIONS = {
        "bulk_update_status": {
            "name_template": _("Bulk Update Penalty Ticket Status"),
            "description_template": _("Bulk update payment status for penalty tickets"),
        },
    }

    def get_serializer_class(self):
        """Use different serializer for update operations."""
        if self.action in ["update", "partial_update"]:
            return PenaltyTicketUpdateSerializer
        return PenaltyTicketSerializer

    def get_queryset(self):
        """Override to optimize queries with select_related."""
        return (
            super()
            .get_queryset()
            .select_related("employee", "created_by", "updated_by")
            .prefetch_related("attachments")
        )

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        serializer.save(created_by=user, updated_by=user)

    def perform_update(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        serializer.save(updated_by=user)

    @extend_schema(
        summary="Update payment status for penalty tickets",
        description="Mark one or multiple penalty tickets as paid or unpaid.",
        tags=["10.3: Penalty Management"],
        request=BulkUpdateStatusSerializer,
        examples=[
            OpenApiExample(
                "Mark tickets as paid",
                value={"ids": [1, 2, 3], "status": PenaltyTicket.Status.PAID},
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={"success": True, "data": {"updated_count": 3}, "error": None},
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Error - Ticket not found",
                value={"success": False, "data": None, "error": {"ids": ["Tickets not found: [99]"]}},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    @action(detail=False, methods=["post"], url_path="bulk-update-status")
    def bulk_update_status(self, request, *args, **kwargs):
        """Bulk update payment status for penalty tickets."""
        serializer = BulkUpdateStatusSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        if not self.request.user.is_authenticated:
            return Response(
                {"detail": _("Authentication credentials were not provided.")},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        counter = serializer.bulk_update_status()

        return Response(
            {"updated_count": counter},
            status=status.HTTP_200_OK,
        )
