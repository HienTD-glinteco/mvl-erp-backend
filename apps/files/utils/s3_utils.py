"""S3 utilities for file upload management."""

import uuid
from typing import Optional

import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.utils.translation import gettext as _

from apps.files.constants import PRESIGNED_URL_EXPIRATION, S3_TMP_PREFIX, S3_UPLOADS_PREFIX


class S3FileUploadService:
    """Service for handling S3 file upload operations."""

    def __init__(self):
        """Initialize S3 client with AWS credentials from settings."""
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION_NAME,
        )
        self.bucket_name = settings.AWS_STORAGE_BUCKET_NAME

    def generate_presigned_url(
        self,
        file_name: str,
        file_size: int,
        purpose: str,
        expiration: int = PRESIGNED_URL_EXPIRATION,
    ) -> dict[str, str]:
        """
        Generate a presigned URL for uploading a file to S3.

        Args:
            file_name: Original name of the file
            file_size: Size of the file in bytes
            purpose: Purpose/category of the file
            expiration: URL expiration time in seconds (default: 1 hour)

        Returns:
            Dictionary containing upload_url, file_path, and file_token

        Raises:
            Exception: If presigned URL generation fails
        """
        # Generate unique file token
        file_token = str(uuid.uuid4())

        # Generate unique temporary path
        temp_path = f"{S3_TMP_PREFIX}{file_token}/{file_name}"

        try:
            # Generate presigned URL for PUT operation
            presigned_url = self.s3_client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": temp_path,
                    "ContentLength": file_size,
                },
                ExpiresIn=expiration,
            )

            return {
                "upload_url": presigned_url,
                "file_path": temp_path,
                "file_token": file_token,
            }

        except ClientError as e:
            raise Exception(_("Failed to generate presigned URL: {error}").format(error=str(e)))

    def check_file_exists(self, file_path: str) -> bool:
        """
        Check if a file exists in S3.

        Args:
            file_path: S3 key/path to check

        Returns:
            True if file exists, False otherwise
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=file_path)
            return True
        except ClientError:
            return False

    def move_file(self, source_path: str, destination_path: str) -> bool:
        """
        Move a file from source to destination in S3.

        Args:
            source_path: Source S3 key
            destination_path: Destination S3 key

        Returns:
            True if successful, False otherwise

        Raises:
            Exception: If move operation fails
        """
        try:
            # Copy object to new location
            copy_source = {"Bucket": self.bucket_name, "Key": source_path}
            self.s3_client.copy_object(CopySource=copy_source, Bucket=self.bucket_name, Key=destination_path)

            # Delete original object
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=source_path)

            return True

        except ClientError as e:
            raise Exception(_("Failed to move file in S3: {error}").format(error=str(e)))

    def get_file_metadata(self, file_path: str) -> Optional[dict]:
        """
        Get metadata for a file in S3.

        Args:
            file_path: S3 key/path

        Returns:
            Dictionary containing file metadata or None if not found
        """
        try:
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=file_path)
            return {
                "size": response.get("ContentLength"),
                "etag": response.get("ETag", "").strip('"'),
                "last_modified": response.get("LastModified"),
                "content_type": response.get("ContentType"),
            }
        except ClientError:
            return None

    def generate_permanent_path(self, purpose: str, object_id: int, file_name: str) -> str:
        """
        Generate permanent path for a confirmed file.

        Args:
            purpose: File purpose/category
            object_id: Related object ID
            file_name: Original file name

        Returns:
            Permanent S3 path
        """
        return f"{S3_UPLOADS_PREFIX}{purpose}/{object_id}/{file_name}"
