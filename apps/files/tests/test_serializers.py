"""Tests for file serializers."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.files.api.serializers import FileConfirmationSerializer

User = get_user_model()


class FileConfirmationSerializerTest(TestCase):
    """Test cases for FileConfirmationSerializer."""

    def test_validation_with_related_fields(self):
        """Test validation when both related_model and related_object_id are provided."""
        # Arrange: Create a user to use as related object
        # Changed to superuser to bypass RoleBasedPermission for API tests
        user = User.objects.create_superuser(username="testuser", email="test@example.com", password="testpass123")

        # Act: Validate serializer with related fields
        data = {
            "file_token": "test-token-123",
            "purpose": "test_purpose",
            "related_model": "core.User",
            "related_object_id": user.id,
        }
        serializer = FileConfirmationSerializer(data=data)

        # Assert
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["related_model"], "core.User")
        self.assertEqual(serializer.validated_data["related_object_id"], user.id)

    def test_validation_without_related_fields(self):
        """Test validation when related fields are not provided."""
        # Act: Validate serializer without related fields
        data = {
            "file_token": "test-token-123",
            "purpose": "import_data",
        }
        serializer = FileConfirmationSerializer(data=data)

        # Assert
        self.assertTrue(serializer.is_valid())
        self.assertIsNone(serializer.validated_data.get("related_model"))
        self.assertIsNone(serializer.validated_data.get("related_object_id"))

    def test_validation_with_only_related_model_fails(self):
        """Test validation fails when only related_model is provided."""
        # Act: Validate serializer with only related_model
        data = {
            "file_token": "test-token-123",
            "purpose": "test_purpose",
            "related_model": "core.User",
        }
        serializer = FileConfirmationSerializer(data=data)

        # Assert
        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)

    def test_validation_with_only_related_object_id_fails(self):
        """Test validation fails when only related_object_id is provided."""
        # Act: Validate serializer with only related_object_id
        data = {
            "file_token": "test-token-123",
            "purpose": "test_purpose",
            "related_object_id": 123,
        }
        serializer = FileConfirmationSerializer(data=data)

        # Assert
        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)

    def test_validation_with_invalid_model_label(self):
        """Test validation fails with invalid model label."""
        # Act: Validate serializer with invalid model
        data = {
            "file_token": "test-token-123",
            "purpose": "test_purpose",
            "related_model": "invalid.Model",
            "related_object_id": 123,
        }
        serializer = FileConfirmationSerializer(data=data)

        # Assert
        self.assertFalse(serializer.is_valid())
        self.assertIn("related_model", serializer.errors)

    def test_validation_with_nonexistent_object_id(self):
        """Test validation fails when related object doesn't exist."""
        # Act: Validate serializer with nonexistent object ID
        data = {
            "file_token": "test-token-123",
            "purpose": "test_purpose",
            "related_model": "core.User",
            "related_object_id": 999999,  # Doesn't exist
        }
        serializer = FileConfirmationSerializer(data=data)

        # Assert
        self.assertFalse(serializer.is_valid())
        self.assertIn("related_object_id", serializer.errors)

    def test_validation_with_null_related_fields(self):
        """Test validation when related fields are explicitly set to null."""
        # Act: Validate serializer with null related fields
        data = {
            "file_token": "test-token-123",
            "purpose": "import_data",
            "related_model": None,
            "related_object_id": None,
        }
        serializer = FileConfirmationSerializer(data=data)

        # Assert
        self.assertTrue(serializer.is_valid())
        self.assertIsNone(serializer.validated_data.get("related_model"))
        self.assertIsNone(serializer.validated_data.get("related_object_id"))
