"""ViewSet for Contract model."""

from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets.contract import ContractFilterSet
from apps.hrm.api.serializers.contract import (
    ContractExportSerializer,
    ContractListSerializer,
    ContractSerializer,
)
from apps.hrm.models import Contract, ContractType
from apps.imports.api.mixins import AsyncImportProgressMixin
from libs import BaseModelViewSet, ExportDocumentMixin
from libs.drf.filtersets.search import PhraseSearchFilter
from libs.export_xlsx import ExportXLSXMixin


@extend_schema_view(
    list=extend_schema(
        summary="List all contracts",
        description="Retrieve a paginated list of all contracts with support for filtering by "
        "code, contract_number, status, employee, contract_type, date ranges, and organization",
        tags=["7.2: Contract"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "count": 2,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": 1,
                                "code": "HD00001",
                                "contract_number": "123/2025/HD-MVL",
                                "employee": {"id": 1, "code": "MV000001", "fullname": "John Doe"},
                                "contract_type": {"id": 1, "name": "Full-time Employment"},
                                "sign_date": "2025-01-15",
                                "effective_date": "2025-02-01",
                                "expiration_date": None,
                                "status": "active",
                                "colored_status": {"value": "active", "variant": "GREEN"},
                                "duration_type": "indefinite",
                                "colored_duration_type": {"value": "indefinite", "variant": "GREY"},
                                "duration_months": None,
                                "duration_display": "Indefinite term",
                                "base_salary": "15000000",
                                "kpi_salary": "2000000",
                                "created_at": "2025-01-15T10:00:00Z",
                            }
                        ],
                    },
                    "error": None,
                },
                response_only=True,
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get contract details",
        description="Retrieve detailed information about a specific contract",
        tags=["7.2: Contract"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "HD00001",
                        "contract_number": "HD00001",
                        "employee": {"id": 1, "code": "MV000001", "fullname": "John Doe"},
                        "contract_type": {"id": 1, "name": "Full-time Employment"},
                        "sign_date": "2025-01-15",
                        "effective_date": "2025-02-01",
                        "expiration_date": None,
                        "status": "active",
                        "colored_status": {"value": "active", "variant": "GREEN"},
                        "duration_type": "indefinite",
                        "colored_duration_type": {"value": "indefinite", "variant": "GREY"},
                        "duration_months": None,
                        "duration_display": "Indefinite term",
                        "base_salary": "15000000",
                        "kpi_salary": "2000000",
                        "lunch_allowance": "500000",
                        "phone_allowance": "200000",
                        "other_allowance": None,
                        "net_percentage": 100,
                        "colored_net_percentage": {"value": 100, "variant": "RED"},
                        "tax_calculation_method": "progressive",
                        "colored_tax_calculation_method": {"value": "progressive", "variant": "YELLOW"},
                        "working_time_type": "full_time",
                        "colored_working_time_type": {"value": "full_time", "variant": "BLUE"},
                        "annual_leave_days": 12,
                        "has_social_insurance": True,
                        "colored_has_social_insurance": {"value": True, "variant": "GREEN"},
                        "working_conditions": "Standard office conditions",
                        "rights_and_obligations": "Employee rights...",
                        "terms": "Contract terms...",
                        "note": None,
                        "attachment": None,
                        "created_at": "2025-01-15T10:00:00Z",
                        "updated_at": "2025-01-15T10:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            ),
        ],
    ),
    create=extend_schema(
        summary="Create a new contract",
        description="Create a new contract. Code is auto-generated. "
        "Snapshot data is copied from the contract type if not explicitly provided. "
        "Status is always DRAFT on creation and cannot be changed directly.",
        tags=["7.2: Contract"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "employee_id": 1,
                    "contract_type_id": 1,
                    "sign_date": "2025-01-15",
                    "effective_date": "2025-02-01",
                    "expiration_date": None,
                    "note": "New contract",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "HD00001",
                        "contract_number": "HD00001",
                        "employee": {"id": 1, "code": "MV000001", "fullname": "John Doe"},
                        "contract_type": {"id": 1, "name": "Full-time Employment"},
                        "sign_date": "2025-01-15",
                        "effective_date": "2025-02-01",
                        "expiration_date": None,
                        "status": "draft",
                        "colored_status": {"value": "draft", "variant": "YELLOW"},
                        "duration_type": "indefinite",
                        "colored_duration_type": {"value": "indefinite", "variant": "GREY"},
                        "duration_months": None,
                        "duration_display": "Indefinite term",
                        "base_salary": "15000000",
                        "kpi_salary": "2000000",
                        "note": "New contract",
                        "created_at": "2025-01-15T10:00:00Z",
                        "updated_at": "2025-01-15T10:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error - Validation",
                value={
                    "success": False,
                    "data": None,
                    "error": {"sign_date": ["Sign date must be on or before effective date."]},
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    update=extend_schema(
        summary="Update contract",
        description="Update all fields of a contract. Only DRAFT contracts can be edited.",
        tags=["7.2: Contract"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "employee_id": 1,
                    "contract_type_id": 1,
                    "sign_date": "2025-01-15",
                    "effective_date": "2025-02-01",
                    "expiration_date": "2026-02-01",
                    "base_salary": "18000000",
                    "kpi_salary": "2500000",
                    "note": "Updated contract",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "HD00001",
                        "contract_number": "HD00001",
                        "status": "draft",
                        "base_salary": "18000000",
                        "kpi_salary": "2500000",
                        "note": "Updated contract",
                    },
                    "error": None,
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error - Non-draft status",
                value={
                    "success": False,
                    "data": None,
                    "error": {"status": ["Only contracts with DRAFT status can be edited."]},
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    partial_update=extend_schema(
        summary="Partially update contract",
        description="Update specific fields of a contract. Only DRAFT contracts can be edited.",
        tags=["7.2: Contract"],
    ),
    destroy=extend_schema(
        summary="Delete contract",
        description="Delete a contract from the system. Only DRAFT contracts can be deleted.",
        tags=["7.2: Contract"],
        examples=[
            OpenApiExample(
                "Success",
                value={"success": True, "data": None, "error": None},
                response_only=True,
            ),
            OpenApiExample(
                "Error - Non-draft status",
                value={
                    "success": False,
                    "data": None,
                    "error": {"detail": "Only contracts with DRAFT status can be deleted."},
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    export=extend_schema(
        tags=["7.2: Contract"],
    ),
    start_import=extend_schema(
        tags=["7.2: Contract"],
    ),
    import_template=extend_schema(
        tags=["7.2: Contract"],
    ),
    export_detail_document=extend_schema(
        tags=["7.2: Contract"],
    ),
)
class ContractViewSet(
    ExportDocumentMixin, AsyncImportProgressMixin, ExportXLSXMixin, AuditLoggingMixin, BaseModelViewSet
):
    """ViewSet for Contract model.

    Provides CRUD operations, XLSX export, and document export (PDF/DOCX) for contracts.
    Supports filtering, searching, and ordering.
    Supports import from file via AsyncImportProgressMixin.

    Note: This ViewSet only returns contracts (category='contract'), not appendices.

    Search fields: code, contract_number, employee__fullname, employee__code
    """

    queryset = Contract.objects.filter(
        contract_type__category=ContractType.Category.CONTRACT,
    ).select_related(
        "employee",
        "employee__department",
        "employee__position",
        "contract_type",
        "attachment",
    )
    serializer_class = ContractSerializer
    filterset_class = ContractFilterSet
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    search_fields = ["code", "contract_number", "employee__fullname", "employee__code"]
    ordering_fields = [
        "code",
        "contract_number",
        "sign_date",
        "effective_date",
        "expiration_date",
        "status",
        "employee__fullname",
        "created_at",
    ]
    ordering = ["-created_at"]

    # Permission registration attributes
    module = _("HRM")
    submodule = _("Contract Management")
    permission_prefix = "contract"
    PERMISSION_REGISTERED_ACTIONS = {
        "publish": {
            "name_template": _("Publish {model_name}"),
            "description_template": _("Publish {model_name}"),
        },
    }

    # Export configuration
    export_serializer_class = ContractExportSerializer
    export_filename = "contracts"

    # Document export configuration
    document_template_name = "documents/contract.html"

    # Import handler path for AsyncImportProgressMixin
    # import_row_handler will be determined dynamically
    import_row_handler = "apps.hrm.import_handlers.contract_creation.import_handler"  # Default

    # Import configuration
    import_template_name = "hrm_contract_template"

    def get_import_handler_path(self):
        """Determine import handler path based on mode option."""
        # Get base handler path from parent logic if needed, but we implement custom routing here

        # Access options from request data
        options = self.request.data.get("options", {}) if self.request.data else {}
        mode = options.get("mode")

        if mode == "create":
            return "apps.hrm.import_handlers.contract_creation.import_handler"
        elif mode == "update":
            return "apps.hrm.import_handlers.contract_update.import_handler"

        # If no valid mode provided, raise validation error
        # Since this method is called inside start_import which catches errors,
        # raising ValidationError here will result in 400 Bad Request
        from rest_framework.exceptions import ValidationError
        raise ValidationError({"options": {"mode": _("Import mode must be either 'create' or 'update'")}})

    def get_export_context(self, instance):
        """Prepare context for contract document export.

        Args:
            instance: Contract instance to export.

        Returns:
            dict: Context dictionary for template rendering.
        """
        return {"contract": instance}

    def get_export_filename(self, instance):
        """Generate filename for contract document export.

        Args:
            instance: Contract instance to export.

        Returns:
            str: Filename without extension.
        """
        return f"contract_{instance.code}"

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == "list":
            return ContractListSerializer
        return ContractSerializer

    def destroy(self, request, *args, **kwargs):
        """Delete contract. Only DRAFT contracts can be deleted."""
        instance = self.get_object()

        if instance.status != Contract.ContractStatus.DRAFT:
            return Response(
                {"detail": "Only contracts with DRAFT status can be deleted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        summary="Publish contract",
        description="Change contract status from DRAFT to effective status (NOT_EFFECTIVE or ACTIVE).",
        tags=["7.2: Contract"],
        request=None,
        responses={
            200: OpenApiExample(
                "Success",
                value={"success": True, "data": {"status": "active"}, "error": None},
            ),
            400: OpenApiExample(
                "Error",
                value={
                    "success": False,
                    "data": None,
                    "error": {"detail": "Only DRAFT contracts can be published."},
                },
            ),
        },
    )
    @action(detail=True, methods=["post"], url_path="publish")
    def publish(self, request, pk=None):
        """Publish the contract (change status from DRAFT)."""
        instance = self.get_object()

        if instance.status != Contract.ContractStatus.DRAFT:
            return Response(
                {"detail": "Only DRAFT contracts can be published."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Calculate new status based on dates
        instance.status = instance.get_status_from_dates()
        instance.save()

        serializer = self.get_serializer(instance)
        return Response(serializer.data)
