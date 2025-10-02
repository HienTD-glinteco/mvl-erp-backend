"""Token management views with proper API documentation."""

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework_simplejwt.views import (
    TokenRefreshView as SimpleJWTTokenRefreshView,
    TokenVerifyView as SimpleJWTTokenVerifyView,
)

from apps.core.api.serializers.auth.responses import TokenRefreshResponseSerializer


class TokenRefreshView(SimpleJWTTokenRefreshView):
    """
    Làm mới JWT access token bằng refresh token.

    Endpoint này sử dụng refresh token để tạo access token mới.
    Nếu rotation được bật, refresh token mới cũng sẽ được trả về.
    """

    @extend_schema(
        summary="Làm mới access token",
        description="Sử dụng refresh token để tạo access token mới. "
        "Nếu ROTATE_REFRESH_TOKENS được bật, refresh token cũ sẽ bị thu hồi "
        "và refresh token mới sẽ được trả về.",
        responses={
            200: TokenRefreshResponseSerializer,
            401: OpenApiResponse(description="Refresh token không hợp lệ hoặc đã hết hạn"),
        },
        tags=["Token Management"],
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class TokenVerifyView(SimpleJWTTokenVerifyView):
    """
    Xác thực tính hợp lệ của một JWT token.

    Endpoint này kiểm tra xem token có hợp lệ và chưa hết hạn hay không.
    """

    @extend_schema(
        summary="Xác thực token",
        description="Kiểm tra tính hợp lệ của JWT token (access hoặc refresh). "
        "Trả về 200 nếu token hợp lệ, 401 nếu không hợp lệ.",
        responses={
            200: OpenApiResponse(description="Token hợp lệ"),
            401: OpenApiResponse(description="Token không hợp lệ hoặc đã hết hạn"),
        },
        tags=["Token Management"],
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
