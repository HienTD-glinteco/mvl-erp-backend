from django.db.models import ProtectedError
from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.imports.api.mixins import AsyncImportProgressMixin
from apps.payroll.api.filtersets import SalesRevenueFilterSet
from apps.payroll.api.serializers import SalesRevenueSerializer
from apps.payroll.models import SalesRevenue
from libs import BaseModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter
from libs.export_xlsx.mixins import ExportXLSXMixin


@extend_schema_view(
    list=extend_schema(
        summary="List all sales revenues",
        description="Retrieve a paginated list of sales revenues with support for filtering and search. Shows latest version only, sorted by newest created. Default page size is 25 rows. Displays by current period by default.",
        tags=["10.5: Sales Revenue Management"],
        examples=[
            OpenApiExample(
                "Success - List of sales revenues",
                value={
                    "success": True,
                    "data": {
                        "count": 2,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": 1,
                                "code": "SR-202511-0001",
                                "employee": {
                                    "id": 101,
                                    "code": "MV000000101",
                                    "fullname": "Nguyen Van A",
                                },
                                "block": {"id": 1, "name": "Sales Block", "code": "BL001"},
                                "branch": {"id": 1, "name": "Hanoi Branch", "code": "HN"},
                                "department": {"id": 1, "name": "Sales Department", "code": "SALES"},
                                "position": {"id": 1, "name": "Sales Manager", "code": "SM"},
                                "revenue": 150000000,
                                "transaction_count": 12,
                                "month": "11/2025",
                                "status": "NOT_CALCULATED",
                                "created_by": 1,
                                "updated_by": None,
                                "created_at": "2025-11-15T10:00:00Z",
                                "updated_at": "2025-11-15T10:00:00Z",
                            },
                            {
                                "id": 2,
                                "code": "SR-202511-0002",
                                "employee": {
                                    "id": 102,
                                    "code": "MV000000102",
                                    "fullname": "Tran Thi B",
                                },
                                "block": {"id": 1, "name": "Sales Block", "code": "BL001"},
                                "branch": {"id": 1, "name": "Hanoi Branch", "code": "HN"},
                                "department": {"id": 1, "name": "Sales Department", "code": "SALES"},
                                "position": {"id": 2, "name": "Sales Executive", "code": "SE"},
                                "revenue": 200000000,
                                "transaction_count": 18,
                                "month": "11/2025",
                                "status": "CALCULATED",
                                "created_by": 1,
                                "updated_by": None,
                                "created_at": "2025-11-14T10:00:00Z",
                                "updated_at": "2025-11-14T10:00:00Z",
                            },
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
        summary="Get sales revenue details",
        description="Retrieve detailed information about a specific sales revenue record. Shows all fields with current values.",
        tags=["10.5: Sales Revenue Management"],
        examples=[
            OpenApiExample(
                "Success - Single sales revenue",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "SR-202511-0001",
                        "employee": {
                            "id": 101,
                            "code": "MV000000101",
                            "fullname": "Nguyen Van A",
                        },
                        "block": {"id": 1, "name": "Sales Block", "code": "BL001"},
                        "branch": {"id": 1, "name": "Hanoi Branch", "code": "HN"},
                        "department": {"id": 1, "name": "Sales Department", "code": "SALES"},
                        "position": {"id": 1, "name": "Sales Manager", "code": "SM"},
                        "revenue": 150000000,
                        "transaction_count": 12,
                        "month": "11/2025",
                        "status": "NOT_CALCULATED",
                        "created_by": 1,
                        "updated_by": None,
                        "created_at": "2025-11-15T10:00:00Z",
                        "updated_at": "2025-11-15T10:00:00Z",
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
        summary="Create a new sales revenue",
        description="Create a new sales revenue record. Code is auto-generated in format SR-{YYYYMM}-{seq}. Status defaults to NOT_CALCULATED. Month must be in MM/YYYY format. Employee must be active. Each employee can only have one revenue record per month.",
        tags=["10.5: Sales Revenue Management"],
        examples=[
            OpenApiExample(
                "Request - Create sales revenue",
                value={
                    "employee_id": 101,
                    "revenue": 150000000,
                    "transaction_count": 12,
                    "month": "11/2025",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success - Created",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "SR-202511-0001",
                        "employee": {
                            "id": 101,
                            "code": "MV000000101",
                            "fullname": "Nguyen Van A",
                        },
                        "block": {"id": 1, "name": "Sales Block", "code": "BL001"},
                        "branch": {"id": 1, "name": "Hanoi Branch", "code": "HN"},
                        "department": {"id": 1, "name": "Sales Department", "code": "SALES"},
                        "position": {"id": 1, "name": "Sales Manager", "code": "SM"},
                        "revenue": 150000000,
                        "transaction_count": 12,
                        "month": "11/2025",
                        "status": "NOT_CALCULATED",
                        "created_by": 1,
                        "updated_by": None,
                        "created_at": "2025-11-15T10:00:00Z",
                        "updated_at": "2025-11-15T10:00:00Z",
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
                        "revenue": ["Revenue must be non-negative"],
                        "month": ["Month must be in MM/YYYY format (e.g., 11/2025)"],
                    },
                },
                response_only=True,
                status_codes=["400"],
            ),
            OpenApiExample(
                "Error - Duplicate record",
                value={
                    "success": False,
                    "data": None,
                    "error": {"non_field_errors": ["Sales revenue for this employee and month already exists"]},
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    update=extend_schema(
        summary="Update sales revenue",
        description="Update all fields of a sales revenue. Code is immutable. Status is automatically reset to NOT_CALCULATED on update. Changes are saved in audit history.",
        tags=["10.5: Sales Revenue Management"],
        examples=[
            OpenApiExample(
                "Request - Update sales revenue",
                value={
                    "employee_id": 101,
                    "revenue": 180000000,
                    "transaction_count": 15,
                    "month": "11/2025",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success - Updated",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "SR-202511-0001",
                        "employee": {
                            "id": 101,
                            "code": "MV000000101",
                            "fullname": "Nguyen Van A",
                        },
                        "revenue": 180000000,
                        "transaction_count": 15,
                        "month": "11/2025",
                        "status": "NOT_CALCULATED",
                        "created_by": 1,
                        "updated_by": 2,
                        "created_at": "2025-11-15T10:00:00Z",
                        "updated_at": "2025-11-15T12:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    ),
    partial_update=extend_schema(
        summary="Partially update sales revenue",
        description="Update specific fields of a sales revenue. Status is automatically reset to NOT_CALCULATED on any update.",
        tags=["10.5: Sales Revenue Management"],
        examples=[
            OpenApiExample(
                "Request - Update revenue only",
                value={"revenue": 175000000},
                request_only=True,
            ),
            OpenApiExample(
                "Success - Partially updated",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "SR-202511-0001",
                        "employee": {
                            "id": 101,
                            "code": "MV000000101",
                            "fullname": "Nguyen Van A",
                        },
                        "revenue": 175000000,
                        "transaction_count": 12,
                        "month": "11/2025",
                        "status": "NOT_CALCULATED",
                        "created_by": 1,
                        "updated_by": 2,
                        "created_at": "2025-11-15T10:00:00Z",
                        "updated_at": "2025-11-15T12:30:00Z",
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    ),
    destroy=extend_schema(
        summary="Delete sales revenue",
        description="Delete a sales revenue. Deletion is blocked if payroll already exists for that month. Returns 409 Conflict if blocked.",
        tags=["10.5: Sales Revenue Management"],
        examples=[
            OpenApiExample(
                "Success - Deleted",
                value={"success": True, "data": None, "error": None},
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
                        "message": "Cannot delete sales revenue for a month with existing payroll.",
                    },
                },
                response_only=True,
                status_codes=["409"],
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
    export=extend_schema(
        summary="Export sales revenues to XLSX",
        description="Export the filtered sales revenues list to XLSX. By default, returns a presigned download URL (delivery=link). Use delivery=direct to download the file directly.",
        tags=["10.5: Sales Revenue Management"],
        examples=[
            OpenApiExample(
                "Success - Export link",
                value={
                    "success": True,
                    "data": {
                        "download_url": "https://example.com/exports/sales-revenues-2025-11.xlsx",
                        "expires_at": "2025-11-15T12:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    ),
    start_import=extend_schema(tags=["10.5: Sales Revenue Management"]),
    import_template=extend_schema(tags=["10.5: Sales Revenue Management"]),
)
class SalesRevenueViewSet(AsyncImportProgressMixin, ExportXLSXMixin, AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for SalesRevenue model.

    Provides full CRUD operations for sales revenue records with:
    - Pagination: 25 rows per page by default
    - Search: by code, employee code, employee fullname (phrase search)
    - Filtering: by month (MM/YYYY), status, branch, block, department, position
    - Ordering: by created_at (desc default), code, revenue, month
    - Upload: Excel upload for bulk import via AsyncImportProgressMixin
    - Export: Excel export with filtered data
    - Delete guard: blocks deletion if payroll exists for the month

    Business rules:
    - Code is auto-generated on create
    - Status defaults to NOT_CALCULATED on create
    - Status is reset to NOT_CALCULATED on any update
    - One employee can only have one revenue record per month
    - Deletion is blocked if payroll exists for the month
    - Upload: if record exists, it will be updated (upsert)
    """

    queryset = SalesRevenue.objects.select_related(
        "employee", "employee__branch", "employee__block", "employee__department", "employee__position"
    ).all()
    serializer_class = SalesRevenueSerializer
    filterset_class = SalesRevenueFilterSet
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    search_fields = ["code", "employee__code", "employee__fullname"]
    ordering_fields = ["created_at", "code", "revenue", "month"]
    ordering = ["-created_at"]

    module = _("Payroll")
    submodule = _("Sales Revenue Management")
    permission_prefix = "sales_revenue"

    # Import handler configuration
    import_row_handler = "apps.payroll.import_handlers.sales_revenue.process_sales_revenue_row"

    def perform_create(self, serializer):
        """Set created_by when creating a new sales revenue."""
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        """Set updated_by when updating a sales revenue."""
        serializer.save(updated_by=self.request.user)

    def perform_destroy(self, instance):
        """Check if payroll exists before deletion."""
        try:
            instance.delete()
        except ProtectedError:
            return Response(
                {
                    "code": "PAYROLL_EXISTS",
                    "message": _("Cannot delete sales revenue for a month with existing payroll."),
                },
                status=status.HTTP_409_CONFLICT,
            )

    def get_export_data(self, request):
        """Custom export data for SalesRevenue."""
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)

        return {
            "sheets": [
                {
                    "name": str(queryset.model._meta.verbose_name),
                    "headers": [str(field.label) for field in serializer.child.fields.values()],
                    "field_names": [str(key) for key in serializer.child.fields.keys()],
                    "data": serializer.data,
                }
            ]
        }
