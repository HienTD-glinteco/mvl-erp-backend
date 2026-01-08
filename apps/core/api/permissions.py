from django.utils.translation import gettext as _
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission


class RoleBasedPermission(BasePermission):
    """
    Permission class that checks if a user has the required permission
    based on their assigned roles.

    This permission class expects views to define `permission_prefix` and set
    `self.action` (automatically handled by BaseModelViewSet, PermissionedAPIView,
    and other classes that inherit PermissionRegistrationMixin).
    """

    def has_permission(self, request, view):
        """Verify that the authenticated user has the required permission."""
        permission_code = None

        if getattr(view, "permission_prefix", None) and getattr(view, "action", None):
            permission_code = f"{view.permission_prefix}.{view.action}"

        # If no permission code is set, allow access (view doesn't require permission)
        if not permission_code:
            return True

        # Check if user is authenticated
        if not request.user or not request.user.is_authenticated:
            raise PermissionDenied(_("You need to login to perform this action"))

        # Allow superusers
        if request.user.is_superuser:
            return True

        # Check if user has the required permission through their roles
        if request.user.has_permission(permission_code):
            return True

        # Deny access with a clear message
        raise PermissionDenied(_("You do not have permission to perform this action"))


class DataScopePermission(BasePermission):
    """
    Object-level permission that checks if user has access to the object's
    organizational unit based on their role's data scope.

    This permission class should be used together with RoleDataScopeFilterBackend.
    - FilterBackend: Filters list views
    - Permission: Blocks access to individual objects (retrieve, update, delete)

    Usage in ViewSet:
        class EmployeeViewSet(viewsets.ModelViewSet):
            permission_classes = [IsAuthenticated, RoleBasedPermission, DataScopePermission]
            filter_backends = [RoleDataScopeFilterBackend, ...]

            data_scope_config = {
                "branch_field": "branch",
                "block_field": "block",
                "department_field": "department",
            }

    Returns:
        - True: User has access to the object
        - PermissionDenied (403): User does not have access to the object
    """

    message = _("You do not have permission to access this data.")

    def has_permission(self, request, view):
        """
        List-level permission check.
        Always returns True because filtering is handled by RoleDataScopeFilterBackend.
        """
        return True

    def has_object_permission(self, request, view, obj):
        """
        Object-level permission check.
        Verifies user has access to the object's organizational unit.
        """
        user = request.user

        # Unauthenticated users are handled by IsAuthenticated
        if not user or not user.is_authenticated:
            return False

        # Superusers have full access
        if user.is_superuser:
            return True

        # Get allowed units for user
        from apps.hrm.utils.role_data_scope import collect_role_allowed_units

        allowed = collect_role_allowed_units(user)

        # ROOT scope has full access
        if allowed.has_all:
            return True

        # No allowed units = no access
        if allowed.is_empty:
            raise PermissionDenied(self.message)

        # Get config from view
        config = getattr(view, "data_scope_config", {})

        # Check if object is within allowed scope
        if not self._check_object_scope(obj, allowed, config):
            raise PermissionDenied(self.message)

        return True

    def _check_object_scope(self, obj, allowed, config):
        """
        Check if object is within user's allowed organizational scope.

        Performance optimized: Uses select_related data when available,
        falls back to DB query only when necessary.

        Args:
            obj: The model instance being accessed
            allowed: RoleAllowedUnits with user's allowed units
            config: Dict with field mappings from view

        Returns:
            bool: True if object is within scope
        """
        branch_field = config.get("branch_field", "branch")
        block_field = config.get("block_field", "block")
        department_field = config.get("department_field", "department")

        # Get organizational unit IDs from object
        branch_id = self._get_field_id(obj, branch_field)
        block_id = self._get_field_id(obj, block_field)
        department_id = self._get_field_id(obj, department_field)

        # Check each scope type
        if self._check_branch_scope(obj, allowed, branch_id, block_id, department_id, block_field, department_field):
            return True
        if self._check_block_scope(obj, allowed, block_id, department_id, department_field):
            return True
        if self._check_department_scope(allowed, department_id):
            return True

        return False

    def _check_branch_scope(self, obj, allowed, branch_id, block_id, department_id, block_field, department_field):
        """Check if object is within allowed branches"""
        if not allowed.branches:
            return False

        if branch_id and branch_id in allowed.branches:
            return True
        if block_id:
            block_branch_id = self._get_parent_branch_id(obj, block_field)
            if block_branch_id and block_branch_id in allowed.branches:
                return True
        if department_id:
            dept_branch_id = self._get_parent_branch_id(obj, department_field)
            if dept_branch_id and dept_branch_id in allowed.branches:
                return True
        return False

    def _check_block_scope(self, obj, allowed, block_id, department_id, department_field):
        """Check if object is within allowed blocks"""
        if not allowed.blocks:
            return False

        if block_id and block_id in allowed.blocks:
            return True
        if department_id:
            dept_block_id = self._get_parent_block_id(obj, department_field)
            if dept_block_id and dept_block_id in allowed.blocks:
                return True
        return False

    def _check_department_scope(self, allowed, department_id):
        """Check if object is within allowed departments"""
        if not allowed.departments:
            return False
        return department_id and department_id in allowed.departments

    def _get_field_id(self, obj, field_path):
        """
        Get field ID from object, preferring _id attribute to avoid extra queries.

        Args:
            obj: The model instance
            field_path: Path like "branch" or "employee__branch"

        Returns:
            The field ID or None
        """
        parts = field_path.split("__")
        value = obj

        for i, part in enumerate(parts):
            if value is None:
                return None
            # For the last part, try to get _id directly
            if i == len(parts) - 1:
                id_attr = f"{part}_id"
                if hasattr(value, id_attr):
                    return getattr(value, id_attr)
            value = getattr(value, part, None)

        # Return ID if it's a model instance
        if value is not None and hasattr(value, "id"):
            return value.id
        return value

    def _get_parent_branch_id(self, obj, field_path):
        """Get branch_id from a block or department field"""
        value = self._traverse_path(obj, field_path)
        if value is None:
            return None
        # Try to get branch_id directly (avoids extra query)
        if hasattr(value, "branch_id"):
            return value.branch_id
        if hasattr(value, "branch") and value.branch:
            return value.branch.id
        return None

    def _get_parent_block_id(self, obj, field_path):
        """Get block_id from a department field"""
        value = self._traverse_path(obj, field_path)
        if value is None:
            return None
        if hasattr(value, "block_id"):
            return value.block_id
        if hasattr(value, "block") and value.block:
            return value.block.id
        return None

    def _traverse_path(self, obj, field_path):
        """Traverse object path without getting IDs"""
        parts = field_path.split("__")
        value = obj
        for part in parts:
            if value is None:
                return None
            value = getattr(value, part, None)
        return value
