from __future__ import annotations

from typing import Any, Optional, cast

from django.conf import settings
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.request import Request
from rest_framework_simplejwt.authentication import AuthUser, JWTAuthentication, Token

from apps.core.utils.jwt import get_mobile_token_version


def get_request_client(request: Request) -> str:
    if request.path.startswith(settings.MOBILE_PATH_PREFIX):
        return settings.MOBILE_CLIENT_IDENTIFIER
    return settings.WEB_CLIENT_IDENTIFIER


class ClientAwareJWTAuthentication(JWTAuthentication):
    """JWT authentication that enforces client and mobile token versioning."""

    def authenticate(self, request: Request) -> Optional[tuple[AuthUser, Token]]:
        result = super().authenticate(request)
        if result is None:
            return None

        user, token = result
        user_any: Any = user

        route_client = get_request_client(request)
        token_client = token.get("client")
        if token_client != route_client:
            raise AuthenticationFailed(_("Token client does not match endpoint client."))

        # Check token version for both mobile and web clients
        tv = token.get("tv")
        if tv is not None:  # Only check if token has version (for backward compatibility)
            try:
                tv_int = int(tv)
            except (TypeError, ValueError):
                raise AuthenticationFailed(_("Invalid token version."))
            user_id = str(getattr(user_any, "id", "") or getattr(user_any, "pk", ""))
            current_tv = get_mobile_token_version(user_id=user_id)
            if tv_int != current_tv:
                raise AuthenticationFailed(_("Token has been revoked."))

        if route_client == settings.WEB_CLIENT_IDENTIFIER:
            role = getattr(user_any, "role", None)
            role_code = getattr(role, "code", None)
            if role_code == settings.HRM_EMPLOYEE_ROLE_CODE and request.path.startswith("/api/"):
                # Allow auth endpoints to return their own error responses.
                if request.path.startswith("/api/auth/") or request.path.startswith("/api/token/"):
                    user_auth = cast(AuthUser, cast(Any, user))
                    return (user_auth, token)
                raise PermissionDenied(_("Web access is not allowed for this role."))

        user_auth = cast(AuthUser, cast(Any, user))
        return (user_auth, token)
