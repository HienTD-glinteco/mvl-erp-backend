from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from libs.models.base_model_mixin import BaseModel


class UserDevice(BaseModel):
    """User device model for mobile device binding and push notifications."""

    class Client(models.TextChoices):
        MOBILE = "mobile", "Mobile"
        WEB = "web", "Web"

    class State(models.TextChoices):
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        REVOKED = "revoked", "Revoked"

    class Platform(models.TextChoices):
        IOS = "ios", _("iOS")
        ANDROID = "android", _("Android")
        WEB = "web", _("Web")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="devices",
        on_delete=models.CASCADE,
        verbose_name="User",
    )

    client = models.CharField(
        max_length=20,
        choices=Client.choices,
        default=Client.MOBILE,
        verbose_name="Client",
    )

    device_id = models.CharField(
        max_length=255,
        verbose_name="Device ID",
        help_text="Client provided device identifier",
    )

    push_token = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Push token",
        help_text="Push notification token (e.g., FCM/APNS)",
    )

    platform = models.CharField(
        max_length=20,
        choices=Platform.choices,
        blank=True,
        verbose_name="Platform",
        help_text="Device platform (iOS/Android)",
    )

    state = models.CharField(
        max_length=20,
        choices=State.choices,
        default=State.ACTIVE,
        verbose_name="State",
    )

    last_seen_at = models.DateTimeField(null=True, blank=True, verbose_name="Last seen at")

    class Meta:
        verbose_name = "User device"
        verbose_name_plural = "User devices"
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(client="mobile", state="active"),
                name="uniq_active_mobile_device_per_user",
            ),
            models.UniqueConstraint(
                fields=["device_id"],
                condition=Q(client="mobile", state="active"),
                name="uniq_active_mobile_device_id",
            ),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.device_id or 'no-device'}"

    @property
    def active(self) -> bool:
        return self.state == self.State.ACTIVE

    @property
    def fcm_token(self) -> str:
        return self.push_token or self.device_id
