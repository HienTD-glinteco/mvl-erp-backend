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


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(
        max_length=100,
        help_text="Username",
        error_messages={
            "required": _("Please enter your username."),
            "blank": _("Username cannot be blank."),
        },
    )
    password = serializers.CharField(
        write_only=True,
        help_text="Password",
        error_messages={
            "required": _("Please enter your password."),
            "blank": _("Password cannot be blank."),
        },
    )

    # Always included in token claims for both web and mobile.
    device_id = serializers.CharField(
        max_length=255,
        help_text="Device identifier provided by client",
        # error_messages={
        #     "required": _("Device ID is required."),
        #     "blank": _("Device ID cannot be blank."),
        # },
        required=False,
        allow_blank=True,
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

    def validate_username(self, value: str) -> str:
        if not value or not value.strip():
            raise serializers.ValidationError(_("Username cannot be blank."))
        return value.strip()

    def validate_password(self, value: str) -> str:
        if not value:
            raise serializers.ValidationError(_("Password cannot be blank."))
        return value

    # def validate_device_id(self, value: str) -> str:
    #     if not value or not value.strip():
    #         raise serializers.ValidationError(_("Device ID cannot be blank."))
    #     return value.strip()

    def validate(self, attrs):
        username = attrs.get("username")
        password = attrs.get("password")
        device_id = (attrs.get("device_id") or "").strip()
        platform = (attrs.get("platform") or "").strip()
        push_token = (attrs.get("push_token") or "").strip()

        client = self.context.get("client", UserDevice.Client.WEB)

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise serializers.ValidationError({"username": _("Username does not exist.")})

        if user.is_locked:
            remaining_time = (user.locked_until - timezone.now()).seconds // 60
            raise serializers.ValidationError(
                {
                    "username": _("Account is locked. Please try again in %(minutes)d minutes.")
                    % {"minutes": remaining_time}
                }
            )

        if not user.is_active:
            raise serializers.ValidationError({"username": _("Account has been deactivated.")})

        if not user.check_password(password):
            user.increment_failed_login()
            if user.is_locked:
                logger.warning("Account locked for user %s after failed login attempts", username)
                raise serializers.ValidationError(
                    {
                        "password": _(
                            "Account has been locked due to 5 failed login attempts. Please try again in 5 minutes."
                        )
                    }
                )
            logger.warning("Failed login attempt for user %s", username)
            raise serializers.ValidationError({"password": _("Incorrect password.")})

        if client == UserDevice.Client.MOBILE:
            if not device_id:
                raise serializers.ValidationError({"device_id": _("Device ID is required for mobile login.")})
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
                raise serializers.ValidationError(
                    {"device_id": _("This device is already registered to another user.")}
                )

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

    def get_tokens(self, user: User, *, client: str) -> dict[str, str]:
        device_id: str = self.validated_data["device_id"]
        now = timezone.now()

        if client == UserDevice.Client.MOBILE:
            active_device = UserDevice.objects.filter(
                user=user,
                client=UserDevice.Client.MOBILE,
                state=UserDevice.State.ACTIVE,
            ).first()

            if active_device is None:
                UserDevice.objects.create(
                    user=user,
                    client=UserDevice.Client.MOBILE,
                    device_id=device_id,
                    platform=str(self.validated_data.get("platform") or ""),
                    push_token=str(self.validated_data.get("push_token") or ""),
                    last_seen_at=now,
                    state=UserDevice.State.ACTIVE,
                )
            else:
                active_device.platform = str(self.validated_data.get("platform") or "")
                active_device.push_token = str(self.validated_data.get("push_token") or "")
                active_device.last_seen_at = now
                active_device.save(update_fields=["platform", "push_token", "last_seen_at"])

        if client == UserDevice.Client.WEB:
            UserDevice.objects.update_or_create(
                user=user,
                client=UserDevice.Client.WEB,
                device_id=device_id,
                defaults={
                    "last_seen_at": now,
                    "state": UserDevice.State.ACTIVE,
                    "platform": UserDevice.Platform.WEB,
                },
            )

        refresh = RefreshToken.for_user(user)
        refresh["client"] = client
        refresh["device_id"] = device_id

        access = refresh.access_token
        access["client"] = client
        access["device_id"] = device_id

        if client == UserDevice.Client.MOBILE:
            refresh["tv"] = user.mobile_token_version
            access["tv"] = user.mobile_token_version

        return {"refresh": str(refresh), "access": str(access)}
