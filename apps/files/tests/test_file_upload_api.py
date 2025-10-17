"""Tests for file upload API endpoints."""

import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.files.constants import CACHE_KEY_PREFIX
from apps.files.models import FileModel

User = get_user_model()


class APITestMixin:
    """Mixin to handle wrapped API responses and data extraction."""

    def get_response_data(self, response):
        """Extract data from wrapped API response."""
        content = json.loads(response.content.decode())
        if "data" in content:
            return content["data"]
        return content


class PresignURLAPITest(TestCase, APITestMixin):
    """Test cases for presign URL generation endpoint."""

    def setUp(self):
        """Set up test data."""
        # Clear cache
        cache.clear()

        # Create test user
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    @patch("apps.files.api.views.file_views.S3FileUploadService")
    def test_presign_url_success(self, mock_s3_service):
        """Test successful presigned URL generation."""
        # Arrange: Mock S3 service
        mock_instance = mock_s3_service.return_value
        mock_instance.generate_presigned_url.return_value = {
            "upload_url": "https://s3.amazonaws.com/bucket/uploads/tmp/test-token/test.pdf?signature=abc",
            "file_path": "uploads/tmp/test-token/test.pdf",
            "file_token": "test-token",
        }

        # Act: Call presign endpoint
        url = reverse("files:presign")
        data = {
            "file_name": "test.pdf",
            "file_type": "application/pdf",
            "purpose": "job_description",
        }
        response = self.client.post(url, data, format="json")

        # Assert: Check response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)

        self.assertIn("upload_url", response_data)
        self.assertIn("file_path", response_data)
        self.assertIn("file_token", response_data)
        self.assertEqual(response_data["file_token"], "test-token")

        # Assert: Check cache was populated
        cache_key = f"{CACHE_KEY_PREFIX}test-token"
        cached_data = cache.get(cache_key)
        self.assertIsNotNone(cached_data)

        cached_obj = json.loads(cached_data)
        self.assertEqual(cached_obj["file_name"], "test.pdf")
        self.assertEqual(cached_obj["file_type"], "application/pdf")
        self.assertEqual(cached_obj["purpose"], "job_description")

    def test_presign_url_invalid_file_type(self):
        """Test presign URL with invalid file type for purpose."""
        # Arrange & Act
        url = reverse("files:presign")
        data = {
            "file_name": "test.exe",
            "file_type": "application/x-msdownload",  # Invalid for job_description
            "purpose": "job_description",
        }
        response = self.client.post(url, data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_presign_url_missing_fields(self):
        """Test presign URL with missing required fields."""
        # Arrange & Act
        url = reverse("files:presign")
        data = {
            "file_name": "test.pdf",
            # Missing file_type and purpose
        }
        response = self.client.post(url, data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_presign_url_unauthenticated(self):
        """Test presign URL without authentication."""
        # Arrange: Create unauthenticated client
        client = APIClient()

        # Act
        url = reverse("files:presign")
        data = {
            "file_name": "test.pdf",
            "file_type": "application/pdf",
            "purpose": "job_description",
        }
        response = client.post(url, data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ConfirmMultipleFilesAPITest(TestCase, APITestMixin):
    """Test cases for confirming multiple file uploads."""

    def setUp(self):
        """Set up test data."""
        # Clear cache and database
        cache.clear()
        FileModel.objects.all().delete()

        # Create test user
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Store test data in cache for multiple files
        self.file_token_1 = "test-token-001"
        self.file_token_2 = "test-token-002"

        cache_key_1 = f"{CACHE_KEY_PREFIX}{self.file_token_1}"
        cache_data_1 = {
            "file_name": "test1.pdf",
            "file_type": "application/pdf",
            "purpose": "job_description",
            "file_path": "uploads/tmp/test-token-001/test1.pdf",
        }
        cache.set(cache_key_1, json.dumps(cache_data_1), 3600)

        cache_key_2 = f"{CACHE_KEY_PREFIX}{self.file_token_2}"
        cache_data_2 = {
            "file_name": "test2.pdf",
            "file_type": "application/pdf",
            "purpose": "job_description",
            "file_path": "uploads/tmp/test-token-002/test2.pdf",
        }
        cache.set(cache_key_2, json.dumps(cache_data_2), 3600)

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    @patch("apps.files.api.views.file_views.S3FileUploadService")
    def test_confirm_multiple_files_success(self, mock_s3_service_views, mock_s3_service_utils):
        """Test successful confirmation of multiple files."""
        # Arrange: Mock S3 service in views
        mock_instance = mock_s3_service_views.return_value
        mock_instance.check_file_exists.return_value = True
        mock_instance.generate_permanent_path.side_effect = [
            "uploads/job_description/1/test1.pdf",
            "uploads/job_description/1/test2.pdf",
        ]
        mock_instance.move_file.return_value = True

        # Mock get_file_metadata calls (2 for validation + 2 for permanent)
        mock_instance.get_file_metadata.side_effect = [
            {"size": 123456, "content_type": "application/pdf", "etag": "abc123"},
            {"size": 234567, "content_type": "application/pdf", "etag": "def456"},
            {"size": 123456, "etag": "abc123"},
            {"size": 234567, "etag": "def456"},
        ]

        # Mock S3 service in utils (for properties in serializer)
        mock_utils_instance = mock_s3_service_utils.return_value
        mock_utils_instance.generate_view_url.return_value = "https://s3.amazonaws.com/view-url"
        mock_utils_instance.generate_download_url.return_value = "https://s3.amazonaws.com/download-url"

        # Act: Call confirm endpoint
        url = reverse("files:confirm")
        data = {
            "files": [
                {
                    "file_token": self.file_token_1,
                    "purpose": "job_description",
                    "related_model": "core.User",
                    "related_object_id": self.user.id,
                },
                {
                    "file_token": self.file_token_2,
                    "purpose": "job_description",
                    "related_model": "core.User",
                    "related_object_id": self.user.id,
                },
            ]
        }
        response = self.client.post(url, data, format="json")

        # Assert: Check response
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)

        self.assertIn("confirmed_files", response_data)
        self.assertEqual(len(response_data["confirmed_files"]), 2)

        # Check first file
        file1 = response_data["confirmed_files"][0]
        self.assertEqual(file1["file_name"], "test1.pdf")
        self.assertEqual(file1["purpose"], "job_description")
        self.assertTrue(file1["is_confirmed"])
        self.assertEqual(file1["size"], 123456)

        # Check second file
        file2 = response_data["confirmed_files"][1]
        self.assertEqual(file2["file_name"], "test2.pdf")
        self.assertEqual(file2["purpose"], "job_description")
        self.assertTrue(file2["is_confirmed"])
        self.assertEqual(file2["size"], 234567)

        # Assert: Check FileModel records were created
        self.assertEqual(FileModel.objects.count(), 2)
        file_records = FileModel.objects.filter(object_id=self.user.id).order_by("id")

        self.assertEqual(file_records[0].file_name, "test1.pdf")
        self.assertEqual(file_records[0].uploaded_by, self.user)
        self.assertEqual(file_records[1].file_name, "test2.pdf")
        self.assertEqual(file_records[1].uploaded_by, self.user)

        # Assert: Check S3 service was called correctly
        self.assertEqual(mock_instance.check_file_exists.call_count, 2)
        self.assertEqual(mock_instance.move_file.call_count, 2)

        # Assert: Check cache was cleared
        cache_key_1 = f"{CACHE_KEY_PREFIX}{self.file_token_1}"
        cache_key_2 = f"{CACHE_KEY_PREFIX}{self.file_token_2}"
        self.assertIsNone(cache.get(cache_key_1))
        self.assertIsNone(cache.get(cache_key_2))

    @patch("apps.files.api.views.file_views.S3FileUploadService")
    def test_confirm_multiple_files_invalid_token(self, mock_s3_service_utils):
        mock_s3 = MagicMock()
        mock_s3_service_utils.return_value = mock_s3
        """Test confirm multiple files with one invalid token."""
        # Arrange & Act
        url = reverse("files:confirm")
        data = {
            "files": [
                {
                    "file_token": self.file_token_1,
                    "purpose": "avatar",
                    "related_model": "core.User",
                    "related_object_id": self.user.id,
                },
                {
                    "file_token": "invalid-token",
                    "purpose": "avatar",
                    "related_model": "core.User",
                    "related_object_id": self.user.id,
                },
            ]
        }
        response = self.client.post(url, data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        content = json.loads(response.content.decode())
        self.assertFalse(content.get("success"))
        error_data = content.get("error", {})
        # Check for validation or application error
        self.assertTrue("detail" in error_data or "type" in error_data or len(error_data) > 0)

    @patch("apps.files.api.views.file_views.S3FileUploadService")
    def test_confirm_multiple_files_one_not_in_s3(self, mock_s3_service):
        """Test confirm multiple files when one doesn't exist in S3."""
        # Arrange: Mock S3 service - first file exists, second doesn't
        mock_instance = mock_s3_service.return_value
        mock_instance.check_file_exists.side_effect = [True, False]
        mock_instance.get_file_metadata.return_value = {
            "size": 123456,
            "content_type": "application/pdf",
            "etag": "abc123",
        }

        # Act
        url = reverse("files:confirm")
        data = {
            "files": [
                {
                    "file_token": self.file_token_1,
                    "purpose": "avatar",
                    "related_model": "core.User",
                    "related_object_id": self.user.id,
                },
                {
                    "file_token": self.file_token_2,
                    "purpose": "avatar",
                    "related_model": "core.User",
                    "related_object_id": self.user.id,
                },
            ]
        }
        response = self.client.post(url, data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        content = json.loads(response.content.decode())
        self.assertFalse(content.get("success"))
        self.assertIn("detail", content.get("error", {}))

        # Verify no files were created (transaction rolled back)
        self.assertEqual(FileModel.objects.count(), 0)

    def test_confirm_multiple_files_invalid_related_object(self):
        """Test confirm multiple files with invalid related object."""
        # Arrange & Act
        url = reverse("files:confirm")
        data = {
            "files": [
                {
                    "file_token": self.file_token_1,
                    "purpose": "avatar",
                    "related_model": "core.User",
                    "related_object_id": 99999,
                },
                {
                    "file_token": self.file_token_2,
                    "purpose": "avatar",
                    "related_model": "core.User",
                    "related_object_id": 99999,
                },
            ]
        }
        response = self.client.post(url, data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirm_multiple_files_empty_list(self):
        """Test confirm multiple files with empty files list."""
        # Arrange & Act
        url = reverse("files:confirm")
        data = {"files": []}
        response = self.client.post(url, data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirm_multiple_files_unauthenticated(self):
        """Test confirm multiple files without authentication."""
        # Arrange: Create unauthenticated client
        client = APIClient()

        # Act
        url = reverse("files:confirm")
        data = {
            "files": [
                {
                    "file_token": self.file_token_1,
                    "purpose": "avatar",
                    "related_model": "core.User",
                    "related_object_id": self.user.id,
                },
                {
                    "file_token": self.file_token_2,
                    "purpose": "avatar",
                    "related_model": "core.User",
                    "related_object_id": self.user.id,
                },
            ]
        }
        response = client.post(url, data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class FileModelTest(TestCase):
    """Test cases for FileModel."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    def test_create_file_model(self):
        """Test creating a FileModel instance."""
        # Arrange & Act
        file_record = FileModel.objects.create(
            purpose="test_purpose",
            file_name="test.pdf",
            file_path="uploads/test/1/test.pdf",
            size=123456,
            checksum="abc123",
            is_confirmed=True,
            object_id=self.user.id,
        )

        # Assert
        self.assertEqual(file_record.purpose, "test_purpose")
        self.assertEqual(file_record.file_name, "test.pdf")
        self.assertTrue(file_record.is_confirmed)
        self.assertEqual(file_record.size, 123456)

    def test_file_model_str_representation(self):
        """Test string representation of FileModel."""
        # Arrange & Act
        file_record = FileModel.objects.create(
            purpose="test_purpose",
            file_name="test.pdf",
            file_path="uploads/test/1/test.pdf",
        )

        # Assert
        self.assertEqual(str(file_record), "test_purpose - test.pdf")

    def test_file_model_ordering(self):
        """Test FileModel default ordering."""
        # Arrange: Create multiple files
        file1 = FileModel.objects.create(
            purpose="purpose1",
            file_name="file1.pdf",
            file_path="uploads/test/1/file1.pdf",
        )
        file2 = FileModel.objects.create(
            purpose="purpose2",
            file_name="file2.pdf",
            file_path="uploads/test/2/file2.pdf",
        )

        # Act: Retrieve files (should be ordered by -created_at)
        files = list(FileModel.objects.all())

        # Assert: Latest file should come first
        self.assertEqual(files[0].id, file2.id)
        self.assertEqual(files[1].id, file1.id)

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_view_url_property(self, mock_s3_service):
        """Test view_url property generates presigned URL."""
        # Arrange
        mock_instance = mock_s3_service.return_value
        mock_instance.generate_view_url.return_value = "https://s3.amazonaws.com/view-url"

        file_record = FileModel.objects.create(
            purpose="test_purpose",
            file_name="test.pdf",
            file_path="uploads/test/1/test.pdf",
        )

        # Act
        url = file_record.view_url

        # Assert
        self.assertEqual(url, "https://s3.amazonaws.com/view-url")
        mock_instance.generate_view_url.assert_called_once_with("uploads/test/1/test.pdf")

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_download_url_property(self, mock_s3_service):
        """Test download_url property generates presigned download URL."""
        # Arrange
        mock_instance = mock_s3_service.return_value
        mock_instance.generate_download_url.return_value = "https://s3.amazonaws.com/download-url"

        file_record = FileModel.objects.create(
            purpose="test_purpose",
            file_name="test.pdf",
            file_path="uploads/test/1/test.pdf",
        )

        # Act
        url = file_record.download_url

        # Assert
        self.assertEqual(url, "https://s3.amazonaws.com/download-url")
        mock_instance.generate_download_url.assert_called_once_with("uploads/test/1/test.pdf", "test.pdf")
