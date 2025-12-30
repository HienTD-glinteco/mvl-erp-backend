from typing import Final

from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.core.api.filtersets import RoleFilterSet
from apps.core.api.serializers import RoleSerializer
from apps.core.models import Role
from libs import BaseModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter

ROLE_CLONE_SUFFIX: Final = "-copy"


@extend_schema_view(
    list=extend_schema(
        summary="List roles",
        description="Retrieve a list of all roles in the system",
        tags=["3.1: Roles"],
        examples=[
            OpenApiExample(
                "List roles success",
                description="Example response when listing roles",
                value={
                    "success": True,
                    "data": {
                        "count": 2,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": 1,
                                "code": "VT001",
                                "name": "System Admin",
                                "description": "Full system access with all permissions",
                                "is_system_role": True,
                                "created_by": "System",
                                "permissions_detail": [
                                    {
                                        "id": 1,
                                        "code": "user.create",
                                        "name": "Create User",
                                        "description": "Permission to create users",
                                        "module": "Core",
                                        "submodule": "User Management",
                                    }
                                ],
                                "created_at": "2025-01-01T00:00:00Z",
                                "updated_at": "2025-01-01T00:00:00Z",
                            },
                            {
                                "id": 2,
                                "code": "VT002",
                                "name": "Manager",
                                "description": "Manager role with limited permissions",
                                "is_system_role": False,
                                "created_by": "admin@example.com",
                                "permissions_detail": [
                                    {
                                        "id": 5,
                                        "code": "user.view",
                                        "name": "View User",
                                        "description": "Permission to view users",
                                        "module": "Core",
                                        "submodule": "User Management",
                                    }
                                ],
                                "created_at": "2025-01-10T10:30:00Z",
                                "updated_at": "2025-01-10T10:30:00Z",
                            },
                        ],
                    },
                },
                response_only=True,
            )
        ],
    ),
    create=extend_schema(
        summary="Create a new role",
        description="Create a new role in the system",
        tags=["3.1: Roles"],
        examples=[
            OpenApiExample(
                "Create role request",
                description="Example request to create a new role",
                value={
                    "name": "Project Manager",
                    "description": "Manages projects and teams",
                    "permission_ids": [1, 2, 5, 10],
                },
                request_only=True,
            ),
            OpenApiExample(
                "Create role success",
                description="Success response when creating a role",
                value={
                    "success": True,
                    "data": {
                        "id": 10,
                        "code": "VT010",
                        "name": "Project Manager",
                        "description": "Manages projects and teams",
                        "is_system_role": False,
                        "created_by": "admin@example.com",
                        "permissions_detail": [
                            {
                                "id": 1,
                                "code": "user.create",
                                "name": "Create User",
                                "description": "",
                                "module": "Core",
                                "submodule": "User Management",
                            },
                            {
                                "id": 2,
                                "code": "user.update",
                                "name": "Update User",
                                "description": "",
                                "module": "Core",
                                "submodule": "User Management",
                            },
                        ],
                        "created_at": "2025-01-15T14:20:00Z",
                        "updated_at": "2025-01-15T14:20:00Z",
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Create role validation error",
                description="Error response when validation fails",
                value={
                    "success": False,
                    "error": {
                        "name": ["Role name already exists"],
                        "permission_ids": ["At least one permission must be selected"],
                    },
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get role details",
        description="Retrieve detailed information about a specific role",
        tags=["3.1: Roles"],
        examples=[
            OpenApiExample(
                "Get role success",
                description="Example response when retrieving a role",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "VT001",
                        "name": "System Admin",
                        "description": "Full system access with all permissions",
                        "is_system_role": True,
                        "created_by": "System",
                        "permissions_detail": [
                            {
                                "id": 1,
                                "code": "user.create",
                                "name": "Create User",
                                "description": "Permission to create users",
                                "module": "Core",
                                "submodule": "User Management",
                            },
                            {
                                "id": 2,
                                "code": "user.update",
                                "name": "Update User",
                                "description": "Permission to update users",
                                "module": "Core",
                                "submodule": "User Management",
                            },
                        ],
                        "created_at": "2025-01-01T00:00:00Z",
                        "updated_at": "2025-01-01T00:00:00Z",
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Get role not found",
                description="Error response when role is not found",
                value={"success": False, "error": "Role not found"},
                response_only=True,
                status_codes=["404"],
            ),
        ],
    ),
    update=extend_schema(
        summary="Update role",
        description="Update role information",
        tags=["3.1: Roles"],
        examples=[
            OpenApiExample(
                "Update role request",
                description="Example request to update a role",
                value={
                    "name": "Senior Manager",
                    "description": "Senior management role",
                    "permission_ids": [1, 2, 3, 5, 10, 15],
                },
                request_only=True,
            ),
            OpenApiExample(
                "Update role success",
                description="Success response when updating a role",
                value={
                    "success": True,
                    "data": {
                        "id": 10,
                        "code": "VT010",
                        "name": "Senior Manager",
                        "description": "Senior management role",
                        "is_system_role": False,
                        "created_by": "admin@example.com",
                        "permissions_detail": [
                            {
                                "id": 1,
                                "code": "user.create",
                                "name": "Create User",
                                "description": "",
                                "module": "Core",
                                "submodule": "User Management",
                            }
                        ],
                        "created_at": "2025-01-15T14:20:00Z",
                        "updated_at": "2025-01-16T09:15:00Z",
                    },
                },
                response_only=True,
            ),
        ],
    ),
    partial_update=extend_schema(
        summary="Partially update role",
        description="Partially update role information",
        tags=["3.1: Roles"],
        examples=[
            OpenApiExample(
                "Partial update request",
                description="Example request to partially update a role",
                value={"description": "Updated description for the role"},
                request_only=True,
            ),
            OpenApiExample(
                "Partial update success",
                description="Success response when partially updating a role",
                value={
                    "success": True,
                    "data": {
                        "id": 10,
                        "code": "VT010",
                        "name": "Project Manager",
                        "description": "Updated description for the role",
                        "is_system_role": False,
                        "created_by": "admin@example.com",
                        "permissions_detail": [
                            {
                                "id": 1,
                                "code": "user.create",
                                "name": "Create User",
                                "description": "",
                                "module": "Core",
                                "submodule": "User Management",
                            }
                        ],
                        "created_at": "2025-01-15T14:20:00Z",
                        "updated_at": "2025-01-16T11:30:00Z",
                    },
                },
                response_only=True,
            ),
        ],
    ),
    destroy=extend_schema(
        summary="Delete role",
        description="Delete role from the system",
        tags=["3.1: Roles"],
        examples=[
            OpenApiExample(
                "Delete role success",
                description="Success response when deleting a role",
                value=None,
                response_only=True,
                status_codes=["204"],
            ),
            OpenApiExample(
                "Delete role error",
                description="Error response when role cannot be deleted (e.g., system role or role in use)",
                value={"success": False, "detail": "Cannot delete system role"},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
)
class RoleViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for Role model"""

    queryset = Role.objects.prefetch_related("permissions").all()
    serializer_class = RoleSerializer
    filterset_class = RoleFilterSet
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    search_fields = ["name", "code", "description"]
    ordering_fields = ["code", "name", "created_at"]
    ordering = ["code"]

    # Permission registration attributes
    module = _("Core")
    submodule = _("Role Management")
    permission_prefix = "role"
    PERMISSION_REGISTERED_ACTIONS = {
        "clone": {
            "name_template": _("Clone role"),
            "description_template": _("Clone an existing role"),
        },
    }

    def _generate_clone_name(self, base_name: str) -> str:
        """Generate a unique name for the cloned role."""
        sanitized_name = base_name.strip()
        candidate = f"{sanitized_name}{ROLE_CLONE_SUFFIX}"
        suffix_counter = 2

        while Role.objects.filter(name=candidate).exists():
            candidate = f"{sanitized_name}{ROLE_CLONE_SUFFIX}-{suffix_counter}"
            suffix_counter += 1

        return candidate

    @extend_schema(
        summary="Clone role",
        description="Clone an existing role by duplicating its details and permissions while ensuring the cloned role "
        "is not marked as a system role.",
        tags=["3.1: Roles"],
        request=None,
        responses={201: RoleSerializer},
        examples=[
            OpenApiExample(
                "Clone role request",
                description="No request body is needed when cloning a role.",
                value={},
                request_only=True,
            ),
            OpenApiExample(
                "Clone role success",
                description="Example response after cloning a role",
                value={
                    "success": True,
                    "data": {
                        "id": 12,
                        "code": "VT012",
                        "name": "Project Manager-copy",
                        "description": "Manages projects and teams",
                        "is_system_role": False,
                        "created_by": "admin@example.com",
                        "permissions_detail": [
                            {
                                "id": 1,
                                "code": "user.create",
                                "name": "Create User",
                                "description": "Permission to create users",
                                "module": "Core",
                                "submodule": "User Management",
                            },
                            {
                                "id": 2,
                                "code": "user.update",
                                "name": "Update User",
                                "description": "Permission to update users",
                                "module": "Core",
                                "submodule": "User Management",
                            },
                        ],
                        "created_at": "2025-01-20T09:30:00Z",
                        "updated_at": "2025-01-20T09:30:00Z",
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["201"],
            ),
            OpenApiExample(
                "Clone role not found",
                description="Error response when the target role does not exist",
                value={"success": False, "data": None, "error": "Role not found"},
                response_only=True,
                status_codes=["404"],
            ),
        ],
    )
    @action(detail=True, methods=["post"], url_path="clone")
    def clone(self, request, *args, **kwargs):
        """Clone an existing role and return the newly created role."""
        source_role = self.get_object()
        clone_data = {
            "name": self._generate_clone_name(source_role.name),
            "description": source_role.description,
            "permission_ids": list(source_role.permissions.values_list("id", flat=True)),
        }

        serializer = self.get_serializer(data=clone_data)
        serializer.is_valid(raise_exception=True)
        new_role = serializer.save()

        response_serializer = self.get_serializer(new_role)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

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
