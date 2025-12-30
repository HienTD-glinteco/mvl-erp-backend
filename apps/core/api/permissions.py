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
