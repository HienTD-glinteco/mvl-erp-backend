from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserDevice(models.Model):
    """Model representing a user's device for push notifications."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="device",
        on_delete=models.CASCADE,
        verbose_name=_("User"),
    )

    device_id = models.CharField(
        max_length=255,
        unique=True,
        verbose_name=_("Device ID"),
        help_text=_("Unique identifier for the device"),
    )

    fcm_token = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("FCM token"),
        help_text=_("Firebase Cloud Messaging token"),
    )

    class Platform(models.TextChoices):
        IOS = "ios", _("iOS")
        ANDROID = "android", _("Android")
        WEB = "web", _("Web")

    platform = models.CharField(
        max_length=20,
        choices=Platform.choices,
        blank=True,
        verbose_name=_("Platform"),
        help_text=_("Device platform (iOS, Android, or Web)"),
    )

    active = models.BooleanField(
        default=True,
        verbose_name=_("Active"),
        help_text=_("Whether the device is active for receiving notifications"),
    )

    class Meta:
        verbose_name = _("User device")
        verbose_name_plural = _("User devices")

    def __str__(self):
        return f"{self.user.username} - {self.device_id or 'no-device'}"
