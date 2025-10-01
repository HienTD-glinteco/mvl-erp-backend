import logging

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.core.api.serializers.auth import PasswordResetSerializer
from apps.core.models import PasswordResetOTP
from apps.core.tasks.sms import send_otp_sms_task

logger = logging.getLogger(__name__)


class LoginRateThrottle(AnonRateThrottle):
    scope = "login"
    rate = "5/min"


class PasswordResetView(APIView):
    """
    API endpoint for password reset request.

    Sends password reset instructions via Email or SMS and returns reset_token.
    """

    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]
    serializer_class = PasswordResetSerializer

    @extend_schema(
        summary="Yêu cầu đặt lại mật khẩu",
        description="Gửi hướng dẫn đặt lại mật khẩu qua email hoặc SMS dựa trên email hoặc số điện thoại",
        responses={
            200: OpenApiResponse(description="OTP đã được gửi"),
            400: OpenApiResponse(description="Thông tin không hợp lệ"),
            429: OpenApiResponse(description="Quá nhiều yêu cầu đặt lại mật khẩu"),
            500: OpenApiResponse(description="Lỗi hệ thống khi gửi OTP"),
        },
    )
    def post(self, request):
        serializer = PasswordResetSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.validated_data["user"]
            identifier = (request.data.get("identifier") or "").strip()
            is_email = "@" in identifier

            # Create a password reset request with OTP via manager
            reset_request, otp_code = PasswordResetOTP.objects.create_request(
                user, channel=("email" if is_email else "sms")
            )

            # Dispatch OTP via chosen channel
            if is_email:
                # Keep existing email behavior (no OTP content change here)
                sent = serializer.send_reset_email(user)
                if not sent:
                    logger.error(f"Failed to send password reset email for user {user.username}")
                message = "Mã OTP đặt lại mật khẩu đã được gửi đến email của bạn. Mã có hiệu lực trong 3 phút."
                email_hint = (
                    f"{user.email[:3]}***@{user.email.split('@')[1]}" if user.email and "@" in user.email else None
                )
                response_payload = {
                    "message": message,
                    "reset_token": reset_request.reset_token,
                    "email_hint": email_hint,
                    "expires_at": reset_request.expires_at.isoformat(),
                }
            else:
                # Send via SMS using third-party API
                phone = user.phone_number or identifier
                try:
                    send_otp_sms_task.delay(phone, otp_code)
                    logger.info(f"Password reset OTP SMS queued for user {user.username} phone {phone}")
                except Exception as e:
                    logger.error(f"Failed to queue SMS OTP for user {user.username}: {e}")
                masked = None
                if phone:
                    # Basic masking: show last 2-3 digits
                    last = phone[-2:]
                    masked = f"***{last}"
                message = "Mã OTP đặt lại mật khẩu đã được gửi qua SMS. Mã có hiệu lực trong 3 phút."
                response_payload = {
                    "message": message,
                    "reset_token": reset_request.reset_token,
                    "phone_hint": masked,
                    "expires_at": reset_request.expires_at.isoformat(),
                }

            return Response(response_payload, status=status.HTTP_200_OK)

        logger.warning(f"Invalid password reset attempt: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
