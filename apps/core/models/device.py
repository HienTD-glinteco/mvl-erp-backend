from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserDevice(models.Model):
    """Model representing a user's device for push notifications."""

    class Platform(models.TextChoices):
        IOS = "ios", _("iOS")
        ANDROID = "android", _("Android")
        WEB = "web", _("Web")

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="device",
        on_delete=models.CASCADE,
        verbose_name="User",
    )

    device_id = models.CharField(
        max_length=255,
        unique=True,
        verbose_name="Device ID",
        help_text="Firebase Cloud Messaging token",
    )

    platform = models.CharField(
        max_length=20,
        choices=Platform.choices,
        blank=True,
        verbose_name="Platform",
        help_text="Device platform (iOS, Android, or Web)",
    )

    active = models.BooleanField(
        default=True,
        verbose_name="Active",
        help_text="Whether the device is active for receiving notifications",
    )

    class Meta:
        verbose_name = "User device"
        verbose_name_plural = "User devices"

    def __str__(self):
        return f"{self.user.username} - {self.device_id or 'no-device'}"

    @property
    def fcm_token(self) -> str:
        return self.device_id
