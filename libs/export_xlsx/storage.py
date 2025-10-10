"""
Storage backends for saving and serving exported files.
"""

import os
from datetime import datetime

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from .constants import ERROR_INVALID_STORAGE, STORAGE_LOCAL, STORAGE_S3


class StorageBackend:
    """
    Base class for storage backends.
    """

    def save(self, file_content, filename):
        """
        Save file to storage.

        Args:
            file_content: File content (BytesIO or bytes)
            filename: Filename to save

        Returns:
            str: File path or URL
        """
        raise NotImplementedError

    def get_url(self, file_path):
        """
        Get URL for accessing the file.

        Args:
            file_path: File path in storage

        Returns:
            str: Accessible URL
        """
        raise NotImplementedError


class LocalStorageBackend(StorageBackend):
    """
    Local filesystem storage backend.
    """

    def __init__(self):
        """Initialize local storage backend."""
        self.storage_path = getattr(settings, "EXPORTER_LOCAL_STORAGE_PATH", "exports")

    def save(self, file_content, filename):
        """
        Save file to local storage.

        Args:
            file_content: File content (BytesIO or bytes)
            filename: Filename to save

        Returns:
            str: File path relative to MEDIA_ROOT
        """
        # Create path with timestamp to avoid collisions
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(self.storage_path, f"{timestamp}_{filename}")

        # Save using Django's default storage
        if hasattr(file_content, "read"):
            content = file_content.read()
        else:
            content = file_content

        saved_path = default_storage.save(file_path, ContentFile(content))
        return saved_path

    def get_url(self, file_path):
        """
        Get URL for accessing the file.

        Args:
            file_path: File path in storage

        Returns:
            str: Accessible URL
        """
        return default_storage.url(file_path)


class S3StorageBackend(StorageBackend):
    """
    AWS S3 storage backend.
    """

    def __init__(self):
        """Initialize S3 storage backend."""
        self.bucket_name = getattr(settings, "EXPORTER_S3_BUCKET_NAME", None)
        self.signed_url_expire = getattr(settings, "EXPORTER_S3_SIGNED_URL_EXPIRE", 3600)

        if not self.bucket_name:
            self.bucket_name = getattr(settings, "AWS_STORAGE_BUCKET_NAME", None)

    def save(self, file_content, filename):
        """
        Save file to S3 storage.

        Args:
            file_content: File content (BytesIO or bytes)
            filename: Filename to save

        Returns:
            str: S3 object key
        """
        # Create path with timestamp to avoid collisions
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        storage_path = getattr(settings, "EXPORTER_LOCAL_STORAGE_PATH", "exports")
        file_path = f"{storage_path}/{timestamp}_{filename}"

        # Save using Django's default storage (should be S3)
        if hasattr(file_content, "read"):
            content = file_content.read()
        else:
            content = file_content

        saved_path = default_storage.save(file_path, ContentFile(content))
        return saved_path

    def get_url(self, file_path):
        """
        Get signed URL for accessing the file.

        Args:
            file_path: S3 object key

        Returns:
            str: Signed URL
        """
        # Django storage will handle URL generation
        return default_storage.url(file_path)


def get_storage_backend(backend_type=None):
    """
    Get storage backend instance.

    Args:
        backend_type: Storage backend type ('local' or 's3')

    Returns:
        StorageBackend: Storage backend instance

    Raises:
        ValueError: If backend_type is invalid
    """
    if backend_type is None:
        backend_type = getattr(settings, "EXPORTER_STORAGE_BACKEND", STORAGE_LOCAL)

    if backend_type == STORAGE_LOCAL:
        return LocalStorageBackend()
    elif backend_type == STORAGE_S3:
        return S3StorageBackend()
    else:
        raise ValueError(f"{ERROR_INVALID_STORAGE}: {backend_type}")
