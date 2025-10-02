from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.core.api.filtersets import RoleFilterSet
from apps.core.api.serializers import RoleSerializer
from apps.core.models import Role


@extend_schema_view(
    list=extend_schema(
        summary="Danh sách vai trò",
        description="Lấy danh sách tất cả vai trò trong hệ thống",
        tags=["Vai trò"],
    ),
    create=extend_schema(
        summary="Tạo vai trò mới",
        description="Tạo một vai trò mới trong hệ thống",
        tags=["Vai trò"],
    ),
    retrieve=extend_schema(
        summary="Chi tiết vai trò",
        description="Lấy thông tin chi tiết của một vai trò",
        tags=["Vai trò"],
    ),
    update=extend_schema(
        summary="Cập nhật vai trò",
        description="Cập nhật thông tin vai trò",
        tags=["Vai trò"],
    ),
    partial_update=extend_schema(
        summary="Cập nhật một phần vai trò",
        description="Cập nhật một phần thông tin vai trò",
        tags=["Vai trò"],
    ),
    destroy=extend_schema(
        summary="Xóa vai trò",
        description="Xóa vai trò khỏi hệ thống",
        tags=["Vai trò"],
    ),
)
class RoleViewSet(viewsets.ModelViewSet):
    """ViewSet for Role model"""

    queryset = Role.objects.prefetch_related("permissions").all()
    serializer_class = RoleSerializer
    filterset_class = RoleFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "code", "description"]
    ordering_fields = ["code", "name", "created_at"]
    ordering = ["code"]

    def destroy(self, request, *args, **kwargs):
        """Delete a role with validation"""
        instance = self.get_object()
        can_delete, error_message = instance.can_delete()

        if not can_delete:
            return Response(
                {"detail": error_message},
                status=status.HTTP_400_BAD_REQUEST,
            )

        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)
