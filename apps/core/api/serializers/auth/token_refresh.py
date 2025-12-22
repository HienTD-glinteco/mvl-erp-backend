from __future__ import annotations

from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken


class ClientAwareTokenRefreshSerializer(TokenRefreshSerializer):
    """Ensure custom claims are preserved when refreshing tokens."""

    def validate(self, attrs):
        data = super().validate(attrs)

        original_refresh = RefreshToken(attrs["refresh"])

        # Replace access token so it always contains required claims.
        access = original_refresh.access_token
        for claim in ("client", "device_id", "tv"):
            if claim in original_refresh:
                access[claim] = original_refresh[claim]
        data["access"] = str(access)

        # If rotation is enabled, the parent serializer returns a new refresh token string.
        # Copy required claims over to the rotated refresh token as well.
        if "refresh" in data:
            rotated = RefreshToken(data["refresh"])
            for claim in ("client", "device_id", "tv"):
                if claim in original_refresh:
                    rotated[claim] = original_refresh[claim]
            data["refresh"] = str(rotated)

        return data
