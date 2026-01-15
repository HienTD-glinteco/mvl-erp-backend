import logging

from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework import serializers
from rest_framework.exceptions import APIException
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import User, UserDevice

logger = logging.getLogger(__name__)


class MobileDeviceConflict(APIException):
    status_code = 409
    default_detail = _(
        "You are attempting to login from a different device. "
        "Please use the device change request process to change your device."
    )
    default_code = "device_conflict"


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

    # Always included in token claims for both web and mobile.
    device_id = serializers.CharField(
        max_length=255,
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="Device identifier provided by client",
    )
    platform = serializers.ChoiceField(
        choices=UserDevice.Platform.choices,
        required=False,
        allow_blank=True,
        help_text="Device platform (ios/android)",
    )
    push_token = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        help_text="Push token (e.g., FCM/APNS)",
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
        device_id = (attrs.get("device_id") or "").strip() or None
        platform = (attrs.get("platform") or "").strip()
        push_token = (attrs.get("push_token") or "").strip()

        client = self.context.get("client", UserDevice.Client.WEB)

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise serializers.ValidationError(_("Username does not exist."))

        if not user.verify_otp(otp_code):
            logger.warning(f"Invalid OTP attempt for user {username}")
            raise serializers.ValidationError(_("OTP code is incorrect or has expired."))

        if client == UserDevice.Client.MOBILE:
            if not device_id:
                raise serializers.ValidationError(_("Device ID is required for mobile login."))

            device_taken = (
                UserDevice.objects.filter(
                    client=UserDevice.Client.MOBILE,
                    state=UserDevice.State.ACTIVE,
                    device_id=device_id,
                )
                .exclude(user=user)
                .first()
            )
            if device_taken is not None:
                raise serializers.ValidationError(_("This device is already registered to another user."))

            active_device = UserDevice.objects.filter(
                user=user,
                client=UserDevice.Client.MOBILE,
                state=UserDevice.State.ACTIVE,
            ).first()
            if active_device is not None and active_device.device_id != device_id:
                raise MobileDeviceConflict()

        attrs["user"] = user
        attrs["device_id"] = device_id
        attrs["platform"] = platform
        attrs["push_token"] = push_token
        return attrs

    def get_tokens(self, user: User, device_id: str | None = None, *, client: str = "web"):
        now = timezone.now()

        if client == UserDevice.Client.MOBILE:
            platform: str = str(self.validated_data.get("platform") or "")
            push_token: str = str(self.validated_data.get("push_token") or "")

            active_device = UserDevice.objects.filter(
                user=user,
                client=UserDevice.Client.MOBILE,
                state=UserDevice.State.ACTIVE,
            ).first()

            if active_device is None:
                UserDevice.objects.create(
                    user=user,
                    client=UserDevice.Client.MOBILE,
                    device_id=device_id or "",
                    platform=platform,
                    push_token=push_token,
                    last_seen_at=now,
                    state=UserDevice.State.ACTIVE,
                )
            else:
                active_device.platform = platform
                active_device.push_token = push_token
                active_device.last_seen_at = now
                active_device.save(update_fields=["platform", "push_token", "last_seen_at"])

        if client == UserDevice.Client.WEB:
            if device_id:
                UserDevice.objects.create(
                    user=user,
                    client=UserDevice.Client.WEB,
                    device_id=device_id,
                    platform=UserDevice.Platform.WEB,
                    last_seen_at=now,
                    state=UserDevice.State.ACTIVE,
                )

        refresh = RefreshToken.for_user(user)
        refresh["client"] = client
        refresh["device_id"] = device_id
        refresh["tv"] = user.mobile_token_version  # Add for both web and mobile

        access = refresh.access_token
        access["client"] = client
        access["device_id"] = device_id
        access["tv"] = user.mobile_token_version  # Add for both web and mobile

        user.clear_otp()

        return {
            "refresh": str(refresh),
            "access": str(access),
        }
