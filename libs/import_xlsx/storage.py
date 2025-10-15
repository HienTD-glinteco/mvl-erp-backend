"""
Storage backend for import error reports.
"""

import os
from datetime import datetime

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage


class ImportStorage:
    """
    Storage backend for import error reports and temporary files.
    """

    def __init__(self, storage_type="local"):
        """
        Initialize storage backend.

        Args:
            storage_type: 'local' or 's3'
        """
        self.storage_type = storage_type
        self.base_path = getattr(settings, "IMPORTER_LOCAL_STORAGE_PATH", "imports")

    def save_error_report(self, content: bytes, filename: str | None = None) -> str:
        """
        Save error report file.

        Args:
            content: File content as bytes
            filename: Optional filename (auto-generated if not provided)

        Returns:
            str: File path in storage
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"import_errors_{timestamp}.xlsx"

        # Ensure path includes the base directory
        file_path = os.path.join(self.base_path, "errors", filename)

        # Save using Django's storage backend
        saved_path = default_storage.save(file_path, ContentFile(content))

        return saved_path

    def get_url(self, file_path: str) -> str:
        """
        Get URL for accessing the file.

        Args:
            file_path: File path in storage

        Returns:
            str: URL to access the file
        """
        if self.storage_type == "s3":
            # For S3, generate a signed URL
            # Note: Django's default storage.url() doesn't support expire parameter
            # If using S3, configure AWS_QUERYSTRING_EXPIRE in settings
            return default_storage.url(file_path)
        else:
            # For local storage, return media URL
            return default_storage.url(file_path)

    def save_temp_file(self, content: bytes, filename: str) -> str:
        """
        Save temporary file for async processing.

        Args:
            content: File content as bytes
            filename: Filename

        Returns:
            str: File path in storage
        """
        # Ensure path includes the base directory
        file_path = os.path.join(self.base_path, "temp", filename)

        # Save using Django's storage backend
        saved_path = default_storage.save(file_path, ContentFile(content))

        return saved_path

    def delete_file(self, file_path: str) -> None:
        """
        Delete file from storage.

        Args:
            file_path: File path in storage
        """
        if default_storage.exists(file_path):
            default_storage.delete(file_path)


def get_storage_backend(storage_type=None):
    """
    Get storage backend instance.

    Args:
        storage_type: Optional storage type override

    Returns:
        ImportStorage: Storage backend instance
    """
    if storage_type is None:
        storage_type = getattr(settings, "IMPORTER_STORAGE_BACKEND", "local")

    return ImportStorage(storage_type)
