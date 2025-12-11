"""ViewSet for Contract Appendix (using Contract model with category='appendix')."""

from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets.contract_appendix import ContractAppendixFilterSet
from apps.hrm.api.serializers.contract_appendix import (
    ContractAppendixExportSerializer,
    ContractAppendixListSerializer,
    ContractAppendixSerializer,
)
from apps.hrm.models import Contract, ContractType
from apps.imports.api.mixins import AsyncImportProgressMixin
from libs import BaseModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter
from libs.export_xlsx import ExportXLSXMixin


@extend_schema_view(
    list=extend_schema(
        summary="List all contract appendices",
        description="Retrieve a paginated list of all contract appendices with support for filtering by "
        "code, contract_number, parent_contract, date ranges, and organization",
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
                                "code": "PLHD00001",
                                "contract_number": "01/2025/PLHD-MVL",
                                "parent_contract": {
                                    "id": 1,
                                    "code": "HD00001",
                                    "contract_number": "01/2025/HDLD - MVL",
                                },
                                "employee": {"id": 1, "code": "MV000001", "fullname": "John Doe"},
                                "contract_type": {"id": 2, "name": "Contract Appendix"},
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
                        "code": "PLHD00001",
                        "contract_number": "01/2025/PLHD-MVL",
                        "parent_contract": {"id": 1, "code": "HD00001", "contract_number": "01/2025/HDLD - MVL"},
                        "employee": {"id": 1, "code": "MV000001", "fullname": "John Doe"},
                        "contract_type": {"id": 2, "name": "Contract Appendix"},
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
        description="Create a new contract appendix. Code and contract_number are auto-generated. "
        "parent_contract_id is required - employee and contract_type are derived from the parent contract.",
        tags=["7.3: Contract Appendix"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "parent_contract_id": 1,
                    "sign_date": "2025-01-15",
                    "effective_date": "2025-02-01",
                    "content": "New appendix content",
                    "base_salary": "20000000",
                    "kpi_salary": "3000000",
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
                        "code": "PLHD00001",
                        "contract_number": "01/2025/PLHD-MVL",
                        "parent_contract": {"id": 1, "code": "HD00001", "contract_number": "01/2025/HDLD - MVL"},
                        "employee": {"id": 1, "code": "MV000001", "fullname": "John Doe"},
                        "contract_type": {"id": 2, "name": "Contract Appendix"},
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
                "Error - Missing parent contract",
                value={
                    "success": False,
                    "data": None,
                    "error": {"parent_contract_id": ["This field is required."]},
                },
                response_only=True,
                status_codes=["400"],
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
        description="Update all fields of a contract appendix. Only DRAFT appendices can be edited. "
        "If parent_contract_id is changed, employee will be updated accordingly.",
        tags=["7.3: Contract Appendix"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "parent_contract_id": 1,
                    "sign_date": "2025-01-15",
                    "effective_date": "2025-02-01",
                    "content": "Updated appendix content",
                    "base_salary": "22000000",
                    "kpi_salary": "3500000",
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
                        "code": "PLHD00001",
                        "contract_number": "01/2025/PLHD-MVL",
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
        description="Update specific fields of a contract appendix. Only DRAFT appendices can be edited.",
        tags=["7.3: Contract Appendix"],
    ),
    destroy=extend_schema(
        summary="Delete contract appendix",
        description="Delete a contract appendix from the system. Only DRAFT appendices can be deleted.",
        tags=["7.3: Contract Appendix"],
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
                    "error": {"detail": "Only appendices with DRAFT status can be deleted."},
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    export=extend_schema(
        tags=["7.3: Contract Appendix"],
    ),
    start_import=extend_schema(
        tags=["7.3: Contract Appendix"],
    ),
    import_template=extend_schema(
        tags=["7.3: Contract Appendix"],
    ),
)
class ContractAppendixViewSet(AsyncImportProgressMixin, ExportXLSXMixin, AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for Contract Appendix (using Contract model with category='appendix').

    Provides CRUD operations and XLSX export for contract appendices.
    Appendices are stored in the Contract model with contract_type.category='appendix'.
    Supports filtering, searching, and ordering.

    Search fields: code, contract_number, parent_contract__code, employee__fullname
    """

    queryset = Contract.objects.filter(
        contract_type__category=ContractType.Category.APPENDIX,
    ).select_related(
        "parent_contract",
        "employee",
        "contract_type",
    )
    serializer_class = ContractAppendixSerializer
    filterset_class = ContractAppendixFilterSet
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    search_fields = ["code", "contract_number", "parent_contract__code", "employee__fullname"]
    ordering_fields = [
        "code",
        "contract_number",
        "sign_date",
        "effective_date",
        "parent_contract__code",
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

    # Import configuration
    import_template_filename = "contract_appendix_template"

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == "list":
            return ContractAppendixListSerializer
        return ContractAppendixSerializer

    def destroy(self, request, *args, **kwargs):
        """Delete appendix. Only DRAFT appendices can be deleted."""
        instance = self.get_object()

        if instance.status != Contract.ContractStatus.DRAFT:
            return Response(
                {"detail": "Only appendices with DRAFT status can be deleted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        summary="Publish contract appendix",
        description="Change contract appendix status from DRAFT to effective status (NOT_EFFECTIVE or ACTIVE).",
        tags=["7.3: Contract Appendix"],
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
                    "error": {"detail": "Only DRAFT appendices can be published."},
                },
            ),
        },
    )
    @action(detail=True, methods=["post"], url_path="publish")
    def publish(self, request, pk=None):
        """Publish the contract appendix (change status from DRAFT)."""
        instance = self.get_object()

        if instance.status != Contract.ContractStatus.DRAFT:
            return Response(
                {"detail": "Only DRAFT appendices can be published."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Calculate new status based on dates
        instance.status = instance.get_status_from_dates()
        instance.save()

        serializer = self.get_serializer(instance)
        return Response(serializer.data)
