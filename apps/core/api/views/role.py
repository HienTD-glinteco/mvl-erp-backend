from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.audit_logging import AuditLoggingMixin
from apps.core.api.filtersets import RoleFilterSet
from apps.core.api.serializers import RoleSerializer
from apps.core.models import Role
from libs import BaseModelViewSet


@extend_schema_view(
    list=extend_schema(
        summary="List roles",
        description="Retrieve a list of all roles in the system",
        tags=["Roles"],
    ),
    create=extend_schema(
        summary="Create a new role",
        description="Create a new role in the system",
        tags=["Roles"],
    ),
    retrieve=extend_schema(
        summary="Get role details",
        description="Retrieve detailed information about a specific role",
        tags=["Roles"],
    ),
    update=extend_schema(
        summary="Update role",
        description="Update role information",
        tags=["Roles"],
    ),
    partial_update=extend_schema(
        summary="Partially update role",
        description="Partially update role information",
        tags=["Roles"],
    ),
    destroy=extend_schema(
        summary="Delete role",
        description="Delete role from the system",
        tags=["Roles"],
    ),
)
class RoleViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for Role model"""

    queryset = Role.objects.prefetch_related("permissions").all()
    serializer_class = RoleSerializer
    filterset_class = RoleFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "code", "description"]
    ordering_fields = ["code", "name", "created_at"]
    ordering = ["code"]

    # Permission registration attributes
    module = "Core"
    submodule = "Role Management"
    permission_prefix = "role"

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
