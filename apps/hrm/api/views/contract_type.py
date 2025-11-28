from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets.contract_type import ContractTypeFilterSet
from apps.hrm.api.serializers import ContractTypeExportSerializer, ContractTypeListSerializer, ContractTypeSerializer
from apps.hrm.models import ContractType
from libs import BaseModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter
from libs.export_xlsx import ExportXLSXMixin


@extend_schema_view(
    list=extend_schema(
        summary="List all contract types",
        description="Retrieve a paginated list of all contract types with support for filtering by name, code, "
        "duration type, social insurance status, and working time type",
        tags=["7.1 Contract Type"],
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
                                "code": "LHD001",
                                "name": "Full-time Employment Contract",
                                "duration_display": "Indefinite term",
                                "base_salary": "15000000",
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
        summary="Get contract type details",
        description="Retrieve detailed information about a specific contract type",
        tags=["7.1 Contract Type"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "LHD001",
                        "name": "Full-time Employment Contract",
                        "symbol": "HDLD",
                        "duration_type": "indefinite",
                        "duration_months": None,
                        "duration_display": "Indefinite term",
                        "base_salary": "15000000",
                        "lunch_allowance": "500000",
                        "phone_allowance": "200000",
                        "other_allowance": None,
                        "net_percentage": "100",
                        "tax_calculation_method": "progressive",
                        "working_time_type": "full_time",
                        "annual_leave_days": 12,
                        "has_social_insurance": True,
                        "working_conditions": "Standard office conditions",
                        "rights_and_obligations": "Employee rights and obligations...",
                        "terms": "Contract terms...",
                        "note": None,
                        "template_file": None,
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
        summary="Create a new contract type",
        description="Create a new contract type in the system. Code is auto-generated.",
        tags=["7.1 Contract Type"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "name": "Fixed-term Employment Contract",
                    "symbol": "HDLD-TH",
                    "duration_type": "fixed",
                    "duration_months": 12,
                    "base_salary": "12000000",
                    "lunch_allowance": "500000",
                    "phone_allowance": None,
                    "other_allowance": None,
                    "net_percentage": "100",
                    "tax_calculation_method": "progressive",
                    "working_time_type": "full_time",
                    "annual_leave_days": 12,
                    "has_social_insurance": True,
                    "working_conditions": "Standard office conditions",
                    "rights_and_obligations": "Employee rights and obligations...",
                    "terms": "Contract terms...",
                    "template_file_id": 1,
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 2,
                        "code": "LHD002",
                        "name": "Fixed-term Employment Contract",
                        "symbol": "HDLD-TH",
                        "duration_type": "fixed",
                        "duration_months": 12,
                        "duration_display": "12 months",
                        "base_salary": "12000000",
                        "lunch_allowance": "500000",
                        "phone_allowance": None,
                        "other_allowance": None,
                        "net_percentage": "100",
                        "tax_calculation_method": "progressive",
                        "working_time_type": "full_time",
                        "annual_leave_days": 12,
                        "has_social_insurance": True,
                        "working_conditions": "Standard office conditions",
                        "rights_and_obligations": "Employee rights and obligations...",
                        "terms": "Contract terms...",
                        "note": None,
                        "template_file": {"id": 1, "file_name": "template.docx"},
                        "created_at": "2025-01-20T10:00:00Z",
                        "updated_at": "2025-01-20T10:00:00Z",
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
                    "error": {"name": ["contract type with this contract type name already exists."]},
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    update=extend_schema(
        summary="Update contract type",
        description="Update all fields of a contract type (except code)",
        tags=["7.1 Contract Type"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "name": "Fixed-term Employment Contract (Updated)",
                    "symbol": "HDLD-TH",
                    "duration_type": "fixed",
                    "duration_months": 24,
                    "base_salary": "14000000",
                    "lunch_allowance": "600000",
                    "phone_allowance": "300000",
                    "other_allowance": None,
                    "net_percentage": "100",
                    "tax_calculation_method": "progressive",
                    "working_time_type": "full_time",
                    "annual_leave_days": 12,
                    "has_social_insurance": True,
                    "working_conditions": "Updated working conditions",
                    "rights_and_obligations": "Updated rights and obligations...",
                    "terms": "Updated terms...",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 2,
                        "code": "LHD002",
                        "name": "Fixed-term Employment Contract (Updated)",
                        "symbol": "HDLD-TH",
                        "duration_type": "fixed",
                        "duration_months": 24,
                        "duration_display": "24 months",
                        "base_salary": "14000000",
                        "lunch_allowance": "600000",
                        "phone_allowance": "300000",
                        "other_allowance": None,
                        "net_percentage": "100",
                        "tax_calculation_method": "progressive",
                        "working_time_type": "full_time",
                        "annual_leave_days": 12,
                        "has_social_insurance": True,
                        "working_conditions": "Updated working conditions",
                        "rights_and_obligations": "Updated rights and obligations...",
                        "terms": "Updated terms...",
                        "note": None,
                        "template_file": None,
                        "created_at": "2025-01-20T10:00:00Z",
                        "updated_at": "2025-01-21T10:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            ),
        ],
    ),
    partial_update=extend_schema(
        summary="Partially update contract type",
        description="Update specific fields of a contract type",
        tags=["7.1 Contract Type"],
    ),
    destroy=extend_schema(
        summary="Delete contract type",
        description="Remove a contract type from the system. Cannot delete if used in employee contracts.",
        tags=["7.1 Contract Type"],
        examples=[
            OpenApiExample(
                "Success",
                value={"success": True, "data": None, "error": None},
                response_only=True,
            ),
        ],
    ),
    export=extend_schema(
        tags=["7.1 Contract Type"],
    ),
)
class ContractTypeViewSet(ExportXLSXMixin, AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for ContractType model.

    Provides CRUD operations and XLSX export for contract types.
    Supports filtering, searching, and ordering.
    """

    queryset = ContractType.objects.select_related("template_file")
    serializer_class = ContractTypeSerializer
    filterset_class = ContractTypeFilterSet
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    search_fields = ["name", "code", "symbol"]
    ordering_fields = ["name", "code", "base_salary", "created_at"]
    ordering = ["-created_at"]

    # Permission registration attributes
    module = "HRM"
    submodule = "Contract Type Management"
    permission_prefix = "contract_type"

    # Export configuration
    export_serializer_class = ContractTypeExportSerializer
    export_filename = "contract_types"

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == "list":
            return ContractTypeListSerializer
        return ContractTypeSerializer
