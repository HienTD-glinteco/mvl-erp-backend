import logging

from django.conf import settings
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import Throttled
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.audit_logging import LogAction, log_audit_event
from apps.core.api.authentication import get_request_client
from apps.core.api.serializers.auth import LoginSerializer
from apps.core.utils.jwt import revoke_user_outstanding_tokens
from apps.notifications.models import Notification
from apps.notifications.utils import create_notification
from libs.request_utils import UNKNOWN_IP, get_client_ip, get_user_agent

logger = logging.getLogger(__name__)


class LoginRateThrottle(AnonRateThrottle):
    scope = "login"
    rate = "5/min"  # Allow 5 login attempts per minute


class LoginView(APIView):
    """API endpoint for user login with username and password.

    Issues JWT tokens immediately (no OTP step).
    """

    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]
    serializer_class = LoginSerializer

    @extend_schema(
        summary="Login with username and password",
        description="Authenticate login credentials and return JWT tokens.",
        responses={
            200: OpenApiResponse(description="Login success"),
            400: OpenApiResponse(description="Invalid login credentials"),
            403: OpenApiResponse(description="Web access is not allowed for this role"),
            409: OpenApiResponse(description="Device conflict"),
            429: OpenApiResponse(description="Too many login requests"),
        },
        tags=["1.1: Auth"],
        examples=[
            OpenApiExample(
                "Web login request",
                value={"username": "manager01", "password": "SecurePassword123!", "device_id": "web-device-abc"},
                request_only=True,
            ),
            OpenApiExample(
                "Mobile login request",
                value={
                    "username": "employee01",
                    "password": "SecurePassword123!",
                    "device_id": "mobile-device-001",
                    "platform": "android",
                    "push_token": "push-token-001",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Login success",
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
        client = get_request_client(request)
        serializer = LoginSerializer(data=request.data, context={"client": client})
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]

        if client == "web" and getattr(getattr(user, "role", None), "code", None) == settings.HRM_EMPLOYEE_ROLE_CODE:
            return Response(
                {"detail": _("Web access is not allowed for this role.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        revoked = revoke_user_outstanding_tokens(user)
        if revoked:
            logger.info("Revoked %s previous refresh token(s) for user %s", revoked, user.username)

        tokens = serializer.get_tokens(user, client=client)

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

        ip_address = get_client_ip(request) or UNKNOWN_IP
        user_agent = get_user_agent(request)
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

    def check_throttles(self, request):
        """
        Override to provide custom error message on throttle exceed.
        """
        try:
            return super().check_throttles(request)
        except Throttled as exc:
            wait = getattr(exc, "wait", None)
            if wait:
                detail = _("Request was throttled. Expected available in %(wait)s seconds.") % {"wait": int(wait)}
            else:
                detail = _("Request was throttled. Please try again later.")
            raise Throttled(detail=detail, wait=wait)
