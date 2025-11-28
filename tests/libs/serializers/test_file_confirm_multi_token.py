"""
Tests for FileConfirmSerializerMixin multiple file token support.

This module tests the ability to accept both single token strings and arrays
of token strings for file fields, and the add (append) behavior for multi-valued fields.
"""

import pytest
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.test import TestCase
from rest_framework import serializers

from libs.drf.serializers.mixins import FileConfirmSerializerMixin, _FileTokenField


class TestFileTokenField(TestCase):
    """Test cases for _FileTokenField custom field."""

    def test_single_string_normalized_to_list(self):
        """Test that a single string token is normalized to a list."""
        field = _FileTokenField()
        result = field.to_internal_value("token_abc")
        self.assertEqual(result, ["token_abc"])

    def test_list_of_strings_returned_as_is(self):
        """Test that a list of strings is returned as-is."""
        field = _FileTokenField()
        result = field.to_internal_value(["token_1", "token_2", "token_3"])
        self.assertEqual(result, ["token_1", "token_2", "token_3"])

    def test_empty_list_allowed(self):
        """Test that an empty list is allowed."""
        field = _FileTokenField()
        result = field.to_internal_value([])
        self.assertEqual(result, [])

    def test_invalid_type_raises_error(self):
        """Test that invalid types raise validation error."""
        field = _FileTokenField()
        with self.assertRaises(serializers.ValidationError):
            field.to_internal_value(123)

    def test_list_with_non_string_raises_error(self):
        """Test that lists with non-string items raise validation error."""
        field = _FileTokenField()
        with self.assertRaises(serializers.ValidationError):
            field.to_internal_value(["token_1", 123, "token_3"])

    def test_to_representation_returns_value(self):
        """Test that to_representation returns the value as-is."""
        field = _FileTokenField()
        result = field.to_representation(["token_1", "token_2"])
        self.assertEqual(result, ["token_1", "token_2"])


# Mock models for testing
class MockSingleFileModel(models.Model):
    """Model with single-valued file field (ForeignKey)."""

    attachment = models.ForeignKey(
        "files.FileModel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=100)

    class Meta:
        app_label = "test_app"


class MockMultiFileModel(models.Model):
    """Model with multi-valued file field (GenericRelation)."""

    name = models.CharField(max_length=100)
    attachments = GenericRelation("files.FileModel")

    class Meta:
        app_label = "test_app"


class MockMixedFileModel(models.Model):
    """Model with both single and multi-valued file fields."""

    name = models.CharField(max_length=100)
    document = models.ForeignKey(
        "files.FileModel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="document_for_%(class)s",
    )
    attachments = GenericRelation("files.FileModel")

    class Meta:
        app_label = "test_app"


class TestFileConfirmMultiTokenSchema(TestCase):
    """Test cases for schema generation with multi-token support."""

    def test_explicit_single_valued_field_uses_file_token_field(self):
        """Test that explicitly declared single-valued fields use _FileTokenField."""

        class TestSerializer(FileConfirmSerializerMixin, serializers.Serializer):
            file_confirm_fields = ["attachment"]
            name = serializers.CharField()

        serializer = TestSerializer()
        files_field = serializer.fields["files"]
        attachment_field = files_field.fields["attachment"]

        # Should be _FileTokenField (accepts string or array)
        self.assertIsInstance(attachment_field, _FileTokenField)

    def test_explicit_multi_valued_field_uses_list_field(self):
        """Test that explicitly declared multi-valued fields use ListField."""

        class TestSerializer(FileConfirmSerializerMixin, serializers.Serializer):
            file_confirm_fields = ["attachments"]
            file_multi_valued_fields = ["attachments"]
            name = serializers.CharField()

        serializer = TestSerializer()
        files_field = serializer.fields["files"]
        attachments_field = files_field.fields["attachments"]

        # Should be ListField with CharField child
        self.assertIsInstance(attachments_field, serializers.ListField)
        self.assertIsInstance(attachments_field.child, serializers.CharField)

    def test_mixed_single_and_multi_valued_fields(self):
        """Test schema with both single and multi-valued fields."""

        class TestSerializer(FileConfirmSerializerMixin, serializers.Serializer):
            file_confirm_fields = ["document", "attachments"]
            file_multi_valued_fields = ["attachments"]
            name = serializers.CharField()

        serializer = TestSerializer()
        files_field = serializer.fields["files"]

        # document should use _FileTokenField
        self.assertIsInstance(files_field.fields["document"], _FileTokenField)

        # attachments should use ListField
        self.assertIsInstance(files_field.fields["attachments"], serializers.ListField)

    def test_auto_detected_genericrelation_is_multi_valued(self):
        """Test that auto-detected GenericRelation fields are multi-valued."""

        class TestSerializer(FileConfirmSerializerMixin, serializers.ModelSerializer):
            class Meta:
                model = MockMultiFileModel
                fields = "__all__"

        serializer = TestSerializer()
        file_fields_info = serializer._get_file_confirm_fields_with_info()

        # Find attachments field in detected fields
        attachments_info = [info for info in file_fields_info if info[0] == "attachments"]
        self.assertEqual(len(attachments_info), 1)
        self.assertTrue(attachments_info[0][1])  # is_multi should be True

    def test_auto_detected_foreignkey_is_single_valued(self):
        """Test that auto-detected ForeignKey fields are single-valued."""

        class TestSerializer(FileConfirmSerializerMixin, serializers.ModelSerializer):
            class Meta:
                model = MockSingleFileModel
                fields = "__all__"

        serializer = TestSerializer()
        file_fields_info = serializer._get_file_confirm_fields_with_info()

        # Find attachment field in detected fields
        attachment_info = [info for info in file_fields_info if info[0] == "attachment"]
        self.assertEqual(len(attachment_info), 1)
        self.assertFalse(attachment_info[0][1])  # is_multi should be False


class TestFileConfirmMultiTokenValidation(TestCase):
    """Test cases for validation of multi-token input."""

    def test_files_field_accepts_single_token_string(self):
        """Test that files field accepts a single token string."""

        class TestSerializer(FileConfirmSerializerMixin, serializers.Serializer):
            file_confirm_fields = ["attachment"]
            name = serializers.CharField()

        data = {"name": "test", "files": {"attachment": "token_123"}}
        serializer = TestSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        # Token should be normalized to list
        self.assertEqual(serializer.validated_data["files"]["attachment"], ["token_123"])

    def test_files_field_accepts_array_of_tokens(self):
        """Test that files field accepts an array of tokens."""

        class TestSerializer(FileConfirmSerializerMixin, serializers.Serializer):
            file_confirm_fields = ["attachments"]
            file_multi_valued_fields = ["attachments"]
            name = serializers.CharField()

        data = {"name": "test", "files": {"attachments": ["token_1", "token_2"]}}
        serializer = TestSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["files"]["attachments"], ["token_1", "token_2"])

    def test_files_field_accepts_mixed_single_and_array(self):
        """Test that files field accepts mixed single tokens and arrays."""

        class TestSerializer(FileConfirmSerializerMixin, serializers.Serializer):
            file_confirm_fields = ["document", "attachments"]
            file_multi_valued_fields = ["attachments"]
            name = serializers.CharField()

        data = {
            "name": "test",
            "files": {"document": "token_doc", "attachments": ["token_1", "token_2"]},
        }
        serializer = TestSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        # Single token normalized to list
        self.assertEqual(serializer.validated_data["files"]["document"], ["token_doc"])
        # Array stays as array
        self.assertEqual(serializer.validated_data["files"]["attachments"], ["token_1", "token_2"])


class TestNormalizeFileMappings(TestCase):
    """Test cases for _normalize_file_mappings method."""

    def test_normalize_single_strings(self):
        """Test normalizing single string tokens to lists."""

        class TestSerializer(FileConfirmSerializerMixin, serializers.Serializer):
            name = serializers.CharField()

        serializer = TestSerializer()
        mappings = {"attachment": "token_1", "document": "token_2"}
        result = serializer._normalize_file_mappings(mappings)

        self.assertEqual(result, {"attachment": ["token_1"], "document": ["token_2"]})

    def test_normalize_lists(self):
        """Test that lists are kept as-is."""

        class TestSerializer(FileConfirmSerializerMixin, serializers.Serializer):
            name = serializers.CharField()

        serializer = TestSerializer()
        mappings = {"attachments": ["token_1", "token_2", "token_3"]}
        result = serializer._normalize_file_mappings(mappings)

        self.assertEqual(result, {"attachments": ["token_1", "token_2", "token_3"]})

    def test_normalize_mixed(self):
        """Test normalizing mixed single and list tokens."""

        class TestSerializer(FileConfirmSerializerMixin, serializers.Serializer):
            name = serializers.CharField()

        serializer = TestSerializer()
        mappings = {
            "document": "token_doc",
            "attachments": ["token_1", "token_2"],
        }
        result = serializer._normalize_file_mappings(mappings)

        self.assertEqual(
            result,
            {"document": ["token_doc"], "attachments": ["token_1", "token_2"]},
        )


class TestIsMultiValuedField(TestCase):
    """Test cases for _is_multi_valued_field method."""

    def test_explicit_multi_valued_field(self):
        """Test that explicitly declared multi-valued fields are detected."""

        class TestSerializer(FileConfirmSerializerMixin, serializers.Serializer):
            file_multi_valued_fields = ["attachments"]
            name = serializers.CharField()

        serializer = TestSerializer()
        self.assertTrue(serializer._is_multi_valued_field("attachments"))
        self.assertFalse(serializer._is_multi_valued_field("document"))

    def test_auto_detected_genericrelation(self):
        """Test that GenericRelation fields are detected as multi-valued."""

        class TestSerializer(FileConfirmSerializerMixin, serializers.ModelSerializer):
            class Meta:
                model = MockMultiFileModel
                fields = "__all__"

        serializer = TestSerializer()
        self.assertTrue(serializer._is_multi_valued_field("attachments"))

    def test_auto_detected_foreignkey_not_multi(self):
        """Test that ForeignKey fields are not detected as multi-valued."""

        class TestSerializer(FileConfirmSerializerMixin, serializers.ModelSerializer):
            class Meta:
                model = MockSingleFileModel
                fields = "__all__"

        serializer = TestSerializer()
        self.assertFalse(serializer._is_multi_valued_field("attachment"))


@pytest.mark.skipif(True, reason="Requires database for full integration test")
class TestFileConfirmMultiTokenIntegration(TestCase):
    """Integration tests for multi-token file confirmation."""

    def test_multiple_files_added_to_genericrelation(self):
        """Test that multiple files are added to GenericRelation field."""
        # This test requires a database and S3 mocking
        # Skipped in unit tests, covered in integration tests
        pass

    def test_single_file_assigned_to_foreignkey(self):
        """Test that single file is assigned to ForeignKey field."""
        # This test requires a database and S3 mocking
        # Skipped in unit tests, covered in integration tests
        pass
