from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.filters import OrderingFilter, SearchFilter

from apps.audit_logging import AuditLoggingMixin
from apps.core.api.filtersets.administrative_unit import AdministrativeUnitFilterSet
from apps.core.api.serializers.administrative_unit import AdministrativeUnitSerializer
from apps.core.models import AdministrativeUnit


@extend_schema_view(
    list=extend_schema(
        summary="List administrative units",
        description="Retrieve a paginated list of all administrative units (districts, wards, communes, etc.)",
        tags=["Geographic"],
    ),
    retrieve=extend_schema(
        summary="Retrieve an administrative unit",
        description="Retrieve detailed information about a specific administrative unit.",
        tags=["Geographic"],
    ),
)
class AdministrativeUnitViewSet(AuditLoggingMixin, viewsets.ReadOnlyModelViewSet):
    """ViewSet for AdministrativeUnit model - read-only with pagination"""

    queryset = AdministrativeUnit.objects.select_related("parent_province").all()
    serializer_class = AdministrativeUnitSerializer
    filterset_class = AdministrativeUnitFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "code"]
    ordering_fields = ["code", "name", "parent_province__code", "created_at"]
    ordering = ["parent_province__code", "code"]

    # Permission registration attributes
    module = "Core"
    submodule = "Geographic Data"
    permission_prefix = "administrative_unit"
