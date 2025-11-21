from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets.contract_type import ContractTypeFilterSet
from apps.hrm.api.serializers import ContractTypeSerializer
from apps.hrm.models import ContractType
from libs import BaseModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter


@extend_schema_view(
    list=extend_schema(
        summary="List all contract types",
        description="Retrieve a paginated list of all contract types with support for filtering by name",
        tags=["Contract Type"],
    ),
    create=extend_schema(
        summary="Create a new contract type",
        description="Create a new contract type in the system",
        tags=["Contract Type"],
    ),
    retrieve=extend_schema(
        summary="Get contract type details",
        description="Retrieve detailed information about a specific contract type",
        tags=["Contract Type"],
    ),
    update=extend_schema(
        summary="Update contract type",
        description="Update contract type information",
        tags=["Contract Type"],
    ),
    partial_update=extend_schema(
        summary="Partially update contract type",
        description="Partially update contract type information",
        tags=["Contract Type"],
    ),
    destroy=extend_schema(
        summary="Delete contract type",
        description="Remove a contract type from the system",
        tags=["Contract Type"],
    ),
)
class ContractTypeViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for ContractType model."""

    queryset = ContractType.objects.all()
    serializer_class = ContractTypeSerializer
    filterset_class = ContractTypeFilterSet
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    # Permission registration attributes
    module = "HRM"
    submodule = "Contract Type Management"
    permission_prefix = "contract_type"
