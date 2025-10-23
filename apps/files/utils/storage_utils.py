"""Storage utilities for handling S3 paths with storage prefix support."""

import logging
from typing import Optional

from django.conf import settings
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)


def get_storage_prefix() -> str:
    """
    Get the configured storage prefix from settings.

    Checks for storage prefix in the following order:
    1. default_storage.location (for S3Boto3Storage)
    2. settings.AWS_LOCATION
    3. Empty string if no prefix is configured

    Returns:
        Storage prefix without leading/trailing slashes, or empty string
    """
    prefix = ""

    # Try to get location from default_storage (works with S3Boto3Storage)
    if hasattr(default_storage, "location"):
        prefix = default_storage.location or ""
    # Fallback to AWS_LOCATION setting
    elif hasattr(settings, "AWS_LOCATION"):
        prefix = settings.AWS_LOCATION or ""

    # Strip leading and trailing slashes
    prefix = prefix.strip("/")

    logger.debug(f"Storage prefix: '{prefix}'")
    return prefix


def build_storage_key(*segments: str, include_prefix: bool = True) -> str:
    """
    Build a storage key from path segments.

    This function:
    1. Joins all segments with '/' (stripping individual slashes)
    2. Optionally prepends the storage prefix if configured

    Args:
        *segments: Variable number of path segments to join
        include_prefix: Whether to include the storage prefix (default: True)
                       Set to False when building paths for FileModel.file_path

    Returns:
        Storage key with or without prefix

    Examples:
        With prefix='media', include_prefix=True:
            build_storage_key('uploads', 'tmp', 'file.pdf') -> 'media/uploads/tmp/file.pdf'

        With prefix='media', include_prefix=False:
            build_storage_key('uploads', 'tmp', 'file.pdf', include_prefix=False) -> 'uploads/tmp/file.pdf'

        Without prefix configured:
            build_storage_key('uploads', 'tmp', 'file.pdf') -> 'uploads/tmp/file.pdf'

    Notes:
        - Use include_prefix=True for direct boto3 S3 operations (presigned URLs, copy, head_object)
        - Use include_prefix=False for FileModel.file_path (default_storage adds prefix automatically)
    """
    prefix = get_storage_prefix() if include_prefix else ""

    # Filter out empty segments and strip slashes from each segment
    cleaned_segments = [s.strip("/") for s in segments if s]

    # Join segments
    path = "/".join(cleaned_segments)

    # Prepend prefix if it exists
    if prefix:
        result = f"{prefix}/{path}"
    else:
        result = path

    logger.debug(f"Built storage key: '{result}' from segments: {segments} (include_prefix={include_prefix})")
    return result


def resolve_actual_storage_key(db_file_path: str, s3_client=None, bucket_name: str = "") -> str:
    """
    Resolve the actual storage key for a file path from the database.

    This function provides backward compatibility during migration by checking
    if a file exists with the storage prefix prepended to the database path.

    Logic:
    1. If db_file_path already starts with prefix -> return it as-is
    2. If prefix exists and prefixed path exists in S3 -> return prefixed path
    3. Otherwise -> return db_file_path unchanged (fallback)

    Args:
        db_file_path: File path as stored in database
        s3_client: Optional boto3 S3 client (if None, will be imported)
        bucket_name: Optional bucket name (if empty, will use settings)

    Returns:
        Actual S3 key that exists in storage

    Examples:
        prefix='media', db_file_path='uploads/file.pdf', object exists at 'media/uploads/file.pdf'
            -> returns 'media/uploads/file.pdf'

        prefix='media', db_file_path='media/uploads/file.pdf'
            -> returns 'media/uploads/file.pdf' (already has prefix)

        prefix='', db_file_path='uploads/file.pdf'
            -> returns 'uploads/file.pdf' (no prefix configured)
    """
    # Handle empty or invalid paths
    if not db_file_path:
        logger.warning("Empty file path provided to resolve_actual_storage_key")
        return db_file_path

    # Strip leading slashes to avoid double slashes
    db_file_path = db_file_path.lstrip("/")

    prefix = get_storage_prefix()

    # If no prefix configured, return original path
    if not prefix:
        logger.debug(f"No prefix configured, returning original path: {db_file_path}")
        return db_file_path

    # If path already starts with prefix, return it
    if db_file_path.startswith(f"{prefix}/"):
        logger.debug(f"Path already has prefix: {db_file_path}")
        return db_file_path

    # Construct candidate prefixed path
    candidate_path = f"{prefix}/{db_file_path}"

    # Check if prefixed path exists in S3
    try:
        # Import here to avoid circular dependency
        if s3_client is None:
            import boto3

            s3_client = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION_NAME,
            )

        if not bucket_name:
            bucket_name = settings.AWS_STORAGE_BUCKET_NAME

        # Try to check if object exists
        s3_client.head_object(Bucket=bucket_name, Key=candidate_path)
        logger.info(f"Resolved path with prefix: {db_file_path} -> {candidate_path}")
        return candidate_path

    except Exception as e:
        # If object doesn't exist or any error, return original path
        logger.debug(f"Prefixed path not found or error, using original: {db_file_path} (Error: {e})")
        return db_file_path
