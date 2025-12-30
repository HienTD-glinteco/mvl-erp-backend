"""
Base APIView with automatic permission registration.

This module provides a reusable APIView base class that integrates with the
existing PermissionRegistrationMixin logic to automatically register and
document permissions for standalone endpoints (non-ViewSet).
"""

from typing import Any, Dict, Optional

from django.utils.translation import gettext_lazy as _
from rest_framework.views import APIView

from libs.drf.mixin.permission import PermissionRegistrationMixin
from libs.drf.spectacular.permission_schema import PermissionSchemaMixin


class PermissionedAPIView(PermissionSchemaMixin, PermissionRegistrationMixin, APIView):
    """
    APIView base class with automatic permission handling and schema metadata.

    This class mirrors the behavior of BaseModelViewSet by combining
    PermissionRegistrationMixin (for permission metadata) and
    PermissionSchemaMixin (for OpenAPI extensions).
    """

    module: Any = ""
    submodule: Any = ""
    permission_prefix: str = ""

    # Default mapping between HTTP methods and permission action names.
    DEFAULT_PERMISSION_ACTION_MAP: Dict[str, Optional[str]] = {
        "get": "get",
        "post": "post",
        "put": "put",
        "patch": "patch",
        "delete": "delete",
        "head": None,
        "options": None,
    }
    permission_action_map: Dict[str, Optional[str]] = {}

    STANDARD_ACTIONS = {
        "get": {
            "name_template": _("GET {model_name}"),
            "description_template": _("Perform GET on {model_name}"),
        },
        "post": {
            "name_template": _("POST {model_name}"),
            "description_template": _("Perform POST on {model_name}"),
        },
        "put": {
            "name_template": _("PUT {model_name}"),
            "description_template": _("Perform PUT on {model_name}"),
        },
        "patch": {
            "name_template": _("PATCH {model_name}"),
            "description_template": _("Perform PATCH on {model_name}"),
        },
        "delete": {
            "name_template": _("DELETE {model_name}"),
            "description_template": _("Perform DELETE on {model_name}"),
        },
    }

    def get_permission_action(self, method: str) -> Optional[str]:
        """
        Resolve the permission action name for the given HTTP method.

        Subclasses can override permission_action_map to provide custom action names
        (e.g., {"get": "check_status"}). Returning None disables permission checks
        for that method.
        """
        method_lower = method.lower()
        action_map = {**self.DEFAULT_PERMISSION_ACTION_MAP, **getattr(self, "permission_action_map", {})}
        return action_map.get(method_lower)

    def get_schema_action(self, method: str) -> Optional[str]:
        """Helper used during schema generation."""
        return self.get_permission_action(method)

    def initial(self, request, *args, **kwargs):
        """Set the current action before running default APIView initial logic."""
        self.action = self.get_permission_action(request.method)
        return super().initial(request, *args, **kwargs)
