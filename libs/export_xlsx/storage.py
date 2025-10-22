"""
Storage backends for saving and serving exported files.
"""

import os
from datetime import datetime

import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage, default_storage

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

    Uses FileSystemStorage to ensure files are saved locally,
    regardless of default_storage configuration.
    """

    def __init__(self):
        """Initialize local storage backend."""
        self.storage_path = getattr(settings, "EXPORTER_LOCAL_STORAGE_PATH", "exports")

        # Use FileSystemStorage to ensure local file system is used
        media_root = getattr(settings, "MEDIA_ROOT", "media")
        location = os.path.join(media_root, self.storage_path)
        base_url = f"{getattr(settings, 'MEDIA_URL', '/media/')}{self.storage_path}/"

        self.storage = FileSystemStorage(location=location, base_url=base_url)

    def save(self, file_content, filename):
        """
        Save file to local filesystem.

        Args:
            file_content: File content (BytesIO or bytes)
            filename: Filename to save

        Returns:
            str: File path relative to storage location
        """
        # Create filename with timestamp to avoid collisions
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        timestamped_filename = f"{timestamp}_{filename}"

        # Save using FileSystemStorage
        if hasattr(file_content, "read"):
            content = file_content.read()
        else:
            content = file_content

        saved_path = self.storage.save(timestamped_filename, ContentFile(content))
        return saved_path

    def get_url(self, file_path):
        """
        Get URL for accessing the file.

        Args:
            file_path: File path in storage

        Returns:
            str: Accessible URL
        """
        return self.storage.url(file_path)


class S3StorageBackend(StorageBackend):
    """
    AWS S3 storage backend.

    Uses default_storage for saving files and boto3 for generating signed URLs.
    This ensures exports are stored in S3 with secure, time-limited access URLs.
    """

    def __init__(self):
        """Initialize S3 storage backend."""
        self.bucket_name = getattr(settings, "EXPORTER_S3_BUCKET_NAME", None)
        self.signed_url_expire = getattr(settings, "EXPORTER_S3_SIGNED_URL_EXPIRE", 3600)

        if not self.bucket_name:
            self.bucket_name = getattr(settings, "AWS_STORAGE_BUCKET_NAME", None)

        # Use default_storage which should be S3
        self.storage = default_storage
        self.storage_path = getattr(settings, "EXPORTER_LOCAL_STORAGE_PATH", "exports")

        # Initialize boto3 S3 client for signed URL generation
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=getattr(settings, "AWS_ACCESS_KEY_ID", None),
            aws_secret_access_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", None),
            region_name=getattr(settings, "AWS_REGION_NAME", None),
        )

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
        file_path = f"{self.storage_path}/{timestamp}_{filename}"

        # Save using S3 storage
        if hasattr(file_content, "read"):
            content = file_content.read()
        else:
            content = file_content

        saved_path = self.storage.save(file_path, ContentFile(content))
        return saved_path

    def get_url(self, file_path):
        """
        Get signed URL for accessing the file from S3.

        Args:
            file_path: S3 object key

        Returns:
            str: Signed URL for secure access
        """
        # Generate signed URL using boto3 for secure access
        if self.s3_client and self.bucket_name:
            try:
                # Add AWS_LOCATION prefix if configured
                aws_location = getattr(settings, "AWS_LOCATION", "")
                if aws_location and not file_path.startswith(aws_location):
                    s3_key = f"{aws_location}/{file_path}"
                else:
                    s3_key = file_path

                # Generate presigned URL
                signed_url = self.s3_client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket_name, "Key": s3_key},
                    ExpiresIn=self.signed_url_expire,
                )
                return signed_url
            except ClientError:
                # If signed URL generation fails, fall back to storage URL
                pass

        # Fallback to default storage URL
        return self.storage.url(file_path)


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
