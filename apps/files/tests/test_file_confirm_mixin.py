"""Tests for FileConfirmSerializerMixin."""

import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import models
from django.test import TestCase
from rest_framework import serializers

from apps.files.constants import CACHE_KEY_PREFIX
from apps.files.models import FileModel
from libs import FileConfirmSerializerMixin

User = get_user_model()


class DummyModel(models.Model):
    """Dummy model for testing."""

    title = models.CharField(max_length=255)

    class Meta:
        app_label = "files"
        # Use managed=False to avoid creating this table in the database
        managed = False


class DummySerializer(FileConfirmSerializerMixin, serializers.ModelSerializer):
    """Dummy serializer for testing the mixin.

    Note: files field is automatically added by FileConfirmSerializerMixin.
    """

    title = serializers.CharField()

    class Meta:
        model = DummyModel
        fields = ["title"]

    def create(self, validated_data):
        """Create a dummy instance without saving to database."""
        # Create instance without saving to avoid database table requirement
        instance = DummyModel(**validated_data)
        instance.pk = 1
        instance.id = 1
        # Mark as saved to avoid Django thinking it needs to be saved
        instance._state.adding = False
        return instance

    def update(self, instance, validated_data):
        """Update instance without saving to database."""
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
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

    @patch("django.core.cache.cache.delete")
    @patch("django.core.cache.cache.get")
    @patch("apps.files.utils.S3FileUploadService")
    def test_mixin_confirms_files_on_save(self, mock_s3_service, mock_cache_get, mock_cache_delete):
        """Test that mixin confirms files when serializer is saved."""
        # Arrange: Mock cache to return file metadata
        cache_data = {}

        def cache_get_side_effect(key):
            return cache_data.get(key)

        def cache_delete_side_effect(key):
            if key in cache_data:
                del cache_data[key]

        # Pre-populate cache data
        cache_key_1 = f"{CACHE_KEY_PREFIX}{self.file_token_1}"
        cache_key_2 = f"{CACHE_KEY_PREFIX}{self.file_token_2}"
        cache_data[cache_key_1] = json.dumps(
            {
                "file_name": "mixin_test1.pdf",
                "file_type": "application/pdf",
                "purpose": "job_description",
                "file_path": "uploads/tmp/test-token-mixin-001/mixin_test1.pdf",
            }
        )
        cache_data[cache_key_2] = json.dumps(
            {
                "file_name": "mixin_test2.pdf",
                "file_type": "application/pdf",
                "purpose": "job_description",
                "file_path": "uploads/tmp/test-token-mixin-002/mixin_test2.pdf",
            }
        )

        mock_cache_get.side_effect = cache_get_side_effect
        mock_cache_delete.side_effect = cache_delete_side_effect

        # Arrange: Mock S3 service
        mock_instance = mock_s3_service.return_value
        mock_instance.check_file_exists.return_value = True
        mock_instance.generate_permanent_path.side_effect = [
            "uploads/job_description/1/mixin_test1.pdf",
            "uploads/job_description/1/mixin_test2.pdf",
        ]
        mock_instance.move_file.return_value = True
        mock_instance.get_file_metadata.return_value = {
            "size": 123456,
            "content_type": "application/pdf",
            "etag": "abc123",
        }

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
        """Test that mixin works when files dict is empty."""
        # Arrange & Act
        data = {"title": "Test", "files": {}}
        serializer = DummySerializer(data=data)
        self.assertTrue(serializer.is_valid())
        instance = serializer.save()

        # Assert: No files were created
        self.assertEqual(FileModel.objects.count(), 0)
        self.assertIsNotNone(instance)

    @patch("apps.files.utils.S3FileUploadService")
    def test_mixin_with_invalid_token(self, mock_s3_service_utils):
        """Test that mixin raises error for invalid token."""
        # Arrange & Act
        mock_s3 = MagicMock()
        mock_s3_service_utils.return_value = mock_s3

        data = {"title": "Test", "files": {"attachment": "invalid-token"}}
        serializer = DummySerializer(data=data)
        self.assertTrue(serializer.is_valid())

        # Assert: Save should raise ValidationError
        from rest_framework.exceptions import ValidationError

        with self.assertRaises(ValidationError) as context:
            serializer.save()

        # Check error message
        self.assertIn("files", context.exception.detail)

    @patch("apps.files.utils.S3FileUploadService")
    def test_mixin_with_file_not_in_s3(self, mock_s3_service):
        """Test that mixin raises error when file doesn't exist in S3."""
        # Arrange: Mock S3 service to return False
        mock_instance = mock_s3_service.return_value
        mock_instance.check_file_exists.return_value = False

        # Act
        data = {"title": "Test", "files": {"attachment": self.file_token_1}}
        serializer = DummySerializer(data=data)
        self.assertTrue(serializer.is_valid())

        # Assert: Save should raise ValidationError
        from rest_framework.exceptions import ValidationError

        with self.assertRaises(ValidationError) as context:
            serializer.save()

        # Check error message
        self.assertIn("files", context.exception.detail)

    @patch("apps.files.utils.S3FileUploadService")
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
        data = {"title": "Test", "files": {"attachment": self.file_token_1}}
        serializer = DummySerializer(data=data)
        self.assertTrue(serializer.is_valid())

        # Assert: Save should raise ValidationError
        from rest_framework.exceptions import ValidationError

        with self.assertRaises(ValidationError) as context:
            serializer.save()

        # Check error message
        self.assertIn("files", context.exception.detail)

        # Verify the file was deleted
        mock_instance.delete_file.assert_called_once()

    @patch("apps.files.models.FileModel.objects.create")
    @patch("django.contrib.contenttypes.models.ContentType.objects.get_for_model")
    @patch("django.core.cache.cache.delete")
    @patch("django.core.cache.cache.get")
    @patch("apps.files.utils.S3FileUploadService")
    def test_mixin_without_request_context(
        self, mock_s3_service, mock_cache_get, mock_cache_delete, mock_get_content_type, mock_file_create
    ):
        """Test that mixin works without request in context (uploaded_by is None)."""
        # Arrange: Mock ContentType to avoid FK constraint issues with DummyModel
        from django.contrib.contenttypes.models import ContentType

        # Use User's ContentType as a valid ContentType that exists in the test database
        user_content_type = ContentType.objects.get_for_model(User)
        mock_get_content_type.return_value = user_content_type

        # Mock FileModel.objects.create to return a mock file record
        from unittest.mock import MagicMock

        mock_file_record = MagicMock()
        mock_file_record.id = 1
        mock_file_record.uploaded_by = None
        mock_file_record.is_confirmed = True
        mock_file_create.return_value = mock_file_record

        # Arrange: Mock cache
        cache_data = {}

        def cache_get_side_effect(key):
            return cache_data.get(key)

        def cache_delete_side_effect(key):
            if key in cache_data:
                del cache_data[key]

        cache_key_1 = f"{CACHE_KEY_PREFIX}{self.file_token_1}"
        cache_data[cache_key_1] = json.dumps(
            {
                "file_name": "mixin_test1.pdf",
                "file_type": "application/pdf",
                "purpose": "job_description",
                "file_path": "uploads/tmp/test-token-mixin-001/mixin_test1.pdf",
            }
        )

        mock_cache_get.side_effect = cache_get_side_effect
        mock_cache_delete.side_effect = cache_delete_side_effect

        # Arrange: Mock S3 service
        mock_instance = mock_s3_service.return_value
        mock_instance.check_file_exists.return_value = True
        mock_instance.generate_permanent_path.return_value = "uploads/job_description/1/mixin_test1.pdf"
        mock_instance.move_file.return_value = True
        mock_instance.get_file_metadata.return_value = {
            "size": 123456,
            "content_type": "application/pdf",
            "etag": "abc123",
        }

        # Act: Create serializer without request context
        data = {"title": "Test", "files": {"attachment": self.file_token_1}}
        serializer = DummySerializer(data=data)
        self.assertTrue(serializer.is_valid())
        instance = serializer.save()

        # Assert: Check FileModel.objects.create was called without uploaded_by
        self.assertTrue(mock_file_create.called)
        call_kwargs = mock_file_create.call_args[1]
        self.assertIsNone(call_kwargs.get("uploaded_by"))
        self.assertTrue(call_kwargs.get("is_confirmed"))

    @patch("apps.files.utils.S3FileUploadService")
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
        data = {"title": "Test", "files": {"attachment1": self.file_token_1, "attachment2": self.file_token_2}}
        serializer = DummySerializer(data=data)
        self.assertTrue(serializer.is_valid())

        # Assert: Save should raise error and no files should be created
        from rest_framework.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            serializer.save()

        # No files should be created due to transaction rollback
        self.assertEqual(FileModel.objects.count(), 0)
