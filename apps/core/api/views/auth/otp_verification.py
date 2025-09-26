import logging
from django.contrib.sessions.models import Session
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from drf_spectacular.utils import extend_schema, OpenApiResponse

from apps.core.api.serializers.auth import OTPVerificationSerializer

logger = logging.getLogger(__name__)


class LoginRateThrottle(AnonRateThrottle):
    scope = "login"
    rate = "5/min"


class OTPVerificationView(APIView):
    """
    API endpoint for OTP verification and token generation.

    Completes the login process and returns JWT tokens.
    """

    permission_classes = (AllowAny,)
    throttle_classes = [LoginRateThrottle]
    serializer_class = OTPVerificationSerializer

    @extend_schema(
        summary="Xác thực mã OTP",
        description="Xác thực mã OTP và trả về JWT tokens để hoàn tất đăng nhập",
        responses={
            200: OpenApiResponse(description="Đăng nhập thành công, trả về tokens"),
            400: OpenApiResponse(description="Mã OTP không hợp lệ hoặc đã hết hạn"),
            429: OpenApiResponse(description="Quá nhiều yêu cầu xác thực"),
        },
    )
    def post(self, request):
        serializer = OTPVerificationSerializer(data=request.data)

        if serializer.is_valid(raise_exception=True):
            user = serializer.validated_data["user"]

            # Implement single session per user
            if user.active_session_key:
                try:
                    # Delete existing session
                    existing_session = Session.objects.get(
                        session_key=user.active_session_key
                    )
                    existing_session.delete()
                    logger.info(f"Deleted previous session for user {user.username}")
                except Session.DoesNotExist:
                    pass

            # Generate new tokens
            tokens = serializer.get_tokens(user)
            # Store new session key (we'll use the refresh token as session identifier)
            user.active_session_key = tokens["refresh"][
                :40
            ]  # Use first 40 chars as session key
            user.save(update_fields=["active_session_key"])

            logger.info(f"User {user.username} completed login successfully")
            response_data = {
                "message": "Đăng nhập thành công.",
                "user": {
                    "id": str(user.id),
                    "username": user.username,
                    "email": user.email,
                    "full_name": user.get_full_name(),
                },
                "tokens": tokens,
            }
            return Response(response_data, status=status.HTTP_200_OK)
