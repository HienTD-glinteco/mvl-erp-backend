import logging

from django.utils.translation import gettext as _
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import User, UserDevice

logger = logging.getLogger(__name__)


class OTPVerificationSerializer(serializers.Serializer):
    username = serializers.CharField(
        max_length=100,
        help_text="Username",
        error_messages={
            "required": _("Please enter your username."),
            "blank": _("Username cannot be blank."),
        },
    )
    otp_code = serializers.CharField(
        max_length=6,
        min_length=6,
        help_text="OTP code",
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
        help_text="Device ID of client app (browser can skip)",
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
        device_id = attrs.get("device_id")

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise serializers.ValidationError(_("Username does not exist."))

        if not user.verify_otp(otp_code):
            logger.warning(f"Invalid OTP attempt for user {username}")
            raise serializers.ValidationError(_("OTP code is incorrect or has expired."))

        # Check if this is device-change flow (via context flag)
        flow_type = self.context.get("flow")
        
        # Validate device_id if provided
        if device_id:
            existing_device = UserDevice.objects.filter(device_id=device_id).first()
            if existing_device and existing_device.user != user:
                logger.warning(f"Device ID {device_id} already registered to user {existing_device.user.username}")
                raise serializers.ValidationError(_("This device is already registered to another user."))
            
            # If device-change flow is attempted via this serializer, prevent redundant change
            if flow_type == "device_change_request":
                # Check if device_id equals user's registered device_id
                if hasattr(user, "device") and user.device is not None:
                    if user.device.device_id == device_id:
                        raise serializers.ValidationError(
                            _(
                                "This device is already registered for your account. "
                                "No need to create a device change request."
                            )
                        )

        attrs["user"] = user
        attrs["device_id"] = device_id
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
