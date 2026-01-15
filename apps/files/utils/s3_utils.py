"""S3 utilities for file upload management."""

import logging
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
from apps.files.utils.storage_utils import build_storage_key, get_storage_prefix
from libs.retry import retry

logger = logging.getLogger(__name__)


class S3FileUploadService:
    """Service for handling S3 file upload operations."""

    def __init__(self):
        """Initialize S3 client with AWS credentials from settings."""
        kwargs = {
            "aws_access_key_id": settings.AWS_ACCESS_KEY_ID,
            "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY,
            "region_name": settings.AWS_REGION_NAME,
        }
        if hasattr(settings, "AWS_S3_ENDPOINT_URL") and settings.AWS_S3_ENDPOINT_URL:
            kwargs["endpoint_url"] = settings.AWS_S3_ENDPOINT_URL

        self.s3_client = boto3.client("s3", **kwargs)
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

        # Generate S3 key for presigned URL (includes prefix for boto3)
        s3_key = build_storage_key(S3_TMP_PREFIX, file_token, file_name, include_prefix=True)

        # Generate file_path for cache/database (without prefix for default_storage)
        file_path = build_storage_key(S3_TMP_PREFIX, file_token, file_name, include_prefix=False)

        try:
            # Generate presigned URL for PUT operation
            # Include ContentType in signature to ensure client uploads with correct type
            presigned_url = self.s3_client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": s3_key,  # Use full S3 key with prefix
                    "ContentType": file_type,
                },
                ExpiresIn=expiration,
            )

            logger.info(
                f"Generated presigned URL for upload: s3_key={s3_key}, file_path={file_path}, purpose={purpose}"
            )

            return {
                "upload_url": presigned_url,
                "file_path": file_path,  # Return path without prefix for storage in cache/DB
                "file_token": file_token,
            }

        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise Exception(_("Failed to generate presigned URL: {error}").format(error=str(e)))

    def _get_s3_key(self, file_path: str) -> str:
        """
        Convert a file_path (without prefix) to full S3 key (with prefix).

        Args:
            file_path: File path as stored in FileModel (without prefix)

        Returns:
            Full S3 key with prefix for boto3 operations
        """
        prefix = get_storage_prefix()
        if prefix and not file_path.startswith(f"{prefix}/"):
            return f"{prefix}/{file_path}"
        return file_path

    def check_file_exists(self, file_path: str) -> bool:
        """
        Check if a file exists in S3.

        Args:
            file_path: File path (with or without prefix)

        Returns:
            True if file exists, False otherwise
        """
        s3_key = self._get_s3_key(file_path)
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except ClientError:
            return False

    def move_file(self, source_path: str, destination_path: str, max_retries: int = 3) -> bool:
        """
        Move a file from source to destination in S3 with retry logic.

        Args:
            source_path: Source file path (with or without prefix)
            destination_path: Destination file path (with or without prefix)
            max_retries: Maximum number of retry attempts (default: 3)

        Returns:
            True if successful

        Raises:
            Exception: If move operation fails after all retries
        """
        # Convert to full S3 keys with prefix
        source_key = self._get_s3_key(source_path)
        dest_key = self._get_s3_key(destination_path)

        # Wrap the actual copy/delete into a small callable and use the
        # reusable `retry` decorator for retry/backoff behavior. We catch and
        # transform ClientError into a user-friendly Exception below to keep the
        # original behavior.

        @retry(
            max_attempts=max_retries,
            exceptions=(ClientError,),
            delay=1.0,
            backoff=2.0,
            logger=logger,
            raise_on_final=True,
        )
        def _do_move() -> bool:
            copy_source = {"Bucket": self.bucket_name, "Key": source_key}
            self.s3_client.copy_object(CopySource=copy_source, Bucket=self.bucket_name, Key=dest_key)
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=source_key)

            logger.info(
                f"Successfully moved file: {source_path} -> {destination_path} (S3: {source_key} -> {dest_key})"
            )

            return True

        try:
            return _do_move()
        except ClientError as e:
            logger.error(
                f"Failed to move file after {max_retries} attempts: {source_path} -> {destination_path}, error: {e}"
            )
            raise Exception(_("Failed to move file in S3: {error}").format(error=str(e)))

    def get_file_metadata(self, file_path: str) -> Optional[dict]:
        """
        Get metadata for a file in S3.

        Args:
            file_path: File path (with or without prefix)

        Returns:
            Dictionary containing file metadata or None if not found
        """
        s3_key = self._get_s3_key(file_path)
        try:
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
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
            file_path: File path to delete (with or without prefix)

        Returns:
            True if successful

        Raises:
            Exception: If delete operation fails
        """
        s3_key = self._get_s3_key(file_path)
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
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
            file_path: File path (with or without prefix)
            expiration: URL expiration time in seconds (default: 1 hour)
            as_attachment: If True, forces download. If False, allows inline viewing
            file_name: Optional filename for Content-Disposition header

        Returns:
            Presigned GET URL

        Raises:
            Exception: If presigned URL generation fails
        """
        s3_key = self._get_s3_key(file_path)
        try:
            params = {
                "Bucket": self.bucket_name,
                "Key": s3_key,
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

        This returns a path WITHOUT the storage prefix, suitable for storing in FileModel.file_path.
        The prefix will be added automatically by default_storage methods.

        Args:
            purpose: File purpose/category
            file_name: Original file name
            object_id: Related object ID (optional)
            related_model: Related model name (optional, e.g., 'JobDescription')

        Returns:
            Permanent file path WITHOUT storage prefix (for use with default_storage)

        Examples:
            With related object:
                generate_permanent_path('job_description', 'file.pdf', object_id=15)
                -> 'uploads/job_description/15/file.pdf' (NO prefix)

            Without related object:
                generate_permanent_path('import_data', 'file.csv')
                -> 'uploads/import_data/unrelated/{uuid}/file.csv' (NO prefix)

        Note:
            The returned path does NOT include the storage prefix (AWS_LOCATION).
            This is intentional because default_storage.url() and default_storage.open()
            automatically prepend the prefix.
        """
        if object_id is not None:
            # Path with related object ID (without prefix)
            path = build_storage_key(S3_UPLOADS_PREFIX, purpose, str(object_id), file_name, include_prefix=False)
        else:
            # Path for unrelated files - use UUID to avoid collisions (without prefix)
            unique_id = str(uuid.uuid4())
            path = build_storage_key(
                S3_UPLOADS_PREFIX, purpose, "unrelated", unique_id, file_name, include_prefix=False
            )

        logger.debug(f"Generated permanent path: {path} (purpose={purpose}, object_id={object_id})")
        return path
