from django.utils.translation import gettext as _
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission


class RoleBasedPermission(BasePermission):
    """
    Permission class that checks if a user has the required permission
    based on their assigned roles.

    This class works in conjunction with the @register_permission decorator.
    It reads the permission_code metadata attached to the view and verifies
    if the user has access through their roles.

    Usage:
        @api_view(["GET"])
        @permission_classes([RoleBasedPermission])
        @register_permission("document.list", _("View document list"))
        def document_list(request):
            return Response({"ok": True})
    """

    def has_permission(self, request, view):
        # Get permission code from view metadata
        # For function-based views, check the view itself
        # For class-based views, check the specific method handler
        permission_code = None

        if hasattr(view, "_permission_code"):
            # Function-based view
            permission_code = view._permission_code
        elif hasattr(view, request.method.lower()):
            # Class-based view - check the method handler
            method_handler = getattr(view, request.method.lower())
            permission_code = getattr(method_handler, "_permission_code", None)

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
