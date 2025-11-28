import logging

from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.core.api.serializers.auth import LoginSerializer
from apps.core.api.serializers.auth.responses import LoginResponseSerializer

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
        summary="Login with username and password",
        description="Authenticate login credentials and send OTP code via email",
        responses={
            200: LoginResponseSerializer,
            400: OpenApiResponse(description="Invalid login credentials"),
            429: OpenApiResponse(description="Too many login requests"),
            500: OpenApiResponse(description="System error while sending OTP"),
        },
        tags=["1.1 Auth"],
        examples=[
            OpenApiExample(
                "Login request",
                description="Example login request",
                value={"username": "admin", "password": "SecurePassword123!"},
                request_only=True,
            ),
            OpenApiExample(
                "Login success - OTP sent",
                description="Success response when OTP is sent to email",
                value={
                    "success": True,
                    "data": {
                        "message": "OTP code has been sent to your email. Please check your email and enter the OTP code to complete login.",
                        "username": "admin",
                        "email_hint": "adm***@example.com",
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Login error - invalid credentials",
                description="Error response when credentials are invalid",
                value={"success": False, "error": {"username": ["Invalid username or password"]}},
                response_only=True,
                status_codes=["400"],
            ),
            OpenApiExample(
                "Login error - too many attempts",
                description="Error response when rate limit is exceeded",
                value={"success": False, "error": "Too many login requests. Please try again later."},
                response_only=True,
                status_codes=["429"],
            ),
        ],
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.validated_data["user"]

            # Send OTP email
            if serializer.send_otp_email(user):
                logger.info(f"Login attempt successful for user {user.username}, OTP sent")
                response_data = {
                    "message": _(
                        "OTP code has been sent to your email. Please check your email and enter the OTP code to complete login."
                    ),
                    "username": user.username,
                    "email_hint": f"{user.email[:3]}***@{user.email.split('@')[1]}",
                }
                return Response(response_data, status=status.HTTP_200_OK)
            else:
                logger.error(f"Failed to send OTP email for user {user.username}")
                return Response(
                    {"message": _("Unable to send OTP code. Please try again later.")},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        logger.warning(f"Invalid login attempt: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
