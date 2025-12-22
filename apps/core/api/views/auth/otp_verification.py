import logging

from django.conf import settings
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.audit_logging import LogAction, log_audit_event
from apps.core.api.authentication import get_request_client
from apps.core.api.serializers.auth import OTPVerificationSerializer
from apps.core.api.serializers.auth.responses import OTPVerificationResponseSerializer
from apps.core.models.device import UserDevice
from apps.core.utils.jwt import revoke_user_outstanding_tokens
from apps.notifications.models import Notification
from apps.notifications.utils import create_notification
from libs.request_utils import UNKNOWN_IP, get_client_ip, get_user_agent

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
        summary="Verify OTP code",
        description="Verify OTP code and return JWT tokens to complete login.",
        tags=["1.1: Auth"],
        responses={
            200: OTPVerificationResponseSerializer,
            400: OpenApiResponse(description="Invalid or expired OTP code"),
            403: OpenApiResponse(description="Web access is not allowed for this role"),
            409: OpenApiResponse(description="Device conflict"),
            429: OpenApiResponse(description="Too many verification requests"),
        },
        examples=[
            OpenApiExample(
                "Web verify OTP request",
                value={"username": "manager01", "otp_code": "123456", "device_id": "web-device-abc"},
                request_only=True,
            ),
            OpenApiExample(
                "Mobile verify OTP request",
                value={
                    "username": "employee01",
                    "otp_code": "123456",
                    "device_id": "mobile-device-001",
                    "platform": "android",
                    "push_token": "push-token-001",
                },
                request_only=True,
            ),
            OpenApiExample(
                "OTP verify success",
                value={
                    "success": True,
                    "data": {
                        "message": "Login successful.",
                        "user": {
                            "id": "00000000-0000-0000-0000-000000000000",
                            "username": "manager01",
                            "email": "manager01@example.com",
                            "full_name": "Manager User",
                        },
                        "tokens": {"access": "<access.jwt>", "refresh": "<refresh.jwt>"},
                    },
                    "error": None,
                },
                response_only=True,
            ),
            OpenApiExample(
                "Device conflict",
                value={
                    "success": False,
                    "data": None,
                    "error": {
                        "detail": "You are attempting to login from a different device. Please use the device change request process to change your device."
                    },
                },
                response_only=True,
                status_codes=["409"],
            ),
        ],
    )
    def post(self, request):
        client = get_request_client(request)
        serializer = OTPVerificationSerializer(data=request.data, context={"client": client})

        if serializer.is_valid(raise_exception=True):
            user = serializer.validated_data["user"]
            device_id = serializer.validated_data["device_id"]

            if (
                client == UserDevice.Client.WEB
                and getattr(getattr(user, "role", None), "code", None) == settings.HRM_EMPLOYEE_ROLE_CODE
            ):
                return Response(
                    {"detail": _("Web access is not allowed for this role.")},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Enforce single session per user using SimpleJWT blacklist
            revoked = revoke_user_outstanding_tokens(user)
            if revoked:
                logger.info(f"Revoked {revoked} previous refresh token(s) for user {user.username}")

            # Generate new tokens
            tokens = serializer.get_tokens(user, device_id, client=client)

            logger.info(f"User {user.username} completed login successfully")

            # Log audit event for successful login
            # For authentication events, set object_type to Employee if user has employee record
            try:
                modified_object = user.employee
            except Exception:
                modified_object = None

            log_audit_event(
                action=LogAction.LOGIN,
                modified_object=modified_object,
                user=user,
                request=request,
                change_message=f"User {user.username} logged in successfully",
            )

            # Create login notification with IP address and device info
            ip_address = get_client_ip(request) or UNKNOWN_IP
            user_agent = get_user_agent(request)

            # Create a user-friendly message with IP address
            login_message = _("Your account was logged in from IP address: {ip_address}").format(ip_address=ip_address)

            create_notification(
                actor=user,
                recipient=user,
                verb=_("logged in"),
                message=login_message,
                extra_data={
                    "ip_address": ip_address,
                    "user_agent": user_agent,
                },
                delivery_method=Notification.DeliveryMethod.FIREBASE,
            )

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
