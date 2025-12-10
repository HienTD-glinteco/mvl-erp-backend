import hashlib
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from libs.models import BaseModel


class DeviceChangeRequest(BaseModel):
    """Temporary storage for device change requests with OTP verification.

    This model stores device change requests while users verify OTP.
    After successful verification, a Proposal is created and this record
    can be marked as completed.
    """

    class Status(models.TextChoices):
        OTP_SENT = "otp_sent", "OTP Sent"
        VERIFIED = "verified", "Verified"
        FAILED = "failed", "Failed"
        EXPIRED = "expired", "Expired"

    request_id = models.UUIDField(
        unique=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="Request ID",
        help_text="Unique identifier for this device change request",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="device_change_requests",
        verbose_name="User",
    )

    employee = models.ForeignKey(
        "hrm.Employee",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="device_change_requests",
        verbose_name="Employee",
        help_text="Employee associated with the user (if exists)",
    )

    new_device_id = models.CharField(
        max_length=255,
        verbose_name="New Device ID",
        help_text="Device ID being requested for assignment",
    )

    new_platform = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="New Platform",
        help_text="Platform of the new device (ios, android, web)",
    )

    notes = models.TextField(
        null=True,
        blank=True,
        verbose_name="Notes",
        help_text="Additional notes from the requester",
    )

    otp_hash = models.CharField(
        max_length=255,
        verbose_name="OTP Hash",
        help_text="Hashed OTP code for verification",
    )

    otp_sent_at = models.DateTimeField(
        verbose_name="OTP Sent At",
        help_text="Timestamp when OTP was sent",
    )

    otp_expires_at = models.DateTimeField(
        verbose_name="OTP Expires At",
        help_text="Timestamp when OTP expires",
    )

    otp_attempts = models.IntegerField(
        default=0,
        verbose_name="OTP Attempts",
        help_text="Number of OTP verification attempts",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OTP_SENT,
        verbose_name="Status",
    )

    class Meta:
        verbose_name = "Device Change Request"
        verbose_name_plural = "Device Change Requests"
        db_table = "core_device_change_request"
        indexes = [
            models.Index(fields=["request_id"], name="dcr_request_id_idx"),
            models.Index(fields=["user"], name="dcr_user_idx"),
            models.Index(fields=["status"], name="dcr_status_idx"),
        ]

    def __str__(self):
        return f"DeviceChangeRequest {self.request_id} - {self.user.username}"

    @staticmethod
    def hash_otp(otp_code: str) -> str:
        """Hash OTP code using SHA256.

        Args:
            otp_code: Plain OTP code

        Returns:
            Hashed OTP code
        """
        return hashlib.sha256(otp_code.encode()).hexdigest()

    def verify_otp(self, otp_code: str) -> bool:
        """Verify OTP code against stored hash.

        Args:
            otp_code: Plain OTP code to verify

        Returns:
            True if OTP is valid, False otherwise
        """
        # Check if expired
        if timezone.now() > self.otp_expires_at:
            self.status = self.Status.EXPIRED
            self.save(update_fields=["status"])
            return False

        # Verify hash
        if self.hash_otp(otp_code) == self.otp_hash:
            return True

        return False

    def increment_attempts(self) -> None:
        """Increment OTP verification attempts."""
        self.otp_attempts += 1
        if self.otp_attempts >= 5:
            self.status = self.Status.FAILED
        self.save(update_fields=["otp_attempts", "status"])

    def mark_verified(self) -> None:
        """Mark this request as verified."""
        self.status = self.Status.VERIFIED
        self.save(update_fields=["status"])
