"""Tests for FileConfirmSerializerMixin required fields support."""

from django.db import models
from django.test import TestCase
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.files.api.serializers.mixins import FileConfirmSerializerMixin


class FileConfirmRequiredTest(TestCase):
    """Test cases for FileConfirmSerializerMixin required fields."""

    def test_required_fields_explicit(self):
        """Test that explicit file_required_fields are enforced."""

        class TestSerializer(FileConfirmSerializerMixin, serializers.Serializer):
            file_confirm_fields = ["attachment", "document"]
            file_required_fields = ["attachment"]

            def create(self, validated_data):
                return validated_data

        # 1. Missing 'files' field entirely
        serializer = TestSerializer(data={})
        with self.assertRaises(ValidationError) as cm:
            serializer.is_valid(raise_exception=True)
        self.assertIn("files", cm.exception.detail)
        self.assertEqual(cm.exception.detail["files"][0].code, "required")

        # 2. 'files' field present but missing required nested field
        serializer = TestSerializer(data={"files": {"document": "token_123"}})
        with self.assertRaises(ValidationError) as cm:
            serializer.is_valid(raise_exception=True)
        self.assertIn("files", cm.exception.detail)
        self.assertIn("attachment", cm.exception.detail["files"])
        self.assertEqual(cm.exception.detail["files"]["attachment"][0].code, "required")

        # 3. All required fields present
        serializer = TestSerializer(data={"files": {"attachment": "token_123"}})
        self.assertTrue(serializer.is_valid())

    def test_required_multi_valued_fields(self):
        """Test that multi-valued fields can also be required."""

        class TestSerializer(FileConfirmSerializerMixin, serializers.Serializer):
            file_confirm_fields = ["attachments"]
            file_multi_valued_fields = ["attachments"]
            file_required_fields = ["attachments"]

            def create(self, validated_data):
                return validated_data

        # 1. Missing required multi-valued field
        serializer = TestSerializer(data={"files": {}})
        with self.assertRaises(ValidationError) as cm:
            serializer.is_valid(raise_exception=True)
        self.assertIn("attachments", cm.exception.detail["files"])

        # 2. Present but empty list (should fail if required)
        serializer = TestSerializer(data={"files": {"attachments": []}})
        with self.assertRaises(ValidationError) as cm:
            serializer.is_valid(raise_exception=True)
        self.assertIn("attachments", cm.exception.detail["files"])

        # 3. Present and not empty
        serializer = TestSerializer(data={"files": {"attachments": ["token_1"]}})
        self.assertTrue(serializer.is_valid())

    def test_auto_detection_required(self):
        """Test that required status is auto-detected from model fields."""

        class TestFileConfirmRequiredDummyModel(models.Model):
            # We use a mock model or a real one if needed, but since we are testing mixin logic:
            attachment = models.CharField(max_length=100, blank=False)
            document = models.CharField(max_length=100, blank=True)

            class Meta:
                app_label = "files"

        class TestSerializer(FileConfirmSerializerMixin, serializers.ModelSerializer):
            class Meta:
                model = TestFileConfirmRequiredDummyModel
                fields = ["attachment", "document"]

        # Instantiate to trigger get_fields
        serializer = TestSerializer()
        fields = serializer.fields
        self.assertIn("files", fields)
        files_field = fields["files"]

        # Check nested fields requirements
        nested_fields = files_field.fields
        self.assertTrue(nested_fields["attachment"].required)
        self.assertFalse(nested_fields["document"].required)

        # Main files field should be required because attachment is required
        self.assertTrue(files_field.required)
