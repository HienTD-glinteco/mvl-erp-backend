import logging
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from drf_spectacular.utils import extend_schema, OpenApiResponse

from apps.core.api.serializers.auth import PasswordResetSerializer

logger = logging.getLogger(__name__)


class LoginRateThrottle(AnonRateThrottle):
    scope = "login"
    rate = "5/min"


class PasswordResetView(APIView):
    """
    API endpoint for password reset request.

    Sends password reset instructions to user's email.
    """

    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]
    serializer_class = PasswordResetSerializer

    @extend_schema(
        summary="Yêu cầu đặt lại mật khẩu",
        description="Gửi hướng dẫn đặt lại mật khẩu qua email dựa trên email hoặc số điện thoại",
        responses={
            200: OpenApiResponse(description="Email hướng dẫn đã được gửi"),
            400: OpenApiResponse(description="Thông tin không hợp lệ"),
            429: OpenApiResponse(description="Quá nhiều yêu cầu đặt lại mật khẩu"),
            500: OpenApiResponse(description="Lỗi hệ thống khi gửi email"),
        },
    )
    def post(self, request):
        serializer = PasswordResetSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.validated_data["user"]

            if serializer.send_reset_email(user):
                logger.info(f"Password reset email sent for user {user.username}")
                return Response(
                    {
                        "message": "Hướng dẫn đặt lại mật khẩu đã được gửi đến email của bạn."
                    },
                    status=status.HTTP_200_OK,
                )
            else:
                logger.error(
                    f"Failed to send password reset email for user {user.username}"
                )
                return Response(
                    {
                        "message": "Không thể gửi email đặt lại mật khẩu. Vui lòng thử lại sau."
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        logger.warning(f"Invalid password reset attempt: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
