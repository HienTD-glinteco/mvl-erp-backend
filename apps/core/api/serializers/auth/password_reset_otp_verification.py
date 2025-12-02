import logging

from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.core.models import PasswordResetOTP

logger = logging.getLogger(__name__)


class PasswordResetOTPVerificationSerializer(serializers.Serializer):
    """
    Serializer for verifying OTP during password reset flow.

    Step 2 of the forgot password flow. User provides the reset_token UUID
    and OTP code they received via email/SMS. Returns otp_token for final step.
    """

    reset_token = serializers.CharField(
        max_length=64,
        help_text="Reset token UUID received from step 1",
        error_messages={
            "required": _("Please enter the reset token."),
            "blank": _("Reset token cannot be blank."),
        },
    )
    otp_code = serializers.CharField(
        max_length=6,
        min_length=6,
        help_text="6-digit OTP code",
        error_messages={
            "required": _("Please enter the OTP code."),
            "blank": _("OTP code cannot be blank."),
            "min_length": _("OTP code must be 6 digits."),
            "max_length": _("OTP code must be 6 digits."),
        },
    )

    def validate_reset_token(self, value):
        """Validate reset token"""
        if not value or not value.strip():
            raise serializers.ValidationError(_("Please enter the reset token."))
        return value.strip()

    def validate_otp_code(self, value):
        """Validate OTP code format"""
        if not value or not value.strip():
            raise serializers.ValidationError(_("Please enter the OTP code."))

        value = value.strip()
        if not value.isdigit():
            raise serializers.ValidationError(_("OTP code can only contain digits."))

        if len(value) != 6:
            raise serializers.ValidationError(_("OTP code must be 6 digits."))

        return value

    def validate(self, attrs):
        reset_token = attrs.get("reset_token")
        otp_code = attrs.get("otp_code")

        # Find password reset request by token using manager
        reset_request = PasswordResetOTP.objects.get_by_token(reset_token)
        if not reset_request:
            raise serializers.ValidationError(_("Reset token is invalid or has expired."))

        # Check if user is active
        if not reset_request.user.is_active:
            raise serializers.ValidationError(_("Account has been deactivated."))

        # Verify OTP
        if not reset_request.verify_otp(otp_code):
            if reset_request.is_expired():
                raise serializers.ValidationError(_("OTP code has expired."))
            elif reset_request.attempts >= reset_request.max_attempts:
                raise serializers.ValidationError(_("Maximum attempts exceeded. Please request a new OTP."))
            else:
                raise serializers.ValidationError(_("OTP code is incorrect."))

        attrs["reset_request"] = reset_request
        return attrs
