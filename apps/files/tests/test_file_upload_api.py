"""Tests for file upload API endpoints."""

import json
from unittest.mock import patch

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
            "file_size": 123456,
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
        self.assertEqual(cached_obj["file_size"], 123456)
        self.assertEqual(cached_obj["purpose"], "job_description")

    def test_presign_url_invalid_file_size(self):
        """Test presign URL with invalid file size."""
        # Arrange & Act
        url = reverse("files:presign")
        data = {
            "file_name": "test.pdf",
            "file_size": 0,  # Invalid: must be >= 1
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
            # Missing file_size and purpose
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
            "file_size": 123456,
            "purpose": "job_description",
        }
        response = client.post(url, data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ConfirmFileUploadAPITest(TestCase, APITestMixin):
    """Test cases for file upload confirmation endpoint."""

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

        # Store test data in cache
        self.file_token = "test-token-123"
        cache_key = f"{CACHE_KEY_PREFIX}{self.file_token}"
        cache_data = {
            "file_name": "test.pdf",
            "file_size": 123456,
            "purpose": "job_description",
            "file_path": "uploads/tmp/test-token-123/test.pdf",
        }
        cache.set(cache_key, json.dumps(cache_data), 3600)

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    @patch("apps.files.api.views.file_views.S3FileUploadService")
    def test_confirm_upload_success(self, mock_s3_service):
        """Test successful file upload confirmation."""
        # Arrange: Mock S3 service
        mock_instance = mock_s3_service.return_value
        mock_instance.check_file_exists.return_value = True
        mock_instance.generate_permanent_path.return_value = "uploads/job_description/1/test.pdf"
        mock_instance.move_file.return_value = True
        mock_instance.get_file_metadata.return_value = {
            "size": 123456,
            "etag": "abc123def456",
        }

        # Act: Call confirm endpoint
        url = reverse("files:confirm")
        data = {
            "file_token": self.file_token,
            "related_model": "core.User",
            "related_object_id": self.user.id,
            "purpose": "job_description",
        }
        response = self.client.post(url, data, format="json")

        # Assert: Check response
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)

        self.assertIn("id", response_data)
        self.assertEqual(response_data["file_name"], "test.pdf")
        self.assertEqual(response_data["purpose"], "job_description")
        self.assertTrue(response_data["is_confirmed"])
        self.assertEqual(response_data["size"], 123456)

        # Assert: Check FileModel was created
        file_record = FileModel.objects.get(id=response_data["id"])
        self.assertEqual(file_record.file_name, "test.pdf")
        self.assertEqual(file_record.purpose, "job_description")
        self.assertTrue(file_record.is_confirmed)
        self.assertEqual(file_record.object_id, self.user.id)

        # Assert: Check S3 service was called correctly
        mock_instance.check_file_exists.assert_called_once_with("uploads/tmp/test-token-123/test.pdf")
        mock_instance.move_file.assert_called_once()

        # Assert: Check cache was cleared
        cache_key = f"{CACHE_KEY_PREFIX}{self.file_token}"
        self.assertIsNone(cache.get(cache_key))

    def test_confirm_upload_invalid_token(self):
        """Test confirm upload with invalid token."""
        # Arrange & Act
        url = reverse("files:confirm")
        data = {
            "file_token": "invalid-token",
            "related_model": "core.User",
            "related_object_id": self.user.id,
            "purpose": "job_description",
        }
        response = self.client.post(url, data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        content = json.loads(response.content.decode())
        # Check error is wrapped in envelope format
        self.assertFalse(content.get("success"))
        self.assertIn("detail", content.get("error", {}))

    @patch("apps.files.api.views.file_views.S3FileUploadService")
    def test_confirm_upload_file_not_found_in_s3(self, mock_s3_service):
        """Test confirm upload when file doesn't exist in S3."""
        # Arrange: Mock S3 service to return False for file existence check
        mock_instance = mock_s3_service.return_value
        mock_instance.check_file_exists.return_value = False

        # Act
        url = reverse("files:confirm")
        data = {
            "file_token": self.file_token,
            "related_model": "core.User",
            "related_object_id": self.user.id,
            "purpose": "job_description",
        }
        response = self.client.post(url, data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        content = json.loads(response.content.decode())
        # Check error is wrapped in envelope format
        self.assertFalse(content.get("success"))
        self.assertIn("detail", content.get("error", {}))

    def test_confirm_upload_invalid_related_model(self):
        """Test confirm upload with invalid related model."""
        # Arrange & Act
        url = reverse("files:confirm")
        data = {
            "file_token": self.file_token,
            "related_model": "invalid.Model",
            "related_object_id": 1,
            "purpose": "job_description",
        }
        response = self.client.post(url, data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirm_upload_related_object_not_found(self):
        """Test confirm upload when related object doesn't exist."""
        # Arrange & Act
        url = reverse("files:confirm")
        data = {
            "file_token": self.file_token,
            "related_model": "core.User",
            "related_object_id": 99999,  # Non-existent ID
            "purpose": "job_description",
        }
        response = self.client.post(url, data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirm_upload_unauthenticated(self):
        """Test confirm upload without authentication."""
        # Arrange: Create unauthenticated client
        client = APIClient()

        # Act
        url = reverse("files:confirm")
        data = {
            "file_token": self.file_token,
            "related_model": "core.User",
            "related_object_id": self.user.id,
            "purpose": "job_description",
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
