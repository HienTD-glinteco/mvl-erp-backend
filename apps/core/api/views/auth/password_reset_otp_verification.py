import logging

from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.api.serializers.auth.password_reset_otp_verification import (
    PasswordResetOTPVerificationSerializer,
)
from apps.core.api.serializers.auth.responses import PasswordResetOTPVerificationResponseSerializer
from apps.core.utils.jwt import revoke_user_outstanding_tokens

logger = logging.getLogger(__name__)


class LoginRateThrottle(AnonRateThrottle):
    scope = "login"
    rate = "5/min"


class PasswordResetOTPVerificationView(APIView):
    """
    Step 2 of forgot password: verify reset_token + OTP and return JWT tokens

    so client can authorize the final change-password request.
    """

    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]
    serializer_class = PasswordResetOTPVerificationSerializer

    @extend_schema(
        summary=_("Verify OTP (Step 2) and return JWT"),
        description=_("Verify reset_token + OTP, then return access/refresh token for password change step."),
        responses={
            200: PasswordResetOTPVerificationResponseSerializer,
            400: OpenApiResponse(description=_("Invalid reset token or OTP code")),
            429: OpenApiResponse(description=_("Too many verification requests")),
        },
    )
    def post(self, request):
        serializer = PasswordResetOTPVerificationSerializer(data=request.data)

        if serializer.is_valid():
            reset_request = serializer.validated_data["reset_request"]
            user = reset_request.user

            # Single-session: revoke previous outstanding refresh tokens
            revoked = revoke_user_outstanding_tokens(user)
            if revoked:
                logger.info(f"Revoked {revoked} previous refresh token(s) for user {user.username}")

            # Issue new tokens
            refresh = RefreshToken.for_user(user)
            tokens = {"access": str(refresh.access_token), "refresh": str(refresh)}

            logger.info(f"Password reset OTP verified for user {user.username}; issued JWT tokens")
            return Response(
                {
                    "message": _("Valid OTP code. JWT issued for password change."),
                    "tokens": tokens,
                },
                status=status.HTTP_200_OK,
            )

        logger.warning(f"Invalid password reset OTP verification attempt: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
