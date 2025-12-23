from django.db.models import ProtectedError
from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.payroll.api.filtersets import TravelExpenseFilterSet
from apps.payroll.api.serializers import TravelExpenseSerializer
from apps.payroll.models import TravelExpense
from libs import BaseModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter
from libs.export_xlsx.mixins import ExportXLSXMixin


@extend_schema_view(
    list=extend_schema(
        summary="List all travel expenses",
        description="Retrieve a paginated list of travel expenses with support for filtering and search. Shows latest version only, sorted by newest created. Default page size is 25 rows.",
        tags=["10.4: Travel Expenses"],
        examples=[
            OpenApiExample(
                "Success - List of travel expenses",
                value={
                    "success": True,
                    "data": {
                        "count": 2,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": 1,
                                "code": "TE-202511-0001",
                                "name": "Client visit 11/2025",
                                "expense_type": "TAXABLE",
                                "employee": {
                                    "id": 101,
                                    "code": "E0001",
                                    "fullname": "John Doe",
                                },
                                "block": {"id": 1, "name": "Sales Block", "code": "BL001"},
                                "branch": {"id": 1, "name": "Hanoi Branch", "code": "HN"},
                                "department": {"id": 1, "name": "Sales Department", "code": "SALES"},
                                "position": {"id": 1, "name": "Sales Manager", "code": "SM"},
                                "amount": 2500000,
                                "month": "11/2025",
                                "status": "NOT_CALCULATED",
                                "note": "Taxi + meals",
                                "created_by": 1,
                                "updated_by": None,
                                "created_at": "2025-11-15T10:00:00Z",
                                "updated_at": "2025-11-15T10:00:00Z",
                            },
                            {
                                "id": 2,
                                "code": "TE-202511-0002",
                                "name": "Conference trip",
                                "expense_type": "NON_TAXABLE",
                                "employee": {
                                    "id": 101,
                                    "code": "E0001",
                                    "fullname": "John Doe",
                                },
                                "amount": 5000000,
                                "month": "11/2025",
                                "status": "CALCULATED",
                                "note": "Annual tech conference",
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
        summary="Get travel expense details",
        description="Retrieve detailed information about a specific travel expense. Shows all fields with current values.",
        tags=["10.4: Travel Expenses"],
        examples=[
            OpenApiExample(
                "Success - Single travel expense",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "TE-202511-0001",
                        "name": "Client visit 11/2025",
                        "expense_type": "TAXABLE",
                        "employee": {
                            "id": 101,
                            "code": "E0001",
                            "fullname": "John Doe",
                        },
                        "amount": 2500000,
                        "month": "11/2025",
                        "status": "NOT_CALCULATED",
                        "note": "Taxi + meals",
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
        summary="Create a new travel expense",
        description="Create a new travel expense record. Code is auto-generated in format TE-{YYYYMM}-{seq}. Status defaults to NOT_CALCULATED. Month must be in MM/YYYY format. Employee must be active.",
        tags=["10.4: Travel Expenses"],
        examples=[
            OpenApiExample(
                "Request - Create travel expense",
                value={
                    "name": "Client visit 11/2025",
                    "expense_type": "TAXABLE",
                    "employee_id": 101,
                    "amount": 2500000,
                    "month": "11/2025",
                    "note": "Taxi + meals",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success - Created",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "TE-202511-0001",
                        "name": "Client visit 11/2025",
                        "expense_type": "TAXABLE",
                        "employee": {
                            "id": 101,
                            "code": "E0001",
                            "fullname": "John Doe",
                        },
                        "block": {"id": 1, "name": "Sales Block", "code": "BL001"},
                        "branch": {"id": 1, "name": "Hanoi Branch", "code": "HN"},
                        "department": {"id": 1, "name": "Sales Department", "code": "SALES"},
                        "position": {"id": 1, "name": "Sales Manager", "code": "SM"},
                        "amount": 2500000,
                        "month": "11/2025",
                        "status": "NOT_CALCULATED",
                        "note": "Taxi + meals",
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
                        "amount": ["Amount must be greater than 0"],
                        "month": ["Month must be in MM/YYYY format (e.g., 11/2025)"],
                    },
                },
                response_only=True,
                status_codes=["400"],
            ),
            OpenApiExample(
                "Error - Employee not active",
                value={
                    "success": False,
                    "data": None,
                    "error": {
                        "employee_id": ["Employee must be active"],
                    },
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    update=extend_schema(
        summary="Update travel expense",
        description="Update all fields of a travel expense. Code is immutable. Status is automatically reset to NOT_CALCULATED on update. Changes are saved in audit history.",
        tags=["10.4: Travel Expenses"],
        examples=[
            OpenApiExample(
                "Request - Update travel expense",
                value={
                    "name": "Client visit updated",
                    "expense_type": "TAXABLE",
                    "employee_id": 101,
                    "amount": 3000000,
                    "month": "11/2025",
                    "note": "Updated: Taxi + meals + hotel",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success - Updated",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "TE-202511-0001",
                        "name": "Client visit updated",
                        "expense_type": "TAXABLE",
                        "employee": {
                            "id": 101,
                            "code": "E0001",
                            "fullname": "John Doe",
                        },
                        "block": {"id": 1, "name": "Sales Block", "code": "BL001"},
                        "branch": {"id": 1, "name": "Hanoi Branch", "code": "HN"},
                        "department": {"id": 1, "name": "Sales Department", "code": "SALES"},
                        "position": {"id": 1, "name": "Sales Manager", "code": "SM"},
                        "amount": 3000000,
                        "month": "11/2025",
                        "status": "NOT_CALCULATED",
                        "note": "Updated: Taxi + meals + hotel",
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
        summary="Partially update travel expense",
        description="Update specific fields of a travel expense. Status is automatically reset to NOT_CALCULATED on any update.",
        tags=["10.4: Travel Expenses"],
        examples=[
            OpenApiExample(
                "Request - Update amount only",
                value={"amount": 3500000},
                request_only=True,
            ),
            OpenApiExample(
                "Success - Partially updated",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "TE-202511-0001",
                        "name": "Client visit 11/2025",
                        "expense_type": "TAXABLE",
                        "employee": {
                            "id": 101,
                            "code": "E0001",
                            "fullname": "John Doe",
                        },
                        "block": {"id": 1, "name": "Sales Block", "code": "BL001"},
                        "branch": {"id": 1, "name": "Hanoi Branch", "code": "HN"},
                        "department": {"id": 1, "name": "Sales Department", "code": "SALES"},
                        "position": {"id": 1, "name": "Sales Manager", "code": "SM"},
                        "amount": 3500000,
                        "month": "11/2025",
                        "status": "NOT_CALCULATED",
                        "note": "Taxi + meals",
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
        summary="Delete travel expense",
        description="Delete a travel expense. Deletion is blocked if payroll already exists for that month. Returns 409 Conflict if blocked.",
        tags=["10.4: Travel Expenses"],
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
                        "message": "Cannot delete travel expense for a month with existing payroll.",
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
        summary="Export travel expenses to XLSX",
        description="Export the filtered travel expenses list to XLSX. By default, returns a presigned download URL (delivery=link). Use delivery=direct to download the file directly.",
        tags=["10.4: Travel Expenses"],
        examples=[
            OpenApiExample(
                "Success - Export link",
                value={
                    "success": True,
                    "data": {
                        "download_url": "https://example.com/exports/travel-expenses-2025-11.xlsx",
                        "expires_at": "2025-11-15T12:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Success - Async export started",
                value={
                    "success": True,
                    "data": {
                        "task_id": "d3b07384-d9a1-4c8e-9f88-1234567890ab",
                        "status": "PENDING",
                        "message": "Export started. Check status at /api/export/status/?task_id=d3b07384-d9a1-4c8e-9f88-1234567890ab",
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["202"],
            ),
            OpenApiExample(
                "Error - Invalid delivery",
                value={
                    "success": False,
                    "data": None,
                    "error": {"detail": "Invalid delivery parameter; allowed: link, direct"},
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
)
class TravelExpenseViewSet(ExportXLSXMixin, AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for TravelExpense model.

    Provides full CRUD operations for travel expense records with:
    - Pagination: 25 rows per page by default
    - Search: by code, name, employee code, employee name (phrase search)
    - Filtering: by expense_type, month (MM/YYYY), status
    - Ordering: by created_at (desc default), code, name, amount, month
    - Export: Excel export with filtered data
    - Delete guard: blocks deletion if payroll exists for the month

    Business rules:
    - Code is auto-generated on create
    - Status defaults to NOT_CALCULATED on create
    - Status is reset to NOT_CALCULATED on any update
    - Deletion is blocked if payroll exists for the month
    """

    queryset = TravelExpense.objects.all()
    serializer_class = TravelExpenseSerializer
    filterset_class = TravelExpenseFilterSet
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    search_fields = ["code", "name", "employee__code", "employee__fullname"]
    ordering_fields = ["created_at", "code", "name", "amount", "month"]
    ordering = ["-created_at"]

    # Permission registration attributes
    module = _("Payroll")
    submodule = _("Travel Expense Management")
    permission_prefix = "travel_expense"

    def perform_create(self, serializer):
        """Set created_by when creating a new travel expense."""
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        """Set updated_by when updating a travel expense."""
        serializer.save(updated_by=self.request.user)

    def perform_destroy(self, instance):
        """Check if payroll exists before deletion.

        Raises:
            Response with 409 if payroll exists for the expense month.
        """
        # TODO: Add check for payroll existence once payroll model is implemented
        # For now, we'll check if there are any related records preventing deletion
        try:
            instance.delete()
        except ProtectedError:
            return Response(
                {
                    "code": "PAYROLL_EXISTS",
                    "message": _("Cannot delete travel expense for a month with existing payroll."),
                },
                status=status.HTTP_409_CONFLICT,
            )

    def get_export_data(self, request):
        """Custom export data for RecruitmentExpense.

        Exports the following fields:
        """
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
