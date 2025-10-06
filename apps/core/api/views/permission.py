from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.filters import OrderingFilter, SearchFilter

from apps.core.api.filtersets import PermissionFilterSet
from apps.core.api.serializers.role import PermissionSerializer
from apps.core.models import Permission


@extend_schema_view(
    list=extend_schema(
        summary="Danh sách quyền",
        description="Lấy danh sách tất cả quyền có sẵn trong hệ thống",
        tags=["Quyền"],
    ),
    retrieve=extend_schema(
        summary="Chi tiết quyền",
        description="Lấy thông tin chi tiết của một quyền",
        tags=["Quyền"],
    ),
)
class PermissionViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for Permission model - Read only"""

    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    filterset_class = PermissionFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["code", "description"]
    ordering_fields = ["code", "created_at"]
    ordering = ["code"]
