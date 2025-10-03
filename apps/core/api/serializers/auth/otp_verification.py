import logging

from django.utils.translation import gettext as _
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import User, UserDevice

logger = logging.getLogger(__name__)


class OTPVerificationSerializer(serializers.Serializer):
    username = serializers.CharField(
        max_length=100,
        help_text=_("Username"),
        error_messages={
            "required": _("Please enter your username."),
            "blank": _("Username cannot be blank."),
        },
    )
    otp_code = serializers.CharField(
        max_length=6,
        min_length=6,
        help_text=_("OTP code"),
        error_messages={
            "required": _("Please enter the OTP code."),
            "blank": _("OTP code cannot be blank."),
            "min_length": _("OTP code must be 6 digits."),
            "max_length": _("OTP code must be 6 digits."),
        },
    )
    device_id = serializers.CharField(
        max_length=255,
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text=_("Device ID of client app (browser can skip)"),
    )

    def validate_otp_code(self, value):
        """Validate OTP code format"""
        if not value or not value.strip():
            raise serializers.ValidationError(_("OTP code cannot be blank."))
        if not value.isdigit():
            raise serializers.ValidationError(_("OTP code can only contain digits."))
        return value.strip()

    def validate(self, attrs):
        username = attrs.get("username")
        otp_code = attrs.get("otp_code")
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise serializers.ValidationError(_("Username does not exist."))

        if not user.verify_otp(otp_code):
            logger.warning(f"Invalid OTP attempt for user {username}")
            raise serializers.ValidationError(_("OTP code is incorrect or has expired."))

        attrs["user"] = user
        attrs["device_id"] = attrs.get("device_id", None)
        return attrs

    def get_tokens(self, user, device_id=None):
        """Get user device id"""
        if device_id:
            if not hasattr(user, "device") or user.device is None:
                UserDevice.objects.create(user=user, device_id=device_id)
                logger.info(f"Assigned new device_id={device_id} for user={user.username}")
            else:
                device_id = user.device.device_id
        else:
            device_id = None

        """Generate JWT tokens for user"""
        refresh = RefreshToken.for_user(user)
        refresh["device_id"] = device_id
        access = refresh.access_token
        access["device_id"] = device_id

        # Clear OTP after successful login
        user.clear_otp()

        logger.debug(f"User {user.username} logged in successfully")
        return {
            "refresh": str(refresh),
            "access": str(access),
        }
