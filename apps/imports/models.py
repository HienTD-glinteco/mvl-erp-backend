import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from .constants import IMPORT_JOB_STATUS_CHOICES, STATUS_QUEUED


class ImportJob(models.Model):
    """
    Model to track asynchronous import jobs.

    This model stores metadata about file import operations, including progress tracking,
    result files, and status information.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name=_("ID"),
    )
    file = models.ForeignKey(
        "files.FileModel",
        on_delete=models.PROTECT,
        related_name="import_jobs",
        verbose_name=_("File"),
        help_text=_("Source file for import"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="import_jobs",
        verbose_name=_("Created by"),
        help_text=_("User who initiated the import"),
    )
    celery_task_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_("Celery task ID"),
        help_text=_("Celery task ID for tracking the background job"),
    )
    status = models.CharField(
        max_length=20,
        default=STATUS_QUEUED,
        choices=IMPORT_JOB_STATUS_CHOICES,
        verbose_name=_("Status"),
        help_text=_("Current status of the import job"),
    )
    total_rows = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_("Total rows"),
        help_text=_("Total number of rows to process"),
    )
    processed_rows = models.IntegerField(
        default=0,
        verbose_name=_("Processed rows"),
        help_text=_("Number of rows processed"),
    )
    success_count = models.IntegerField(
        default=0,
        verbose_name=_("Success count"),
        help_text=_("Number of rows processed successfully"),
    )
    failure_count = models.IntegerField(
        default=0,
        verbose_name=_("Failure count"),
        help_text=_("Number of rows that failed processing"),
    )
    percentage = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_("Percentage"),
        help_text=_("Percentage of completion (0-100)"),
    )
    options = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_("Options"),
        help_text=_("Import options including handler path and other settings"),
    )
    result_success_s3_path = models.CharField(
        max_length=1024,
        null=True,
        blank=True,
        verbose_name=_("Success result S3 path"),
        help_text=_("S3 path for successfully processed rows file"),
    )
    result_failed_s3_path = models.CharField(
        max_length=1024,
        null=True,
        blank=True,
        verbose_name=_("Failed result S3 path"),
        help_text=_("S3 path for failed rows file"),
    )
    result_success_file = models.ForeignKey(
        "files.FileModel",
        null=True,
        blank=True,
        related_name="import_success_for",
        on_delete=models.SET_NULL,
        verbose_name=_("Success result file"),
        help_text=_("FileModel record for successfully processed rows"),
    )
    result_failed_file = models.ForeignKey(
        "files.FileModel",
        null=True,
        blank=True,
        related_name="import_failed_for",
        on_delete=models.SET_NULL,
        verbose_name=_("Failed result file"),
        help_text=_("FileModel record for failed rows"),
    )
    error_message = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("Error message"),
        help_text=_("Error message if the import failed"),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created at"),
        help_text=_("Date and time when the import job was created"),
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Started at"),
        help_text=_("Date and time when the import job started processing"),
    )
    finished_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Finished at"),
        help_text=_("Date and time when the import job finished"),
    )

    class Meta:
        db_table = "imports_job"
        verbose_name = _("Import Job")
        verbose_name_plural = _("Import Jobs")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_by", "status"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["celery_task_id"]),
        ]

    def __str__(self):
        return f"ImportJob {self.id} - {self.status}"

    def calculate_percentage(self):
        """Calculate and update the percentage of completion."""
        if self.total_rows and self.total_rows > 0:
            self.percentage = (self.processed_rows / self.total_rows) * 100.0
        else:
            self.percentage = None
