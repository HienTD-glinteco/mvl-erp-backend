import logging
from datetime import timedelta

from django.contrib.auth import authenticate
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.audit_logging import LogAction, log_audit_event
from apps.core.models import DeviceChangeRequest, User, UserDevice
from apps.core.tasks import send_otp_device_change_task
from apps.hrm.constants import ProposalStatus, ProposalType
from apps.hrm.models import Proposal

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
        if getattr(user, "is_locked", False):
            raise serializers.ValidationError(
                _("Account is temporarily locked due to multiple failed login attempts. Please try again later.")
            )

        # Check if the device is already registered and not is revoked
        device = (
            UserDevice.objects.filter(device_id=device_id, client=UserDevice.Client.MOBILE)
            .exclude(state=UserDevice.State.REVOKED)
            .first()
        )
        if device:
            if device.user != user:
                raise serializers.ValidationError(
                    _("This device is already registered to another account. Please use a different device.")
                )
            else:
                # Check if device_id equals current registered device
                raise serializers.ValidationError(
                    _("This device is already registered for your account. No need to create a device change request.")
                )

        attrs["user"] = user
        return attrs

    def create_request(self):
        user = self.validated_data["user"]
        device_id = self.validated_data["device_id"]
        platform = self.validated_data.get("platform", "")
        notes = self.validated_data.get("notes", "")

        # Generate OTP
        otp_code = user.generate_otp()
        otp_expires_at = timezone.now() + timedelta(seconds=300)  # 5 minutes

        # Create device change request
        with transaction.atomic():
            device_request = DeviceChangeRequest.objects.create(
                user=user,
                new_device_id=device_id,
                new_platform=platform,
                notes=notes,
                otp_code=otp_code,
                otp_sent_at=timezone.now(),
                otp_expires_at=otp_expires_at,
                status=DeviceChangeRequest.Status.OTP_SENT,
            )

            # Log audit event
            log_audit_event(
                action=LogAction.ADD,
                modified_object=device_request,
                user=user,
                request=self.context.get("request"),
                change_message=f"Device change request created for device_id: {device_id}",
            )

        # Send OTP email asynchronously
        try:
            send_otp_device_change_task.delay(
                user_id=str(user.id),
                user_email=user.email,
                user_full_name=user.get_full_name(),
                username=user.username,
                otp_code=otp_code,
            )
            logger.info(f"OTP sent for device change request {device_request.id} for user {user.username}")
        except Exception as e:  # nosec B110
            logger.error(f"Failed to queue OTP email for device change request: {e}")
        return device_request


class DeviceChangeVerifyOTPSerializer(serializers.Serializer):
    """Serializer for verifying OTP and creating device change proposal."""

    request_id = serializers.IntegerField(
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
            device_request = DeviceChangeRequest.objects.get(id=request_id)
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

        # Ensure user has employee mapping (required for creating Proposal)
        try:
            employee = device_request.user.employee
        except Exception:  # nosec B110
            raise serializers.ValidationError(
                _(
                    "Your account is not linked to an employee record. Please contact HR to set up your employee profile before requesting device change."
                )
            )

        attrs["device_request"] = device_request
        attrs["employee"] = employee
        return attrs

    def create_proposal(self):
        device_request = self.validated_data["device_request"]
        user = device_request.user
        employee = self.validated_data["employee"]
        request = self.context.get("request")

        # Get old device_id if exists
        old_device_id = None
        if hasattr(user, "device") and user.device is not None:
            old_device_id = user.device.device_id

        # Create Proposal with type DEVICE_CHANGE
        with transaction.atomic():
            # Mark device request as verified
            device_request.mark_verified()

            # Create proposal
            proposal = Proposal.objects.create(
                proposal_type=ProposalType.DEVICE_CHANGE,
                proposal_status=ProposalStatus.PENDING,
                created_by=employee,
                device_change_new_device_id=device_request.new_device_id,
                device_change_new_platform=device_request.new_platform,
                device_change_old_device_id=old_device_id,
                note=device_request.notes,
            )

            # Log audit event
            log_audit_event(
                action=LogAction.ADD,
                modified_object=proposal,
                user=user,
                request=request,
                change_message=f"Device change proposal created from request {device_request.id}",
            )

            logger.info(
                f"Device change proposal {proposal.id} created for user {user.username} "
                f"with device_id: {device_request.new_device_id}"
            )
        return proposal
