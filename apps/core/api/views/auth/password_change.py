import logging

from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.audit_logging import LogAction, log_audit_event
from apps.core.api.serializers.auth.password_change import PasswordChangeSerializer
from apps.core.api.serializers.auth.responses import PasswordChangeResponseSerializer

logger = logging.getLogger(__name__)


class PasswordChangeRateThrottle(UserRateThrottle):
    scope = "password_change"
    rate = "3/hour"


class PasswordChangeView(APIView):
    """
    API endpoint for changing password when user knows their current password.

    This is different from password reset (forgot password) flow.
    User must be authenticated and provide their current password.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [PasswordChangeRateThrottle]
    serializer_class = PasswordChangeSerializer

    @extend_schema(
        summary=_("Change password (when current password is known)"),
        description=_("Change password when user is logged in and knows their current password"),
        responses={
            200: PasswordChangeResponseSerializer,
            400: OpenApiResponse(description=_("Invalid information or incorrect current password")),
            401: OpenApiResponse(description=_("Not logged in")),
            429: OpenApiResponse(description=_("Too many password change requests")),
        },
    )
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})

        if serializer.is_valid():
            user = serializer.save()

            logger.info(f"Password successfully changed for user {user}")

            # Log audit event for password change
            log_audit_event(
                action=LogAction.PASSWORD_CHANGE,
                user=user,
                request=request,
                change_message=f"User {user.username} changed their password",
            )

            return Response(
                {
                    "message": _(
                        "Password has been changed successfully. All other login sessions have been logged out."
                    )
                },
                status=status.HTTP_200_OK,
            )

        logger.warning(f"Invalid password change attempt for user {request.user}: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
