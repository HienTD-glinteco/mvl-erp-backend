import logging

from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.audit_logging import LogAction, log_audit_event
from apps.core.api.serializers.auth.password_reset_change_password import (
    PasswordResetChangePasswordSerializer,
)
from apps.core.api.serializers.auth.responses import PasswordResetChangePasswordResponseSerializer

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
        summary=_("Set new password (Step 3: Change password)"),
        description=_("Set new password after successful OTP verification (Step 2). Uses reset_token (from step 2)."),
        tags=["1.1: Auth"],
        responses={
            200: PasswordResetChangePasswordResponseSerializer,
            400: OpenApiResponse(description=_("Invalid information or reset_token has expired/not verified")),
            429: OpenApiResponse(description=_("Too many requests")),
        },
    )
    def post(self, request):
        serializer = PasswordResetChangePasswordSerializer(data=request.data, context={"request": request})

        if serializer.is_valid():
            user = serializer.save()

            logger.info(f"Password successfully reset for user {user} via forgot password flow")

            # Log audit event for password reset completion
            # For authentication events, set object_type to Employee if user has employee record
            try:
                modified_object = user.employee
            except Exception:
                modified_object = None

            log_audit_event(
                action=LogAction.PASSWORD_RESET,
                modified_object=modified_object,
                user=user,
                request=request,
                change_message=f"User {user.username} completed password reset (changed password)",
            )

            return Response(
                {"message": _("Password has been reset successfully. All old login sessions have been logged out.")},
                status=status.HTTP_200_OK,
            )

        logger.warning(f"Invalid password reset change attempt: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
