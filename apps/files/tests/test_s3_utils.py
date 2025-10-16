"""Tests for S3 utilities."""

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError
from django.test import TestCase, override_settings

from apps.files.utils import S3FileUploadService


@override_settings(
    AWS_ACCESS_KEY_ID="test-key",
    AWS_SECRET_ACCESS_KEY="test-secret",
    AWS_REGION_NAME="us-east-1",
    AWS_STORAGE_BUCKET_NAME="test-bucket",
)
class S3FileUploadServiceTest(TestCase):
    """Test cases for S3FileUploadService."""

    def setUp(self):
        """Set up test data."""
        with patch("boto3.client"):
            self.service = S3FileUploadService()

    @patch("boto3.client")
    def test_generate_presigned_url_success(self, mock_boto_client):
        """Test successful presigned URL generation."""
        # Arrange
        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url.return_value = "https://s3.amazonaws.com/test-url"
        mock_boto_client.return_value = mock_s3

        service = S3FileUploadService()

        # Act
        result = service.generate_presigned_url(
            file_name="test.pdf",
            file_type="application/pdf",
            purpose="test_purpose",
        )

        # Assert
        self.assertIn("upload_url", result)
        self.assertIn("file_path", result)
        self.assertIn("file_token", result)
        self.assertIn("uploads/tmp/", result["file_path"])
        mock_s3.generate_presigned_url.assert_called_once()

    @patch("boto3.client")
    def test_generate_presigned_url_failure(self, mock_boto_client):
        """Test presigned URL generation failure."""
        # Arrange
        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url.side_effect = ClientError(
            {"Error": {"Code": "TestError", "Message": "Test error"}},
            "generate_presigned_url",
        )
        mock_boto_client.return_value = mock_s3

        service = S3FileUploadService()

        # Act & Assert
        with self.assertRaises(Exception):
            service.generate_presigned_url(
                file_name="test.pdf",
                file_type="application/pdf",
                purpose="test_purpose",
            )

    @patch("boto3.client")
    def test_check_file_exists_true(self, mock_boto_client):
        """Test checking file existence when file exists."""
        # Arrange
        mock_s3 = MagicMock()
        mock_s3.head_object.return_value = {"ContentLength": 123456}
        mock_boto_client.return_value = mock_s3

        service = S3FileUploadService()

        # Act
        result = service.check_file_exists("uploads/test/file.pdf")

        # Assert
        self.assertTrue(result)
        mock_s3.head_object.assert_called_once_with(Bucket="test-bucket", Key="uploads/test/file.pdf")

    @patch("boto3.client")
    def test_check_file_exists_false(self, mock_boto_client):
        """Test checking file existence when file doesn't exist."""
        # Arrange
        mock_s3 = MagicMock()
        mock_s3.head_object.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}},
            "head_object",
        )
        mock_boto_client.return_value = mock_s3

        service = S3FileUploadService()

        # Act
        result = service.check_file_exists("uploads/test/file.pdf")

        # Assert
        self.assertFalse(result)

    @patch("boto3.client")
    def test_move_file_success(self, mock_boto_client):
        """Test successful file move operation."""
        # Arrange
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        service = S3FileUploadService()

        # Act
        result = service.move_file("uploads/tmp/file.pdf", "uploads/final/file.pdf")

        # Assert
        self.assertTrue(result)
        mock_s3.copy_object.assert_called_once()
        mock_s3.delete_object.assert_called_once_with(Bucket="test-bucket", Key="uploads/tmp/file.pdf")

    @patch("boto3.client")
    def test_move_file_failure(self, mock_boto_client):
        """Test file move operation failure."""
        # Arrange
        mock_s3 = MagicMock()
        mock_s3.copy_object.side_effect = ClientError(
            {"Error": {"Code": "TestError", "Message": "Test error"}},
            "copy_object",
        )
        mock_boto_client.return_value = mock_s3

        service = S3FileUploadService()

        # Act & Assert
        with self.assertRaises(Exception):
            service.move_file("uploads/tmp/file.pdf", "uploads/final/file.pdf")

    @patch("boto3.client")
    def test_get_file_metadata_success(self, mock_boto_client):
        """Test successful file metadata retrieval."""
        # Arrange
        mock_s3 = MagicMock()
        mock_s3.head_object.return_value = {
            "ContentLength": 123456,
            "ETag": '"abc123def456"',
            "LastModified": "2025-10-16T00:00:00Z",
            "ContentType": "application/pdf",
        }
        mock_boto_client.return_value = mock_s3

        service = S3FileUploadService()

        # Act
        result = service.get_file_metadata("uploads/test/file.pdf")

        # Assert
        self.assertIsNotNone(result)
        self.assertEqual(result["size"], 123456)
        self.assertEqual(result["etag"], "abc123def456")
        self.assertEqual(result["content_type"], "application/pdf")

    @patch("boto3.client")
    def test_get_file_metadata_not_found(self, mock_boto_client):
        """Test file metadata retrieval when file doesn't exist."""
        # Arrange
        mock_s3 = MagicMock()
        mock_s3.head_object.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}},
            "head_object",
        )
        mock_boto_client.return_value = mock_s3

        service = S3FileUploadService()

        # Act
        result = service.get_file_metadata("uploads/test/file.pdf")

        # Assert
        self.assertIsNone(result)

    @patch("boto3.client")
    def test_delete_file_success(self, mock_boto_client):
        """Test successful file deletion."""
        # Arrange
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        service = S3FileUploadService()

        # Act
        result = service.delete_file("uploads/tmp/file.pdf")

        # Assert
        self.assertTrue(result)
        mock_s3.delete_object.assert_called_once_with(Bucket="test-bucket", Key="uploads/tmp/file.pdf")

    @patch("boto3.client")
    def test_delete_file_failure(self, mock_boto_client):
        """Test file deletion failure."""
        # Arrange
        mock_s3 = MagicMock()
        mock_s3.delete_object.side_effect = ClientError(
            {"Error": {"Code": "TestError", "Message": "Test error"}},
            "delete_object",
        )
        mock_boto_client.return_value = mock_s3

        service = S3FileUploadService()

        # Act & Assert
        with self.assertRaises(Exception):
            service.delete_file("uploads/tmp/file.pdf")

    @patch("boto3.client")
    def test_generate_view_url_success(self, mock_boto_client):
        """Test successful view URL generation."""
        # Arrange
        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url.return_value = "https://s3.amazonaws.com/view-url"
        mock_boto_client.return_value = mock_s3

        service = S3FileUploadService()

        # Act
        result = service.generate_view_url("uploads/test/file.pdf")

        # Assert
        self.assertEqual(result, "https://s3.amazonaws.com/view-url")
        mock_s3.generate_presigned_url.assert_called_once()
        call_args = mock_s3.generate_presigned_url.call_args
        self.assertEqual(call_args[0][0], "get_object")
        self.assertEqual(call_args[1]["Params"]["Bucket"], "test-bucket")
        self.assertEqual(call_args[1]["Params"]["Key"], "uploads/test/file.pdf")

    @patch("boto3.client")
    def test_generate_download_url_success(self, mock_boto_client):
        """Test successful download URL generation."""
        # Arrange
        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url.return_value = "https://s3.amazonaws.com/download-url"
        mock_boto_client.return_value = mock_s3

        service = S3FileUploadService()

        # Act
        result = service.generate_download_url("uploads/test/file.pdf", "document.pdf")

        # Assert
        self.assertEqual(result, "https://s3.amazonaws.com/download-url")
        mock_s3.generate_presigned_url.assert_called_once()
        call_args = mock_s3.generate_presigned_url.call_args
        self.assertEqual(call_args[0][0], "get_object")
        params = call_args[1]["Params"]
        self.assertEqual(params["Bucket"], "test-bucket")
        self.assertEqual(params["Key"], "uploads/test/file.pdf")
        self.assertIn("ResponseContentDisposition", params)
        self.assertIn("attachment", params["ResponseContentDisposition"])
        self.assertIn("document.pdf", params["ResponseContentDisposition"])

    @patch("boto3.client")
    def test_generate_presigned_get_url_failure(self, mock_boto_client):
        """Test presigned GET URL generation failure."""
        # Arrange
        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url.side_effect = ClientError(
            {"Error": {"Code": "TestError", "Message": "Test error"}},
            "generate_presigned_url",
        )
        mock_boto_client.return_value = mock_s3

        service = S3FileUploadService()

        # Act & Assert
        with self.assertRaises(Exception):
            service.generate_view_url("uploads/test/file.pdf")

    def test_generate_permanent_path(self):
        """Test permanent path generation."""
        # Act
        result = self.service.generate_permanent_path(
            purpose="job_description",
            object_id=42,
            file_name="test.pdf",
        )

        # Assert
        self.assertEqual(result, "uploads/job_description/42/test.pdf")
