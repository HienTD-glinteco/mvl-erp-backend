import logging

from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.core.api.serializers.auth import OTPVerificationSerializer
from apps.core.api.serializers.auth.responses import OTPVerificationResponseSerializer
from apps.core.utils.jwt import revoke_user_outstanding_tokens

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
        summary=_("Verify OTP code"),
        description=_("Verify OTP code and return JWT tokens to complete login"),
        responses={
            200: OTPVerificationResponseSerializer,
            400: OpenApiResponse(description=_("Invalid or expired OTP code")),
            429: OpenApiResponse(description=_("Too many verification requests")),
        },
    )
    def post(self, request):
        serializer = OTPVerificationSerializer(data=request.data)

        if serializer.is_valid(raise_exception=True):
            user = serializer.validated_data["user"]
            device_id = serializer.validated_data["device_id"]

            # Enforce single session per user using SimpleJWT blacklist
            revoked = revoke_user_outstanding_tokens(user)
            if revoked:
                logger.info(f"Revoked {revoked} previous refresh token(s) for user {user.username}")

            # Generate new tokens
            tokens = serializer.get_tokens(user, device_id)

            logger.info(f"User {user.username} completed login successfully")
            response_data = {
                "message": _("Login successful."),
                "user": {
                    "id": str(user.id),
                    "username": user.username,
                    "email": user.email,
                    "full_name": user.get_full_name(),
                },
                "tokens": tokens,
            }
            return Response(response_data, status=status.HTTP_200_OK)
