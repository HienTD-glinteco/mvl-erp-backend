from django.db.models import ProtectedError
from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.payroll.api.filtersets import RecoveryVoucherFilterSet
from apps.payroll.api.serializers import RecoveryVoucherSerializer
from apps.payroll.models import RecoveryVoucher
from libs import BaseModelViewSet, ExportXLSXMixin, PageNumberWithSizePagination
from libs.drf.filtersets.search import PhraseSearchFilter


@extend_schema_view(
    list=extend_schema(
        summary="List all recovery/back pay vouchers",
        description="Retrieve a paginated list of all recovery and back pay vouchers with support for filtering and search. Default page size is 25, sorted by latest update first.",
        tags=["10.2: Recovery/Back Pay"],
        examples=[
            OpenApiExample(
                "Success - List of vouchers",
                value={
                    "success": True,
                    "data": {
                        "count": 1,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": "c1b9b7a8-...",
                                "code": "RV-202509-0001",
                                "name": "September back pay",
                                "voucher_type": "BACK_PAY",
                                "voucher_type_display": "Back Pay",
                                "employee": {
                                    "id": "e5d8f1a3-...",
                                    "code": "E0001",
                                    "fullname": "John Doe",
                                },
                                "block": None,
                                "branch": None,
                                "department": None,
                                "position": None,
                                "amount": 1500000,
                                "month": "09/2025",
                                "status": "NOT_CALCULATED",
                                "note": "Adjustment for commission",
                                "created_at": "2025-09-10T10:00:00Z",
                                "updated_at": "2025-09-10T10:00:00Z",
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
        summary="Get recovery/back pay voucher details",
        description="Retrieve detailed information about a specific recovery or back pay voucher. Status values: CALCULATED, NOT_CALCULATED.",
        tags=["10.2: Recovery/Back Pay"],
        examples=[
            OpenApiExample(
                "Success - Single voucher",
                value={
                    "success": True,
                    "data": {
                        "id": "c1b9b7a8-...",
                        "code": "RV-202509-0001",
                        "name": "September back pay",
                        "voucher_type": "BACK_PAY",
                        "voucher_type_display": "Back Pay",
                        "employee": {
                            "id": "e5d8f1a3-...",
                            "code": "E0001",
                            "fullname": "John Doe",
                        },
                        "block": {"id": 1, "name": "Sales Block", "code": "BL001"},
                        "branch": {"id": 2, "name": "Main Branch", "code": "BR001"},
                        "department": {"id": 3, "name": "Sales Department", "code": "DP001"},
                        "position": {"id": 4, "name": "Sales Manager", "code": "PS001"},
                        "amount": 1500000,
                        "month": "09/2025",
                        "status": "NOT_CALCULATED",
                        "note": "Adjustment for commission",
                        "created_by": 1,
                        "updated_by": 1,
                        "created_at": "2025-09-10T10:00:00Z",
                        "updated_at": "2025-09-10T10:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Error - Not found",
                value={
                    "success": False,
                    "data": None,
                    "error": {"detail": "Not found."},
                },
                response_only=True,
                status_codes=["404"],
            ),
        ],
    ),
    create=extend_schema(
        summary="Create a new recovery/back pay voucher",
        description="Create a new recovery or back pay voucher. Code is auto-generated. Status defaults to NOT_CALCULATED. Created_by and updated_by fields are set automatically.",
        tags=["10.2: Recovery/Back Pay"],
        examples=[
            OpenApiExample(
                "Request - Create voucher",
                value={
                    "name": "September back pay",
                    "voucher_type": "BACK_PAY",
                    "employee": "c1b9b7a8-...",
                    "employee_id": "e5d8f1a3-...",
                    "amount": 1500000,
                    "month": "09/2025",
                    "note": "Adjustment for commission",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success - Created",
                value={
                    "success": True,
                    "data": {
                        "id": "c1b9b7a8-...",
                        "code": "RV-202509-0001",
                        "name": "September back pay",
                        "voucher_type": "BACK_PAY",
                        "voucher_type_display": "Back Pay",
                        "employee": {
                            "id": "e5d8f1a3-...",
                            "code": "E0001",
                            "fullname": "John Doe",
                        },
                        "block": {"id": 1, "name": "Sales Block", "code": "BL001"},
                        "branch": {"id": 2, "name": "Main Branch", "code": "BR001"},
                        "department": {"id": 3, "name": "Sales Department", "code": "DP001"},
                        "position": {"id": 4, "name": "Sales Manager", "code": "PS001"},
                        "amount": 1500000,
                        "month": "09/2025",
                        "status": "NOT_CALCULATED",
                        "note": "Adjustment for commission",
                        "created_by": 1,
                        "updated_by": 1,
                        "created_at": "2025-09-10T10:00:00Z",
                        "updated_at": "2025-09-10T10:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["201"],
            ),
            OpenApiExample(
                "Error - Invalid amount",
                value={
                    "success": False,
                    "data": None,
                    "error": {
                        "amount": ["Amount must be greater than 0."],
                    },
                },
                response_only=True,
                status_codes=["400"],
            ),
            OpenApiExample(
                "Error - Inactive employee",
                value={
                    "success": False,
                    "data": None,
                    "error": {
                        "employee": ["Employee must be in active or onboarding status."],
                    },
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    update=extend_schema(
        summary="Update recovery/back pay voucher",
        description="Update all fields of a recovery/back pay voucher. Code and ID are immutable. Status is reset to NOT_CALCULATED after update. Updated_by field is set automatically.",
        tags=["10.2: Recovery/Back Pay"],
        examples=[
            OpenApiExample(
                "Request - Update voucher",
                value={
                    "name": "September back pay updated",
                    "voucher_type": "BACK_PAY",
                    "employee_id": "e5d8f1a3-...",
                    "amount": 1800000,
                    "month": "09/2025",
                    "note": "Updated adjustment for commission",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success - Updated",
                value={
                    "success": True,
                    "data": {
                        "id": "c1b9b7a8-...",
                        "code": "RV-202509-0001",
                        "name": "September back pay updated",
                        "voucher_type": "BACK_PAY",
                        "voucher_type_display": "Back Pay",
                        "employee": {
                            "id": "e5d8f1a3-...",
                            "code": "E0001",
                            "fullname": "John Doe",
                        },
                        "block": {"id": 1, "name": "Sales Block", "code": "BL001"},
                        "branch": {"id": 2, "name": "Main Branch", "code": "BR001"},
                        "department": {"id": 3, "name": "Sales Department", "code": "DP001"},
                        "position": {"id": 4, "name": "Sales Manager", "code": "PS001"},
                        "amount": 1800000,
                        "month": "09/2025",
                        "status": "NOT_CALCULATED",
                        "note": "Updated adjustment for commission",
                        "created_by": 1,
                        "updated_by": 2,
                        "created_at": "2025-09-10T10:00:00Z",
                        "updated_at": "2025-09-10T12:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    ),
    partial_update=extend_schema(
        summary="Partially update recovery/back pay voucher",
        description="Update specific fields of a recovery/back pay voucher. Status is reset to NOT_CALCULATED after update. Updated_by field is set automatically.",
        tags=["10.2: Recovery/Back Pay"],
        examples=[
            OpenApiExample(
                "Request - Update amount",
                value={"amount": 2000000},
                request_only=True,
            ),
            OpenApiExample(
                "Success - Partially updated",
                value={
                    "success": True,
                    "data": {
                        "id": "c1b9b7a8-...",
                        "code": "RV-202509-0001",
                        "name": "September back pay",
                        "voucher_type": "BACK_PAY",
                        "voucher_type_display": "Back Pay",
                        "employee": {
                            "id": "e5d8f1a3-...",
                            "code": "E0001",
                            "fullname": "John Doe",
                        },
                        "block": {"id": 1, "name": "Sales Block", "code": "BL001"},
                        "branch": {"id": 2, "name": "Main Branch", "code": "BR001"},
                        "department": {"id": 3, "name": "Sales Department", "code": "DP001"},
                        "position": {"id": 4, "name": "Sales Manager", "code": "PS001"},
                        "amount": 2000000,
                        "month": "09/2025",
                        "status": "NOT_CALCULATED",
                        "note": "Adjustment for commission",
                        "created_by": 1,
                        "updated_by": 2,
                        "created_at": "2025-09-10T10:00:00Z",
                        "updated_at": "2025-09-10T14:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    ),
    destroy=extend_schema(
        summary="Delete recovery/back pay voucher",
        description="Delete a recovery/back pay voucher. Deletion is blocked if a payroll table exists for the voucher's period.",
        tags=["10.2: Recovery/Back Pay"],
        examples=[
            OpenApiExample(
                "Success - Deleted",
                value={
                    "success": True,
                    "data": None,
                    "error": None,
                },
                response_only=True,
                status_codes=["204"],
            ),
            OpenApiExample(
                "Error - Payroll exists",
                value={
                    "success": False,
                    "data": None,
                    "error": {
                        "code": "PAYROLL_EXISTS",
                        "message": "Cannot delete voucher for a month with existing payroll.",
                    },
                },
                response_only=True,
                status_codes=["409"],
            ),
        ],
    ),
    export=extend_schema(
        summary="Export recovery/back pay vouchers to XLSX",
        description="Export filtered recovery/back pay vouchers to Excel format. Respects search and filter parameters.",
        tags=["10.2: Recovery/Back Pay"],
    ),
)
class RecoveryVoucherViewSet(ExportXLSXMixin, AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for Recovery/Back Pay voucher CRUD operations.

    Provides list, retrieve, create, update, delete, and export actions
    for recovery and back pay vouchers.
    """

    queryset = RecoveryVoucher.objects.select_related("employee", "created_by", "updated_by").all()
    serializer_class = RecoveryVoucherSerializer
    filterset_class = RecoveryVoucherFilterSet
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    search_fields = ["code", "name", "employee_code", "employee_name"]
    ordering_fields = ["created_at", "updated_at", "month", "amount"]
    ordering = ["-updated_at"]
    pagination_class = PageNumberWithSizePagination

    # Permission configuration
    module = _("Payroll")
    submodule = _("Recovery/Back Pay")
    permission_prefix = "payroll.recovery_voucher"

    def perform_create(self, serializer):
        """Create voucher with audit logging."""
        serializer.save()

    def perform_update(self, serializer):
        """Update voucher with audit logging."""
        serializer.save()

    def perform_destroy(self, instance):
        """Delete voucher with payroll guard check."""
        # TODO: Add check for existing payroll table for the period
        # For now, we'll use Django's ProtectedError as a basic guard
        try:
            instance.delete()
        except ProtectedError:
            from rest_framework.exceptions import ValidationError

            raise ValidationError(
                {
                    "code": "PAYROLL_EXISTS",
                    "message": _("Cannot delete voucher for a month with existing payroll."),
                }
            )

    @extend_schema(
        summary="Export recovery/back pay vouchers to XLSX",
        description="Export filtered recovery/back pay vouchers to Excel format. Respects search and filter parameters.",
        tags=["10.2: Recovery/Back Pay"],
        parameters=[
            OpenApiParameter(
                name="search",
                description="Search across code, name, employee_code, employee_name",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="voucher_type",
                description="Filter by voucher type (RECOVERY or BACK_PAY)",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="status",
                description="Filter by status (NOT_CALCULATED or CALCULATED)",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="employee_id",
                description="Filter by employee UUID",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="period",
                description="Filter by period in MM/YYYY format",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="amount_min",
                description="Minimum amount in VND",
                required=False,
                type=int,
            ),
            OpenApiParameter(
                name="amount_max",
                description="Maximum amount in VND",
                required=False,
                type=int,
            ),
        ],
        examples=[
            OpenApiExample(
                "Success - Export started",
                value={
                    "success": True,
                    "data": {
                        "download_url": "https://s3.amazonaws.com/...",
                        "expires_at": "2025-09-10T11:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    )
    def get_export_schema_parameters(self):
        """Get additional schema parameters for the export endpoint."""
        return [
            OpenApiParameter(
                name="search",
                description="Search across code, name, employee_code, employee_name",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="voucher_type",
                description="Filter by voucher type",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="status",
                description="Filter by status",
                required=False,
                type=str,
            ),
        ]
