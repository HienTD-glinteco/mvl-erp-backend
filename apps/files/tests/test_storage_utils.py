"""Tests for storage utilities."""

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError
from django.test import TestCase, override_settings

from apps.files.utils.storage_utils import build_storage_key, get_storage_prefix, resolve_actual_storage_key


class GetStoragePrefixTest(TestCase):
    """Test cases for get_storage_prefix function."""

    @override_settings(AWS_LOCATION="media")
    def test_get_storage_prefix_from_settings(self):
        """Test getting storage prefix from AWS_LOCATION setting."""
        # Act
        result = get_storage_prefix()

        # Assert
        self.assertEqual(result, "media")

    @override_settings(AWS_LOCATION="  media/  ")
    def test_get_storage_prefix_strips_slashes(self):
        """Test that storage prefix strips leading/trailing slashes."""
        # Act
        result = get_storage_prefix()

        # Assert
        self.assertEqual(result, "media")

    @override_settings(AWS_LOCATION="")
    def test_get_storage_prefix_empty(self):
        """Test getting empty storage prefix when not configured."""
        # Act
        result = get_storage_prefix()

        # Assert
        self.assertEqual(result, "")

    @patch("apps.files.utils.storage_utils.default_storage")
    def test_get_storage_prefix_from_storage_location(self, mock_storage):
        """Test getting storage prefix from default_storage.location."""
        # Arrange
        mock_storage.location = "custom-prefix"

        # Act
        result = get_storage_prefix()

        # Assert
        self.assertEqual(result, "custom-prefix")


class BuildStorageKeyTest(TestCase):
    """Test cases for build_storage_key function."""

    @override_settings(AWS_LOCATION="media")
    def test_build_storage_key_with_prefix(self):
        """Test building storage key with prefix."""
        # Act
        result = build_storage_key("uploads", "tmp", "file.pdf")

        # Assert
        self.assertEqual(result, "media/uploads/tmp/file.pdf")

    @override_settings(AWS_LOCATION="")
    def test_build_storage_key_without_prefix(self):
        """Test building storage key without prefix."""
        # Act
        result = build_storage_key("uploads", "tmp", "file.pdf")

        # Assert
        self.assertEqual(result, "uploads/tmp/file.pdf")

    @override_settings(AWS_LOCATION="media")
    def test_build_storage_key_strips_slashes(self):
        """Test that build_storage_key strips slashes from segments."""
        # Act
        result = build_storage_key("/uploads/", "/tmp/", "/file.pdf")

        # Assert
        self.assertEqual(result, "media/uploads/tmp/file.pdf")

    @override_settings(AWS_LOCATION="media")
    def test_build_storage_key_single_segment(self):
        """Test building storage key with single segment."""
        # Act
        result = build_storage_key("file.pdf")

        # Assert
        self.assertEqual(result, "media/file.pdf")

    @override_settings(AWS_LOCATION="")
    def test_build_storage_key_empty_segments_filtered(self):
        """Test that empty segments are filtered out."""
        # Act
        result = build_storage_key("uploads", "", "tmp", None, "file.pdf")

        # Assert
        self.assertEqual(result, "uploads/tmp/file.pdf")


class ResolveActualStorageKeyTest(TestCase):
    """Test cases for resolve_actual_storage_key function."""

    @override_settings(
        AWS_LOCATION="media",
        AWS_ACCESS_KEY_ID="test-key",
        AWS_SECRET_ACCESS_KEY="test-secret",
        AWS_REGION_NAME="us-east-1",
        AWS_STORAGE_BUCKET_NAME="test-bucket",
    )
    @patch("boto3.client")
    def test_resolve_with_prefix_exists(self, mock_boto_client):
        """Test resolving key when prefixed path exists in S3."""
        # Arrange
        mock_s3 = MagicMock()
        mock_s3.head_object.return_value = {"ContentLength": 123456}
        mock_boto_client.return_value = mock_s3

        # Act
        result = resolve_actual_storage_key("uploads/test/file.pdf", s3_client=mock_s3, bucket_name="test-bucket")

        # Assert
        self.assertEqual(result, "media/uploads/test/file.pdf")
        mock_s3.head_object.assert_called_once_with(Bucket="test-bucket", Key="media/uploads/test/file.pdf")

    @override_settings(
        AWS_LOCATION="media",
        AWS_ACCESS_KEY_ID="test-key",
        AWS_SECRET_ACCESS_KEY="test-secret",
        AWS_REGION_NAME="us-east-1",
        AWS_STORAGE_BUCKET_NAME="test-bucket",
    )
    @patch("boto3.client")
    def test_resolve_with_prefix_not_exists(self, mock_boto_client):
        """Test resolving key when prefixed path doesn't exist in S3."""
        # Arrange
        mock_s3 = MagicMock()
        mock_s3.head_object.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}}, "head_object"
        )
        mock_boto_client.return_value = mock_s3

        # Act
        result = resolve_actual_storage_key("uploads/test/file.pdf", s3_client=mock_s3, bucket_name="test-bucket")

        # Assert
        self.assertEqual(result, "uploads/test/file.pdf")  # Falls back to original

    @override_settings(AWS_LOCATION="media")
    def test_resolve_already_has_prefix(self):
        """Test resolving key that already has prefix."""
        # Act
        result = resolve_actual_storage_key("media/uploads/test/file.pdf")

        # Assert
        self.assertEqual(result, "media/uploads/test/file.pdf")

    @override_settings(AWS_LOCATION="")
    def test_resolve_no_prefix_configured(self):
        """Test resolving key when no prefix is configured."""
        # Act
        result = resolve_actual_storage_key("uploads/test/file.pdf")

        # Assert
        self.assertEqual(result, "uploads/test/file.pdf")

    def test_resolve_empty_path(self):
        """Test resolving empty file path."""
        # Act
        result = resolve_actual_storage_key("")

        # Assert
        self.assertEqual(result, "")

    @override_settings(AWS_LOCATION="media")
    def test_resolve_path_with_leading_slash(self):
        """Test resolving path with leading slash."""
        # Act
        result = resolve_actual_storage_key("/uploads/test/file.pdf")

        # Assert
        # Should strip leading slash and check for prefix
        self.assertIn("uploads/test/file.pdf", result)
