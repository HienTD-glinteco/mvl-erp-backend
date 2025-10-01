import logging

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.core.api.serializers.auth.password_reset_change_password import (
    PasswordResetChangePasswordSerializer,
)

logger = logging.getLogger(__name__)


class LoginRateThrottle(AnonRateThrottle):
    scope = "login"
    rate = "5/min"


class PasswordResetChangePasswordView(APIView):
    """
    API endpoint for changing password after OTP verification in forgot password flow.

    Step 3 of forgot password flow - changes password using reset_token after OTP verification in step 2.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [LoginRateThrottle]
    serializer_class = PasswordResetChangePasswordSerializer

    @extend_schema(
        summary="Đặt lại mật khẩu mới (Bước 3: Thay đổi mật khẩu)",
        description="Đặt lại mật khẩu mới sau khi xác thực OTP thành công (Bước 2). Sử dụng reset_token (đã dùng ở bước 2).",
        responses={
            200: OpenApiResponse(description="Mật khẩu đã được thay đổi thành công"),
            400: OpenApiResponse(description="Thông tin không hợp lệ hoặc reset_token đã hết hạn/chưa được xác thực"),
            429: OpenApiResponse(description="Quá nhiều yêu cầu"),
        },
    )
    def post(self, request):
        serializer = PasswordResetChangePasswordSerializer(data=request.data, context={"request": request})

        if serializer.is_valid():
            user = serializer.save()

            logger.info(f"Password successfully reset for user {user} via forgot password flow")
            return Response(
                {"message": "Mật khẩu đã được đặt lại thành công. Tất cả phiên đăng nhập cũ đã bị đăng xuất."},
                status=status.HTTP_200_OK,
            )

        logger.warning(f"Invalid password reset change attempt: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
