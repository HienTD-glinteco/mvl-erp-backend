import logging
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from drf_spectacular.utils import extend_schema, OpenApiResponse

from apps.core.api.serializers.auth import LoginSerializer

logger = logging.getLogger(__name__)


class LoginRateThrottle(AnonRateThrottle):
    scope = "login"
    rate = "5/min"  # Allow 5 login attempts per minute


class LoginView(APIView):
    """
    API endpoint for user login with username and password.

    After successful credential verification, sends OTP to user's email.
    """

    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]
    serializer_class = LoginSerializer

    @extend_schema(
        summary="Đăng nhập với tên đăng nhập và mật khẩu",
        description="Xác thực thông tin đăng nhập và gửi mã OTP qua email",
        responses={
            200: OpenApiResponse(description="OTP đã được gửi thành công"),
            400: OpenApiResponse(description="Thông tin đăng nhập không hợp lệ"),
            429: OpenApiResponse(description="Quá nhiều yêu cầu đăng nhập"),
            500: OpenApiResponse(description="Lỗi hệ thống khi gửi OTP"),
        },
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.validated_data["user"]

            # Send OTP email
            if serializer.send_otp_email(user):
                logger.info(
                    f"Login attempt successful for user {user.username}, OTP sent"
                )
                response_data = {
                    "message": "Mã OTP đã được gửi đến email của bạn. Vui lòng kiểm tra email và nhập mã OTP để hoàn tất đăng nhập.",
                    "username": user.username,
                    "email_hint": f"{user.email[:3]}***@{user.email.split('@')[1]}",
                }
                return Response(response_data, status=status.HTTP_200_OK)
            else:
                logger.error(f"Failed to send OTP email for user {user.username}")
                return Response(
                    {"message": "Không thể gửi mã OTP. Vui lòng thử lại sau."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        logger.warning(f"Invalid login attempt: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
