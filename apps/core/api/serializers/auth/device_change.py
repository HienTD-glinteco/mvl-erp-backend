import logging

from django.contrib.auth import authenticate
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.core.models import DeviceChangeRequest, User, UserDevice

logger = logging.getLogger(__name__)


class DeviceChangeRequestSerializer(serializers.Serializer):
    """Serializer for initiating device change request with username/password."""

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
    device_id = serializers.CharField(
        max_length=255,
        help_text="New device ID (FCM token or device UUID)",
        error_messages={
            "required": _("Please provide device ID."),
            "blank": _("Device ID cannot be blank."),
        },
    )
    platform = serializers.ChoiceField(
        choices=UserDevice.Platform.choices,
        required=False,
        allow_blank=True,
        help_text="Device platform (ios, android, web)",
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Additional notes for the request",
    )
    client_meta = serializers.DictField(
        required=False,
        help_text="Client metadata (IP address, user agent, etc.)",
    )

    def validate(self, attrs):
        """Validate credentials and device_id."""
        username = attrs.get("username")
        password = attrs.get("password")
        device_id = attrs.get("device_id")

        # Authenticate user
        user = authenticate(username=username, password=password)
        if user is None:
            # Check if username exists to provide better error message
            try:
                User.objects.get(username=username)
                raise serializers.ValidationError(_("Incorrect password. Please try again."))
            except User.DoesNotExist:
                raise serializers.ValidationError(_("Username does not exist."))

        # Check if user is active
        if not user.is_active:
            raise serializers.ValidationError(_("This account is inactive. Please contact support."))

        # Check if user is locked
        if user.is_locked:
            raise serializers.ValidationError(
                _("Account is temporarily locked due to multiple failed login attempts. Please try again later.")
            )

        # Check if device_id equals current registered device
        if hasattr(user, "device") and user.device is not None:
            if user.device.device_id == device_id:
                raise serializers.ValidationError(
                    _(
                        "This device is already registered for your account. "
                        "No need to create a device change request."
                    )
                )

        attrs["user"] = user
        return attrs


class DeviceChangeVerifyOTPSerializer(serializers.Serializer):
    """Serializer for verifying OTP and creating device change proposal."""

    request_id = serializers.UUIDField(
        help_text="Device change request ID",
        error_messages={
            "required": _("Please provide request ID."),
            "invalid": _("Invalid request ID format."),
        },
    )
    otp = serializers.CharField(
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
        help_text="Device ID (optional, for additional verification)",
    )
    client_meta = serializers.DictField(
        required=False,
        help_text="Client metadata (IP address, user agent, etc.)",
    )

    def validate_otp(self, value):
        """Validate OTP code format."""
        if not value or not value.strip():
            raise serializers.ValidationError(_("OTP code cannot be blank."))
        if not value.isdigit():
            raise serializers.ValidationError(_("OTP code can only contain digits."))
        return value.strip()

    def validate(self, attrs):
        """Validate OTP and device change request."""
        request_id = attrs.get("request_id")
        otp = attrs.get("otp")

        # Retrieve device change request
        try:
            device_request = DeviceChangeRequest.objects.get(request_id=request_id)
        except DeviceChangeRequest.DoesNotExist:
            logger.warning(f"Device change request not found: {request_id}")
            raise serializers.ValidationError(_("Invalid or expired request. Please start over."))

        # Check if already verified or failed
        if device_request.status == DeviceChangeRequest.Status.VERIFIED:
            raise serializers.ValidationError(_("This request has already been verified."))
        if device_request.status == DeviceChangeRequest.Status.FAILED:
            raise serializers.ValidationError(
                _("This request has failed due to too many incorrect attempts. Please start over.")
            )
        if device_request.status == DeviceChangeRequest.Status.EXPIRED:
            raise serializers.ValidationError(_("This request has expired. Please start over."))

        # Check if OTP has expired
        if timezone.now() > device_request.otp_expires_at:
            device_request.status = DeviceChangeRequest.Status.EXPIRED
            device_request.save(update_fields=["status"])
            raise serializers.ValidationError(_("OTP code has expired. Please request a new one."))

        # Check attempts limit
        if device_request.otp_attempts >= 5:
            device_request.status = DeviceChangeRequest.Status.FAILED
            device_request.save(update_fields=["status"])
            raise serializers.ValidationError(
                _("Too many incorrect attempts. This request has been marked as failed. Please start over.")
            )

        # Verify OTP
        if not device_request.verify_otp(otp):
            device_request.increment_attempts()
            remaining_attempts = 5 - device_request.otp_attempts
            if remaining_attempts > 0:
                raise serializers.ValidationError(
                    _("Incorrect OTP code. You have {attempts} attempt(s) remaining.").format(
                        attempts=remaining_attempts
                    )
                )
            else:
                raise serializers.ValidationError(
                    _("Too many incorrect attempts. This request has been marked as failed. Please start over.")
                )

        attrs["device_request"] = device_request
        return attrs
