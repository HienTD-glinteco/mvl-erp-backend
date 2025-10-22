"""S3 utilities for file upload management."""

import logging
import time
import uuid
from typing import Optional

import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.utils.translation import gettext as _

from apps.files.constants import (
    PRESIGNED_GET_URL_EXPIRATION,
    PRESIGNED_URL_EXPIRATION,
    S3_TMP_PREFIX,
    S3_UPLOADS_PREFIX,
)
from apps.files.utils.storage_utils import build_storage_key

logger = logging.getLogger(__name__)


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
        file_type: str,
        purpose: str,
        expiration: int = PRESIGNED_URL_EXPIRATION,
    ) -> dict[str, str]:
        """
        Generate a presigned URL for uploading a file to S3.

        Args:
            file_name: Original name of the file
            file_type: MIME type of the file (e.g., application/pdf)
            purpose: Purpose/category of the file
            expiration: URL expiration time in seconds (default: 1 hour)

        Returns:
            Dictionary containing upload_url, file_path, and file_token

        Raises:
            Exception: If presigned URL generation fails
        """
        # Generate unique file token
        file_token = str(uuid.uuid4())

        # Generate unique temporary path with storage prefix
        temp_path = build_storage_key(S3_TMP_PREFIX, file_token, file_name)

        try:
            # Generate presigned URL for PUT operation
            # Include ContentType in signature to ensure client uploads with correct type
            presigned_url = self.s3_client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": temp_path,
                    "ContentType": file_type,
                },
                ExpiresIn=expiration,
            )

            logger.info(f"Generated presigned URL for upload: key={temp_path}, purpose={purpose}")

            return {
                "upload_url": presigned_url,
                "file_path": temp_path,
                "file_token": file_token,
            }

        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
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

    def move_file(self, source_path: str, destination_path: str, max_retries: int = 3) -> bool:
        """
        Move a file from source to destination in S3 with retry logic.

        Args:
            source_path: Source S3 key
            destination_path: Destination S3 key
            max_retries: Maximum number of retry attempts (default: 3)

        Returns:
            True if successful

        Raises:
            Exception: If move operation fails after all retries
        """
        retry_delay = 1  # Initial delay in seconds

        for attempt in range(max_retries):
            try:
                # Copy object to new location
                copy_source = {"Bucket": self.bucket_name, "Key": source_path}
                self.s3_client.copy_object(CopySource=copy_source, Bucket=self.bucket_name, Key=destination_path)

                # Delete original object
                self.s3_client.delete_object(Bucket=self.bucket_name, Key=source_path)

                logger.info(f"Successfully moved file: {source_path} -> {destination_path}")
                return True

            except ClientError as e:
                logger.warning(
                    f"Failed to move file (attempt {attempt + 1}/{max_retries}): {source_path} -> {destination_path}, error: {e}"
                )

                if attempt < max_retries - 1:
                    # Exponential backoff
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    # Final attempt failed
                    logger.error(f"Failed to move file after {max_retries} attempts: {source_path} -> {destination_path}")
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

    def delete_file(self, file_path: str) -> bool:
        """
        Delete a file from S3.

        Args:
            file_path: S3 key/path to delete

        Returns:
            True if successful, False otherwise

        Raises:
            Exception: If delete operation fails
        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=file_path)
            return True
        except ClientError as e:
            raise Exception(_("Failed to delete file from S3: {error}").format(error=str(e)))

    def generate_presigned_get_url(
        self,
        file_path: str,
        expiration: int = PRESIGNED_GET_URL_EXPIRATION,
        as_attachment: bool = False,
        file_name: Optional[str] = None,
    ) -> str:
        """
        Generate a presigned URL for viewing or downloading a file from S3.

        Args:
            file_path: S3 key/path of the file
            expiration: URL expiration time in seconds (default: 1 hour)
            as_attachment: If True, forces download. If False, allows inline viewing
            file_name: Optional filename for Content-Disposition header

        Returns:
            Presigned GET URL

        Raises:
            Exception: If presigned URL generation fails
        """
        try:
            params = {
                "Bucket": self.bucket_name,
                "Key": file_path,
            }

            # Add Content-Disposition header if needed
            if as_attachment and file_name:
                params["ResponseContentDisposition"] = f'attachment; filename="{file_name}"'
            elif as_attachment:
                params["ResponseContentDisposition"] = "attachment"

            presigned_url = self.s3_client.generate_presigned_url(
                "get_object",
                Params=params,
                ExpiresIn=expiration,
            )

            return presigned_url

        except ClientError as e:
            raise Exception(_("Failed to generate presigned GET URL: {error}").format(error=str(e)))

    def generate_view_url(self, file_path: str, expiration: int = PRESIGNED_GET_URL_EXPIRATION) -> str:
        """
        Generate a presigned URL for viewing a file (inline display).

        Args:
            file_path: S3 key/path of the file
            expiration: URL expiration time in seconds (default: 1 hour)

        Returns:
            Presigned URL for viewing the file
        """
        return self.generate_presigned_get_url(file_path, expiration, as_attachment=False)

    def generate_download_url(
        self, file_path: str, file_name: str, expiration: int = PRESIGNED_GET_URL_EXPIRATION
    ) -> str:
        """
        Generate a presigned URL for downloading a file.

        Args:
            file_path: S3 key/path of the file
            file_name: Filename to use for download
            expiration: URL expiration time in seconds (default: 1 hour)

        Returns:
            Presigned URL for downloading the file
        """
        return self.generate_presigned_get_url(file_path, expiration, as_attachment=True, file_name=file_name)

    def generate_permanent_path(
        self, purpose: str, file_name: str, object_id: Optional[int] = None, related_model: Optional[str] = None
    ) -> str:
        """
        Generate permanent path for a confirmed file.

        Args:
            purpose: File purpose/category
            file_name: Original file name
            object_id: Related object ID (optional)
            related_model: Related model name (optional, e.g., 'JobDescription')

        Returns:
            Permanent S3 path with storage prefix

        Examples:
            With related object:
                generate_permanent_path('job_description', 'file.pdf', object_id=15)
                -> 'media/uploads/job_description/15/file.pdf' (with prefix='media')

            Without related object:
                generate_permanent_path('import_data', 'file.csv')
                -> 'media/uploads/import_data/unrelated/{uuid}/file.csv' (with prefix='media')
        """
        if object_id is not None:
            # Path with related object ID
            path = build_storage_key(S3_UPLOADS_PREFIX, purpose, str(object_id), file_name)
        else:
            # Path for unrelated files - use UUID to avoid collisions
            unique_id = str(uuid.uuid4())
            path = build_storage_key(S3_UPLOADS_PREFIX, purpose, "unrelated", unique_id, file_name)

        logger.debug(f"Generated permanent path: {path} (purpose={purpose}, object_id={object_id})")
        return path
