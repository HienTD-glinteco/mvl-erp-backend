import secrets
import hashlib
from datetime import timedelta
from django.db import models
from django.utils import timezone


class PasswordResetOTPManager(models.Manager):
    def create_request(self, user, channel: str = "email", ttl_seconds: int = 180):
        """
        Create a new password reset request with a 6-digit OTP.
        Returns (reset_request, plain_otp_code)
        """
        # Deactivate any existing pending requests for this user
        self.filter(user=user, is_used=False, is_verified=False).update(is_used=True)

        reset_token = secrets.token_urlsafe(32)
        otp = f"{secrets.randbelow(1000000):06d}"
        otp_hash = hashlib.sha256(otp.encode()).hexdigest()

        obj = self.create(
            user=user,
            reset_token=reset_token,
            otp_hash=otp_hash,
            channel=channel,
            expires_at=timezone.now() + timedelta(seconds=ttl_seconds),
        )
        return obj, otp

    def get_by_token(self, reset_token: str):
        """Get an active (not used, not expired) reset request by reset_token."""
        try:
            return self.get(
                reset_token=reset_token,
                is_used=False,
                expires_at__gt=timezone.now(),
            )
        except self.model.DoesNotExist:  # type: ignore[attr-defined]
            return None

    def cleanup_expired_and_old_used(self, retention_days: int = 7) -> int:
        """
        Delete expired requests and used requests older than retention.
        Returns number of rows deleted (best-effort sum).
        """
        now = timezone.now()
        deleted = 0
        deleted += self.filter(expires_at__lte=now).delete()[0]
        if retention_days and retention_days > 0:
            threshold = now - timedelta(days=retention_days)
            deleted += self.filter(is_used=True, created_at__lte=threshold).delete()[0]
        return deleted
