"""Models for mail template send jobs and recipients."""

import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from libs.models import BaseModel


class EmailSendJob(BaseModel):
    """Represents a bulk email send job.

    Tracks the overall status of a bulk email send operation, including
    template used, subject, sender, and aggregated statistics.
    """

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        RUNNING = "running", _("Running")
        COMPLETED = "completed", _("Completed")
        FAILED = "failed", _("Failed")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template_slug = models.CharField(
        max_length=100,
        verbose_name=_("Template slug"),
        help_text=_("Slug of the template used for this job"),
        db_index=True,
    )
    subject = models.CharField(
        max_length=500,
        verbose_name=_("Email subject"),
        help_text=_("Subject line for the emails"),
    )
    sender = models.EmailField(
        verbose_name=_("Sender email"),
        help_text=_("From email address"),
    )
    total = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Total recipients"),
        help_text=_("Total number of recipients in this job"),
    )
    sent_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Sent count"),
        help_text=_("Number of successfully sent emails"),
    )
    failed_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Failed count"),
        help_text=_("Number of failed email sends"),
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name=_("Job status"),
        help_text=_("Current status of the send job"),
        db_index=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Created by"),
        help_text=_("User who created this send job"),
        related_name="email_send_jobs",
    )
    client_request_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("Client request ID"),
        help_text=_("Optional idempotency key provided by client"),
        db_index=True,
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Started at"),
        help_text=_("When the job started processing"),
    )
    finished_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Finished at"),
        help_text=_("When the job finished processing"),
    )

    class Meta:
        verbose_name = _("Email send job")
        verbose_name_plural = _("Email send jobs")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["created_by", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"Job {self.id} - {self.template_slug} ({self.status})"


class EmailSendRecipient(BaseModel):
    """Represents an individual recipient in an email send job.

    Tracks the status and details of each email sent as part of a bulk job,
    including retry attempts and error messages.
    """

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        SENT = "sent", _("Sent")
        FAILED = "failed", _("Failed")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(
        EmailSendJob,
        on_delete=models.CASCADE,
        related_name="recipients",
        verbose_name=_("Send job"),
        help_text=_("The send job this recipient belongs to"),
    )
    email = models.EmailField(
        verbose_name=_("Recipient email"),
        help_text=_("Email address of the recipient"),
        db_index=True,
    )
    data = models.JSONField(
        verbose_name=_("Template data"),
        help_text=_("Data used to render the template for this recipient"),
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name=_("Send status"),
        help_text=_("Current status of this email"),
        db_index=True,
    )
    attempts = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Attempt count"),
        help_text=_("Number of send attempts"),
    )
    last_error = models.TextField(
        blank=True,
        verbose_name=_("Last error"),
        help_text=_("Error message from the last failed attempt"),
    )
    message_id = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Message ID"),
        help_text=_("Provider message ID for tracking"),
    )
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Sent at"),
        help_text=_("When the email was successfully sent"),
    )

    class Meta:
        verbose_name = _("Email send recipient")
        verbose_name_plural = _("Email send recipients")
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["job", "status"]),
            models.Index(fields=["job", "created_at"]),
            models.Index(fields=["email", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.email} - {self.status}"
