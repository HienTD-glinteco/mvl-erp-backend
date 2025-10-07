from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.filters import OrderingFilter, SearchFilter

from apps.core.api.filtersets import PermissionFilterSet
from apps.core.api.serializers.role import PermissionSerializer
from apps.core.models import Permission


@extend_schema_view(
    list=extend_schema(
        summary="List permissions",
        description="Retrieve a list of all permissions available in the system",
        tags=["Permissions"],
    ),
    retrieve=extend_schema(
        summary="Get permission details",
        description="Retrieve detailed information about a specific permission",
        tags=["Permissions"],
    ),
)
class PermissionViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for Permission model - Read only"""

    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    filterset_class = PermissionFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["code", "description", "module", "submodule"]
    ordering_fields = ["code", "created_at"]
    ordering = ["code"]
