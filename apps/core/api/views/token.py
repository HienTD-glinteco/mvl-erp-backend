"""Token management views with proper API documentation."""

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework_simplejwt.views import (
    TokenRefreshView as SimpleJWTTokenRefreshView,
    TokenVerifyView as SimpleJWTTokenVerifyView,
)

from apps.core.api.serializers.auth.responses import TokenRefreshResponseSerializer


class TokenRefreshView(SimpleJWTTokenRefreshView):
    """
    Refresh JWT access token using refresh token.

    This endpoint uses a refresh token to generate a new access token.
    If rotation is enabled, a new refresh token will also be returned.
    """

    @extend_schema(
        summary="Refresh access token",
        description="Use refresh token to generate new access token. "
        "If ROTATE_REFRESH_TOKENS is enabled, the old refresh token will be revoked "
        "and a new refresh token will be returned.",
        responses={
            200: TokenRefreshResponseSerializer,
            401: OpenApiResponse(description="Invalid or expired refresh token"),
        },
        tags=["1.1 Auth"],
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
        tags=["1.1 Auth"],
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
