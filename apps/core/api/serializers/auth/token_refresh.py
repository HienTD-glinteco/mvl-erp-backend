from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings

from apps.core.utils.jwt import get_mobile_token_version


class ClientAwareTokenRefreshSerializer(TokenRefreshSerializer):
    """Ensure custom claims are preserved when refreshing tokens."""

    def validate(self, attrs):
        """Validate and refresh the token by copy logic from base class, preserving custom claims."""

        refresh = self.token_class(attrs["refresh"])

        user_id = refresh.payload.get(api_settings.USER_ID_CLAIM, None)
        if user_id and (user := get_user_model().objects.get(**{api_settings.USER_ID_FIELD: user_id})):
            if not api_settings.USER_AUTHENTICATION_RULE(user):
                raise AuthenticationFailed(
                    self.error_messages["no_active_account"],
                    "no_active_account",
                )

        current_tv = get_mobile_token_version(user_id=user_id)
        refresh["tv"] = current_tv
        for claim in ("client", "device_id", "tv"):
            if claim in refresh:
                refresh.access_token[claim] = refresh[claim]

        data = {"access": str(refresh.access_token)}

        if api_settings.ROTATE_REFRESH_TOKENS:
            if api_settings.BLACKLIST_AFTER_ROTATION:
                try:
                    # Attempt to blacklist the given refresh token
                    refresh.blacklist()
                except AttributeError:
                    # If blacklist app not installed, `blacklist` method will
                    # not be present
                    pass

            refresh.set_jti()
            refresh.set_exp()
            refresh.set_iat()
            refresh.outstand()

            data["refresh"] = str(refresh)
        return data
