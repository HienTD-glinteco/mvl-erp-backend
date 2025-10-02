from django.conf import settings
from django.db import models


class UserDevice(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="device",
        on_delete=models.CASCADE,
    )

    device_id = models.CharField(
        max_length=255,
        unique=True,
    )

    def __str__(self):
        return f"{self.user.username} - {self.device_id or 'no-device'}"
