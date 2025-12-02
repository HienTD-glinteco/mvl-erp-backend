from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _

from libs.models import BaseModel


class Notification(BaseModel):
    """Model representing a notification for a user.

    Notifications track events that users should be aware of, with support
    for various notification types through a generic foreign key to the target object.
    """

    # Delivery method
    class DeliveryMethod(models.TextChoices):
        FIREBASE = "firebase", _("Firebase")
        EMAIL = "email", _("Email")
        BOTH = "both", _("Both")

    # The user who triggered the event (e.g., who commented, who assigned a task)
    actor = models.ForeignKey(
        "core.User",
        on_delete=models.CASCADE,
        related_name="notifications_as_actor",
        verbose_name="Actor",
        help_text="The user who triggered the notification",
    )

    # The user receiving the notification
    recipient = models.ForeignKey(
        "core.User",
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="Recipient",
        help_text="The user receiving the notification",
        db_index=True,
    )

    # The action that was performed (e.g., "commented on", "assigned", "updated")
    verb = models.CharField(
        max_length=255,
        verbose_name="Verb",
        help_text="The action that was performed",
    )

    # Generic foreign key to the object affected by the action
    target_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="notification_targets",
        null=True,
        blank=True,
        verbose_name="Target content type",
    )
    target_object_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Target object ID",
    )
    target = GenericForeignKey("target_content_type", "target_object_id")

    # Optional custom message
    message = models.TextField(
        blank=True,
        verbose_name="Message",
        help_text="Optional custom message for the notification",
    )

    # Read status
    read = models.BooleanField(
        default=False,
        verbose_name="Read",
        help_text="Whether the notification has been read",
        db_index=True,
    )

    # Extra data for additional context (e.g., IDs, URLs, metadata)
    extra_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Extra data",
        help_text="Additional JSON data to provide context for rendering",
    )

    delivery_method = models.CharField(
        max_length=20,
        choices=DeliveryMethod.choices,
        default=DeliveryMethod.FIREBASE,
        verbose_name="Delivery method",
        help_text="How the notification should be delivered",
    )

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "-created_at"]),
            models.Index(fields=["recipient", "read", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.actor} {self.verb} - {self.recipient}"

    def mark_as_read(self):
        """Mark this notification as read."""
        if not self.read:
            self.read = True
            self.save(update_fields=["read", "updated_at"])

    def mark_as_unread(self):
        """Mark this notification as unread."""
        if self.read:
            self.read = False
            self.save(update_fields=["read", "updated_at"])
