"""ViewSet for ContractAppendix model."""

from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets.contract_appendix import ContractAppendixFilterSet
from apps.hrm.api.serializers.contract_appendix import (
    ContractAppendixExportSerializer,
    ContractAppendixListSerializer,
    ContractAppendixSerializer,
)
from apps.hrm.models import ContractAppendix
from libs import BaseModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter
from libs.export_xlsx import ExportXLSXMixin


@extend_schema_view(
    list=extend_schema(
        summary="List all contract appendices",
        description="Retrieve a paginated list of all contract appendices with support for filtering by "
        "code, appendix_code, contract, date ranges, and organization",
        tags=["7.3: Contract Appendix"],
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
                                "code": "01/2025/PLHD-MVL",
                                "appendix_code": "PLHD00001",
                                "appendix_number": "01/2025/PLHD-MVL",
                                "contract": {"id": 1, "code": "01/2025/HDLD - MVL"},
                                "sign_date": "2025-01-15",
                                "effective_date": "2025-02-01",
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
        summary="Get contract appendix details",
        description="Retrieve detailed information about a specific contract appendix",
        tags=["7.3: Contract Appendix"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "01/2025/PLHD-MVL",
                        "appendix_code": "PLHD00001",
                        "appendix_number": "01/2025/PLHD-MVL",
                        "contract": {"id": 1, "code": "01/2025/HDLD - MVL"},
                        "sign_date": "2025-01-15",
                        "effective_date": "2025-02-01",
                        "content": "Appendix content...",
                        "note": None,
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
        summary="Create a new contract appendix",
        description="Create a new contract appendix. Code and appendix_code are auto-generated.",
        tags=["7.3: Contract Appendix"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "contract_id": 1,
                    "sign_date": "2025-01-15",
                    "effective_date": "2025-02-01",
                    "content": "New appendix content",
                    "note": "Additional notes",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "01/2025/PLHD-MVL",
                        "appendix_code": "PLHD00001",
                        "appendix_number": "01/2025/PLHD-MVL",
                        "contract": {"id": 1, "code": "01/2025/HDLD - MVL"},
                        "sign_date": "2025-01-15",
                        "effective_date": "2025-02-01",
                        "content": "New appendix content",
                        "note": "Additional notes",
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
        summary="Update contract appendix",
        description="Update all fields of a contract appendix.",
        tags=["7.3: Contract Appendix"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "contract_id": 1,
                    "sign_date": "2025-01-15",
                    "effective_date": "2025-02-01",
                    "content": "Updated appendix content",
                    "note": "Updated notes",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "01/2025/PLHD-MVL",
                        "appendix_code": "PLHD00001",
                        "appendix_number": "01/2025/PLHD-MVL",
                        "content": "Updated appendix content",
                        "note": "Updated notes",
                    },
                    "error": None,
                },
                response_only=True,
            ),
        ],
    ),
    partial_update=extend_schema(
        summary="Partially update contract appendix",
        description="Update specific fields of a contract appendix.",
        tags=["7.3: Contract Appendix"],
    ),
    destroy=extend_schema(
        summary="Delete contract appendix",
        description="Delete a contract appendix from the system.",
        tags=["7.3: Contract Appendix"],
        examples=[
            OpenApiExample(
                "Success",
                value={"success": True, "data": None, "error": None},
                response_only=True,
            ),
        ],
    ),
    export=extend_schema(
        tags=["7.3: Contract Appendix"],
    ),
)
class ContractAppendixViewSet(ExportXLSXMixin, AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for ContractAppendix model.

    Provides CRUD operations and XLSX export for contract appendices.
    Supports filtering, searching, and ordering.

    Search fields: code, appendix_code, contract__code, contract__employee__fullname
    """

    queryset = ContractAppendix.objects.select_related(
        "contract",
        "contract__employee",
    )
    serializer_class = ContractAppendixSerializer
    filterset_class = ContractAppendixFilterSet
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    search_fields = ["code", "appendix_code", "contract__code", "contract__employee__fullname"]
    ordering_fields = [
        "code",
        "appendix_code",
        "sign_date",
        "effective_date",
        "contract__code",
        "created_at",
    ]
    ordering = ["-created_at"]

    # Permission registration attributes
    module = "HRM"
    submodule = "Contract Appendix Management"
    permission_prefix = "contract_appendix"

    # Export configuration
    export_serializer_class = ContractAppendixExportSerializer
    export_filename = "contract_appendices"

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == "list":
            return ContractAppendixListSerializer
        return ContractAppendixSerializer
