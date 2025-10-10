from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.filters import OrderingFilter, SearchFilter

from apps.audit_logging import AuditLoggingMixin
from apps.core.api.filtersets.province import ProvinceFilterSet
from apps.core.api.serializers.province import ProvinceSerializer
from apps.core.models import Province


@extend_schema_view(
    list=extend_schema(
        summary="List provinces",
        description="Retrieve a list of all provinces/cities in the system",
        tags=["Geographic"],
    ),
    retrieve=extend_schema(
        summary="Retrieve a province",
        description="Retrieve detailed information about a specific province.",
        tags=["Geographic"],
    ),
)
class ProvinceViewSet(AuditLoggingMixin, viewsets.ReadOnlyModelViewSet):
    """ViewSet for Province model - read-only with no pagination"""

    queryset = Province.objects.all()
    serializer_class = ProvinceSerializer
    filterset_class = ProvinceFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "code", "english_name"]
    ordering_fields = ["code", "name", "created_at"]
    ordering = ["code"]
    pagination_class = None  # Disable pagination for provinces

    # Permission registration attributes
    module = "Core"
    submodule = "Geographic Data"
    permission_prefix = "province"
