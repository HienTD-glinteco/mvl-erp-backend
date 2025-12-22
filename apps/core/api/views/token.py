"""Token management views with proper API documentation."""

from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework_simplejwt.views import (
    TokenRefreshView as SimpleJWTTokenRefreshView,
    TokenVerifyView as SimpleJWTTokenVerifyView,
)

from apps.core.api.serializers.auth.responses import TokenRefreshResponseSerializer
from apps.core.api.serializers.auth.token_refresh import ClientAwareTokenRefreshSerializer


class TokenRefreshView(SimpleJWTTokenRefreshView):
    serializer_class = ClientAwareTokenRefreshSerializer
    """
    Refresh JWT access token using refresh token.

    This endpoint uses a refresh token to generate a new access token.
    If rotation is enabled, a new refresh token will also be returned.
    """

    @extend_schema(
        summary="Refresh access token",
        description=(
            "Use refresh token to generate a new access token. "
            "If ROTATE_REFRESH_TOKENS is enabled, the old refresh token will be revoked "
            "and a new refresh token will be returned. "
            "Custom claims (client/device_id/tv) are preserved."
        ),
        responses={
            200: TokenRefreshResponseSerializer,
            401: OpenApiResponse(description="Invalid or expired refresh token"),
        },
        tags=["1.1: Auth"],
        examples=[
            OpenApiExample(
                "Refresh request",
                value={"refresh": "<refresh.jwt>"},
                request_only=True,
            ),
            OpenApiExample(
                "Refresh success",
                value={
                    "success": True,
                    "data": {"access": "<access.jwt>", "refresh": "<refresh.jwt>"},
                    "error": None,
                },
                response_only=True,
            ),
            OpenApiExample(
                "Refresh error",
                value={"success": False, "data": None, "error": "Invalid or expired refresh token"},
                response_only=True,
                status_codes=["401"],
            ),
        ],
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class TokenVerifyView(SimpleJWTTokenVerifyView):
    """
    Verify the validity of a JWT token.

    This endpoint checks whether a token is valid and has not expired.
    """

    @extend_schema(
        summary="Verify token",
        description="Check the validity of a JWT token (access or refresh). "
        "Returns 200 if token is valid, 401 if invalid.",
        responses={
            200: OpenApiResponse(description="Token is valid"),
            401: OpenApiResponse(description="Invalid or expired token"),
        },
        tags=["1.1: Auth"],
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
