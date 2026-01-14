import logging

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.core.utils.jwt import revoke_user_outstanding_tokens

logger = logging.getLogger(__name__)


class PasswordChangeSerializer(serializers.Serializer):
    """
    Serializer for changing password when user knows their current password.

    This is different from password reset (forgot password) flow.
    User must provide their current password + new password.
    """

    old_password = serializers.CharField(
        write_only=True,
        help_text="Current password",
        error_messages={
            "required": _("Please enter your current password."),
            "blank": _("Current password cannot be blank."),
        },
    )
    new_password = serializers.CharField(
        write_only=True,
        help_text="New password",
        error_messages={
            "required": _("Please enter your new password."),
            "blank": _("New password cannot be blank."),
        },
    )
    confirm_password = serializers.CharField(
        write_only=True,
        help_text="Confirm new password",
        error_messages={
            "required": _("Please confirm your new password."),
            "blank": _("Password confirmation cannot be blank."),
        },
    )

    def validate_old_password(self, value):
        """Validate old password is not empty"""
        if not value:
            raise serializers.ValidationError(_("Current password cannot be blank."))
        return value

    def validate_new_password(self, value):
        """Validate new password against Django's password validators"""
        if not value:
            raise serializers.ValidationError(_("New password cannot be blank."))

        # Use Django's password validation
        try:
            validate_password(value)
        except ValidationError as e:
            # Re-raise with proper message formatting
            raise serializers.ValidationError(e.messages)

        return value

    def validate(self, attrs):
        old_password = attrs.get("old_password")
        new_password = attrs.get("new_password")
        confirm_password = attrs.get("confirm_password")

        # Check if passwords match
        # Check if passwords match
        if new_password != confirm_password:
            raise serializers.ValidationError(
                {"confirm_password": _("New password and confirmation password do not match.")}
            )

        # Check if new password is different from old password
        if old_password == new_password:
            raise serializers.ValidationError(
                {"new_password": _("New password must be different from current password.")}
            )

        # Get user from request context (must be authenticated)
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(_("You need to be logged in to change your password."))

        user = request.user

        # Verify old password
        if not user.check_password(old_password):
            raise serializers.ValidationError({"old_password": _("Current password is incorrect.")})

        attrs["user"] = user
        return attrs

    def save(self):
        """
        Change user password and invalidate all existing sessions/tokens.

        This will:
        1. Set new password
        2. Invalidate all Django sessions
        3. Revoke all outstanding JWT tokens

        The user will need to login again with the new password.
        """
        user = self.validated_data["user"]
        new_password = self.validated_data["new_password"]

        # Change password
        user.set_password(new_password)
        user.save()

        # Invalidate all Django sessions (logout from web sessions)
        user.invalidate_all_sessions()

        # Revoke all outstanding JWT refresh tokens (logout from mobile/API)
        revoke_user_outstanding_tokens(user)

        logger.info(f"Password successfully changed for user {user}. All sessions and tokens invalidated.")

        return user
