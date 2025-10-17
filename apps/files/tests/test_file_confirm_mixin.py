"""Tests for FileConfirmSerializerMixin."""

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework import serializers

from apps.files.constants import CACHE_KEY_PREFIX
from apps.files.models import FileModel
from libs import FileConfirmSerializerMixin

User = get_user_model()


class DummyModel:
    """Dummy model for testing."""

    def __init__(self, pk=1):
        self.pk = pk
        self.id = pk

    class Meta:
        pass


class DummySerializer(FileConfirmSerializerMixin, serializers.Serializer):
    """Dummy serializer for testing the mixin.

    Note: file_tokens field is automatically added by FileConfirmSerializerMixin.
    """

    title = serializers.CharField()

    def create(self, validated_data):
        """Create a dummy instance."""
        file_tokens = validated_data.pop("file_tokens", [])
        instance = DummyModel(pk=1)
        # Store tokens for testing
        self.validated_data["file_tokens"] = file_tokens
        return instance

    def update(self, instance, validated_data):
        """Update is not used in tests."""
        return instance


class FileConfirmSerializerMixinTest(TestCase):
    """Test cases for FileConfirmSerializerMixin."""

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

        # Store test data in cache
        self.file_token_1 = "test-token-mixin-001"
        self.file_token_2 = "test-token-mixin-002"

        cache_key_1 = f"{CACHE_KEY_PREFIX}{self.file_token_1}"
        cache_data_1 = {
            "file_name": "mixin_test1.pdf",
            "file_type": "application/pdf",
            "purpose": "job_description",
            "file_path": "uploads/tmp/test-token-mixin-001/mixin_test1.pdf",
        }
        cache.set(cache_key_1, json.dumps(cache_data_1), 3600)

        cache_key_2 = f"{CACHE_KEY_PREFIX}{self.file_token_2}"
        cache_data_2 = {
            "file_name": "mixin_test2.pdf",
            "file_type": "application/pdf",
            "purpose": "job_description",
            "file_path": "uploads/tmp/test-token-mixin-002/mixin_test2.pdf",
        }
        cache.set(cache_key_2, json.dumps(cache_data_2), 3600)

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    @patch("libs.serializers.mixins.S3FileUploadService")
    def test_mixin_confirms_files_on_save(self, mock_s3_service_mixin, mock_s3_service_utils):
        """Test that mixin confirms files when serializer is saved."""
        # Arrange: Mock S3 service
        mock_instance = mock_s3_service_mixin.return_value
        mock_instance.check_file_exists.return_value = True
        mock_instance.generate_permanent_path.side_effect = [
            "uploads/job_description/1/mixin_test1.pdf",
            "uploads/job_description/1/mixin_test2.pdf",
        ]
        mock_instance.move_file.return_value = True
        mock_instance.get_file_metadata.side_effect = [
            {"size": 123456, "content_type": "application/pdf", "etag": "abc123"},
            {"size": 123456, "etag": "abc123"},
            {"size": 234567, "content_type": "application/pdf", "etag": "def456"},
            {"size": 234567, "etag": "def456"},
        ]

        # Act: Create serializer with file tokens dict and save
        data = {"title": "Test", "files": {"attachment1": self.file_token_1, "attachment2": self.file_token_2}}
        serializer = DummySerializer(data=data, context={"request": type("obj", (object,), {"user": self.user})()})
        self.assertTrue(serializer.is_valid())
        instance = serializer.save()

        # Assert: Check FileModel records were created
        self.assertEqual(FileModel.objects.count(), 2)
        file_records = FileModel.objects.filter(object_id=instance.pk).order_by("id")

        self.assertEqual(file_records[0].file_name, "mixin_test1.pdf")
        self.assertEqual(file_records[0].purpose, "job_description")
        self.assertTrue(file_records[0].is_confirmed)
        self.assertEqual(file_records[0].uploaded_by, self.user)

        self.assertEqual(file_records[1].file_name, "mixin_test2.pdf")
        self.assertEqual(file_records[1].purpose, "job_description")
        self.assertTrue(file_records[1].is_confirmed)
        self.assertEqual(file_records[1].uploaded_by, self.user)

        # Assert: Check S3 service was called
        self.assertEqual(mock_instance.check_file_exists.call_count, 2)
        self.assertEqual(mock_instance.move_file.call_count, 2)

        # Assert: Check cache was cleared
        cache_key_1 = f"{CACHE_KEY_PREFIX}{self.file_token_1}"
        cache_key_2 = f"{CACHE_KEY_PREFIX}{self.file_token_2}"
        self.assertIsNone(cache.get(cache_key_1))
        self.assertIsNone(cache.get(cache_key_2))

    def test_mixin_without_file_tokens(self):
        """Test that mixin works when no file tokens are provided."""
        # Arrange & Act
        data = {"title": "Test"}
        serializer = DummySerializer(data=data)
        self.assertTrue(serializer.is_valid())
        instance = serializer.save()

        # Assert: No files were created
        self.assertEqual(FileModel.objects.count(), 0)
        self.assertIsNotNone(instance)

    def test_mixin_with_empty_file_tokens_list(self):
        """Test that mixin works when file tokens list is empty."""
        # Arrange & Act
        data = {"title": "Test", "file_tokens": []}
        serializer = DummySerializer(data=data)
        self.assertTrue(serializer.is_valid())
        instance = serializer.save()

        # Assert: No files were created
        self.assertEqual(FileModel.objects.count(), 0)
        self.assertIsNotNone(instance)

    def test_mixin_with_invalid_token(self):
        """Test that mixin raises error for invalid token."""
        # Arrange & Act
        data = {"title": "Test", "file_tokens": ["invalid-token"]}
        serializer = DummySerializer(data=data)
        self.assertTrue(serializer.is_valid())

        # Assert: Save should raise ValidationError
        from rest_framework.exceptions import ValidationError

        with self.assertRaises(ValidationError) as context:
            serializer.save()

        # Check error message
        self.assertIn("file_tokens", context.exception.detail)

    @patch("libs.serializers.mixins.S3FileUploadService")
    def test_mixin_with_file_not_in_s3(self, mock_s3_service):
        """Test that mixin raises error when file doesn't exist in S3."""
        # Arrange: Mock S3 service to return False
        mock_instance = mock_s3_service.return_value
        mock_instance.check_file_exists.return_value = False

        # Act
        data = {"title": "Test", "file_tokens": [self.file_token_1]}
        serializer = DummySerializer(data=data)
        self.assertTrue(serializer.is_valid())

        # Assert: Save should raise ValidationError
        from rest_framework.exceptions import ValidationError

        with self.assertRaises(ValidationError) as context:
            serializer.save()

        # Check error message
        self.assertIn("file_tokens", context.exception.detail)

    @patch("libs.serializers.mixins.S3FileUploadService")
    def test_mixin_with_content_type_mismatch(self, mock_s3_service):
        """Test that mixin raises error for content type mismatch."""
        # Arrange: Mock S3 service with wrong content type
        mock_instance = mock_s3_service.return_value
        mock_instance.check_file_exists.return_value = True
        mock_instance.get_file_metadata.return_value = {
            "size": 123456,
            "content_type": "application/x-msdownload",  # Wrong type!
            "etag": "abc123",
        }
        mock_instance.delete_file.return_value = True

        # Act
        data = {"title": "Test", "file_tokens": [self.file_token_1]}
        serializer = DummySerializer(data=data)
        self.assertTrue(serializer.is_valid())

        # Assert: Save should raise ValidationError
        from rest_framework.exceptions import ValidationError

        with self.assertRaises(ValidationError) as context:
            serializer.save()

        # Check error message
        self.assertIn("file_tokens", context.exception.detail)

        # Verify the file was deleted
        mock_instance.delete_file.assert_called_once()

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    @patch("libs.serializers.mixins.S3FileUploadService")
    def test_mixin_without_request_context(self, mock_s3_service_mixin, mock_s3_service_utils):
        """Test that mixin works without request in context (uploaded_by is None)."""
        # Arrange: Mock S3 service
        mock_instance = mock_s3_service_mixin.return_value
        mock_instance.check_file_exists.return_value = True
        mock_instance.generate_permanent_path.return_value = "uploads/job_description/1/mixin_test1.pdf"
        mock_instance.move_file.return_value = True
        mock_instance.get_file_metadata.side_effect = [
            {"size": 123456, "content_type": "application/pdf", "etag": "abc123"},
            {"size": 123456, "etag": "abc123"},
        ]

        # Act: Create serializer without request context
        data = {"title": "Test", "file_tokens": [self.file_token_1]}
        serializer = DummySerializer(data=data)
        self.assertTrue(serializer.is_valid())
        instance = serializer.save()

        # Assert: Check FileModel was created without uploaded_by
        self.assertEqual(FileModel.objects.count(), 1)
        file_record = FileModel.objects.get(object_id=instance.pk)
        self.assertIsNone(file_record.uploaded_by)
        self.assertTrue(file_record.is_confirmed)

    @patch("libs.serializers.mixins.S3FileUploadService")
    def test_mixin_transaction_rollback_on_error(self, mock_s3_service):
        """Test that files are not created if save fails (transaction rollback)."""
        # Arrange: Mock S3 service - first file OK, second fails
        mock_instance = mock_s3_service.return_value
        mock_instance.check_file_exists.side_effect = [True, False]
        mock_instance.get_file_metadata.return_value = {
            "size": 123456,
            "content_type": "application/pdf",
            "etag": "abc123",
        }

        # Act
        data = {"title": "Test", "file_tokens": [self.file_token_1, self.file_token_2]}
        serializer = DummySerializer(data=data)
        self.assertTrue(serializer.is_valid())

        # Assert: Save should raise error and no files should be created
        from rest_framework.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            serializer.save()

        # No files should be created due to transaction rollback
        self.assertEqual(FileModel.objects.count(), 0)
