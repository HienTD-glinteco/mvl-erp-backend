import hashlib
from datetime import timedelta

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.querysets.password_reset import PasswordResetOTPManager


class PasswordResetOTP(models.Model):
    """
    Model to handle password reset OTP requests with secure token-based authentication.

    This replaces storing OTP data directly in the User model for better security
    and separation of concerns.
    """

    class Channel(models.TextChoices):
        EMAIL = "email", _("Email")
        SMS = "sms", _("SMS")

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey("User", on_delete=models.CASCADE, related_name="password_reset_requests")
    reset_token = models.CharField(max_length=64, unique=True, db_index=True, verbose_name=_("Reset Token"))
    otp_hash = models.CharField(max_length=128, verbose_name=_("OTP Hash"))  # Hashed OTP, not plain text
    channel = models.CharField(max_length=10, choices=Channel.choices, default=Channel.EMAIL)
    expires_at = models.DateTimeField(verbose_name=_("Expires At"))
    attempts = models.PositiveSmallIntegerField(default=0, verbose_name=_("Verification Attempts"))
    max_attempts = models.PositiveSmallIntegerField(default=5, verbose_name=_("Max Attempts"))
    is_used = models.BooleanField(default=False, verbose_name=_("Is Used"))
    is_verified = models.BooleanField(default=False, verbose_name=_("Is Verified"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))

    objects = PasswordResetOTPManager()

    class Meta:
        verbose_name = _("Password Reset OTP")
        verbose_name_plural = _("Password Reset OTPs")
        db_table = "core_password_reset_otp"
        ordering = ["-created_at"]

    def is_expired(self):
        """Check if the OTP request has expired."""
        return timezone.now() >= self.expires_at

    def verify_otp(self, otp_code):
        """
        Verify the provided OTP code against the stored hash.

        Args:
            otp_code: Plain text OTP code to verify

        Returns:
            bool: True if verification successful, False otherwise
        """
        if self.is_expired() or self.is_used or self.attempts >= self.max_attempts:
            return False

        # Increment attempts
        self.attempts += 1
        self.save(update_fields=["attempts"])

        # Verify OTP hash
        provided_hash = hashlib.sha256(otp_code.strip().encode()).hexdigest()
        if provided_hash == self.otp_hash:
            self.is_verified = True
            self.save(update_fields=["is_verified"])
            return True

        return False

    def mark_as_used(self):
        """Mark this OTP request as used after successful password change."""
        self.is_used = True
        self.save(update_fields=["is_used"])

    def delete_after_use(self):
        """Delete the OTP request after successful password change to avoid DB garbage."""
        self.delete()

    @classmethod
    def can_user_request_new(cls, user):
        """
        Check if the given user can request a new password reset (rate limiting).
        Args:
            user: The user instance to check for recent password reset requests.
        Returns:
            tuple: (can_request: bool, remaining_seconds: int)
        """
        # Check if there's a recent request within the last 3 minutes
        recent_request = cls.objects.filter(user=user, created_at__gte=timezone.now() - timedelta(minutes=3)).first()

        if recent_request:
            time_passed = (timezone.now() - recent_request.created_at).total_seconds()
            remaining = max(0, 180 - int(time_passed))  # 3 minutes = 180 seconds
            return False, remaining

        return True, 0

    def __str__(self):
        return f"Password reset for {self.user} - {self.reset_token[:8]}..."
