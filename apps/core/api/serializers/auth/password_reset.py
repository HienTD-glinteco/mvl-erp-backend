import logging

import sentry_sdk
from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.core.models import User
from apps.core.tasks import send_password_reset_email_task

logger = logging.getLogger(__name__)


class PasswordResetSerializer(serializers.Serializer):
    identifier = serializers.CharField(
        max_length=255,
        help_text=_("Email or phone number"),
        error_messages={
            "required": _("Please enter your email or phone number."),
            "blank": _("Email or phone number cannot be blank."),
        },
    )

    def validate_identifier(self, value):
        """Validate identifier (email or phone number)"""
        if not value or not value.strip():
            raise serializers.ValidationError(_("Please enter your email or phone number."))
        return value.strip()

    def validate(self, attrs):
        identifier = attrs.get("identifier")

        # Search by email or phone number
        user = None
        try:
            if "@" in identifier:
                # Assume it's an email
                user = User.objects.get(email=identifier)
            else:
                # Assume it's a phone number
                user = User.objects.get(phone_number=identifier)
        except User.DoesNotExist:
            raise serializers.ValidationError(_("No account found with this information."))

        if not user.is_active:
            raise serializers.ValidationError(_("Account has been deactivated."))

        attrs["user"] = user
        return attrs

    def send_reset_email(self, user, otp_code):
        """Send password reset OTP via email using Celery task"""
        try:
            # Send email via Celery task
            send_password_reset_email_task.delay(
                user_id=str(user.id),
                user_email=user.email,
                user_full_name=user.get_full_name(),
                username=user.username,
                otp_code=otp_code,
            )

            logger.info(f"Password reset OTP email task queued for user {user.username}")
            return True

        except Exception as e:
            logger.error(f"Failed to queue password reset OTP email task for user {user.username}: {str(e)}")
            sentry_sdk.capture_exception(e)
            return False
