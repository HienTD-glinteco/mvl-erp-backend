"""
Permission schema mixin for automatic x-permissions in OpenAPI docs.

This module provides a mixin that auto-generates x-permissions vendor extension
for DRF ViewSet CRUD actions based on the existing RBAC implementation.
"""

from typing import Any


class PermissionSchemaMixin:
    """
    Mixin for ViewSets to auto-generate x-permissions in OpenAPI schema.

    This mixin provides the get_schema_operation_extensions() method that
    drf-spectacular's AutoSchema calls to add vendor extensions to operations.

    For standard and registered actions, permissions are auto-generated using
    the format: {permission_prefix}.{action_name}

    This aligns with the existing PermissionRegistrationMixin.get_registered_permissions()
    which generates permission codes like "project.list", "project.create", etc.

    For custom actions not in STANDARD_ACTIONS or PERMISSION_REGISTERED_ACTIONS,
    use @extend_schema(extensions={"x-permissions": [...]}) explicitly.

    Class Attributes:
        permission_prefix (str): Prefix for permission codes (e.g., "project")

    Example:
        class ProjectViewSet(PermissionSchemaMixin, BaseModelViewSet):
            permission_prefix = "project"

        This generates:
            - list: ["project.list"]
            - retrieve: ["project.retrieve"]
            - create: ["project.create"]
            - update: ["project.update"]
            - partial_update: ["project.partial_update"]
            - destroy: ["project.destroy"]
    """

    permission_prefix: str = ""

    def get_schema_operation_extensions(self) -> dict[str, Any]:
        """
        Return OpenAPI vendor extensions for the current operation.

        This method is called by drf-spectacular's AutoSchema during schema generation.
        It returns x-permissions based on the current action and permission configuration.

        The permission code format follows PermissionRegistrationMixin.get_registered_permissions():
        {permission_prefix}.{action_name}

        Returns:
            dict: OpenAPI extensions with x-permissions key
        """
        # Get the current action
        action = getattr(self, "action", None)
        if not action:
            return {}

        # Get permission_prefix, skip if not defined
        permission_prefix = getattr(self, "permission_prefix", "")
        if not permission_prefix:
            return {}

        # Get STANDARD_ACTIONS from PermissionRegistrationMixin (if available)
        standard_actions = getattr(self, "STANDARD_ACTIONS", {})

        # Get PERMISSION_REGISTERED_ACTIONS for custom registered actions
        registered_actions = getattr(self, "PERMISSION_REGISTERED_ACTIONS", {})

        # Check if this is a standard action or registered action
        if action in standard_actions or action in registered_actions:
            permission_code = f"{permission_prefix}.{action}"
            return {"x-permissions": [permission_code]}

        # For custom actions not in STANDARD_ACTIONS or PERMISSION_REGISTERED_ACTIONS,
        # return empty - they should use @extend_schema explicitly
        return {}
