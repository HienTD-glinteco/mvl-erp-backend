from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from apps.files.utils.s3_utils import S3FileUploadService
from libs.models import BaseModel


class FileModel(BaseModel):
    """
    Generic file model that can be linked to any Django model using Generic Relations.

    This model stores metadata about files uploaded to S3 and supports a two-phase
    upload process: presign (temporary) -> confirm (permanent).
    """

    purpose = models.CharField(
        max_length=100,
        verbose_name="Purpose",
        help_text="File purpose category (e.g., job_description, invoice, employee_cv)",
    )
    file_name = models.CharField(
        max_length=255,
        verbose_name="File name",
        help_text="Original name of the uploaded file",
    )
    file_path = models.CharField(
        max_length=500,
        verbose_name="File path",
        help_text="S3 path where the file is stored",
    )
    size = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name="File size",
        help_text="File size in bytes",
    )
    checksum = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        verbose_name="Checksum",
        help_text="MD5 checksum for file integrity verification",
    )
    is_confirmed = models.BooleanField(
        default=False,
        verbose_name="Confirmed",
        help_text="Whether the file upload has been confirmed",
    )
    uploaded_by = models.ForeignKey(
        "core.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_files",
        verbose_name="Uploaded by",
        help_text="User who uploaded this file",
    )

    # Generic foreign key to link to any model
    content_type = models.ForeignKey(
        ContentType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Content type",
    )
    object_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Object ID",
    )
    related_object = GenericForeignKey("content_type", "object_id")

    class Meta:
        db_table = "files_file"
        verbose_name = "File"
        verbose_name_plural = "Files"
        indexes = [
            models.Index(fields=["purpose", "is_confirmed"]),
            models.Index(fields=["content_type", "object_id"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.purpose} - {self.file_name}"

    @property
    def view_url(self) -> str:
        """
        Generate a presigned URL for viewing the file (inline display).

        Returns:
            Presigned URL that allows viewing the file in browser
        """
        service = S3FileUploadService()
        return service.generate_view_url(self.file_path)

    @property
    def download_url(self) -> str:
        """
        Generate a presigned URL for downloading the file.

        Returns:
            Presigned URL that forces file download with original filename
        """
        service = S3FileUploadService()
        return service.generate_download_url(self.file_path, self.file_name)
