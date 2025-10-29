"""Permissions for mail template operations."""

from django.utils.translation import gettext as _
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission


class IsTemplateEditor(BasePermission):
    """Permission to edit/save templates.

    Allows:
    - Staff users
    - Users with is_template_editor flag
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise PermissionDenied(_("Authentication required"))

        if request.user.is_staff:
            return True

        if hasattr(request.user, "is_template_editor") and request.user.is_template_editor:
            return True

        raise PermissionDenied(_("Template editor permission required"))


class CanSendMail(BasePermission):
    """Permission to send bulk emails.

    Allows:
    - Staff users
    - Users with can_send_mail flag
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise PermissionDenied(_("Authentication required"))

        if request.user.is_staff:
            return True

        if hasattr(request.user, "can_send_mail") and request.user.can_send_mail:
            return True

        raise PermissionDenied(_("Mail sending permission required"))


class CanPreviewRealData(BasePermission):
    """Permission to preview templates with real data.

    Allows:
    - Staff users
    - Users with can_preview_real flag
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise PermissionDenied(_("Authentication required"))

        if request.user.is_staff:
            return True

        if hasattr(request.user, "can_preview_real") and request.user.can_preview_real:
            return True

        raise PermissionDenied(_("Real data preview permission required"))
