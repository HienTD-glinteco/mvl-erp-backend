"""Tests for FileConfirmSerializerMixin schema functionality.

This test module validates that the FileConfirmSerializerMixin properly injects
a 'files' field into serializer schemas with enhanced OpenAPI documentation support.
"""

import pytest
from django.apps import apps
from rest_framework import serializers

from apps.files.api.serializers.mixins import FileConfirmSerializerMixin


class TestFileConfirmSerializerMixinSchema:
    """Test cases for FileConfirmSerializerMixin schema generation."""

    def test_mixin_injects_files_field_with_explicit_fields(self):
        """Test that mixin injects a structured 'files' field when file_confirm_fields is provided."""

        class DummySerializer(FileConfirmSerializerMixin, serializers.Serializer):
            """Test serializer with explicit file fields."""

            file_confirm_fields = ["attachment", "document"]
            title = serializers.CharField()

        # Create serializer instance
        serializer = DummySerializer()

        # Assert 'files' field was injected
        assert "files" in serializer.fields
        assert serializer.fields["files"].write_only is True
        assert serializer.fields["files"].required is False

    def test_mixin_injects_generic_dict_without_file_fields(self):
        """Test that mixin falls back to generic dict field when no file_confirm_fields provided."""

        class DummySerializer(FileConfirmSerializerMixin, serializers.Serializer):
            """Test serializer without file fields."""

            title = serializers.CharField()

        # Create serializer instance
        serializer = DummySerializer()

        # Assert 'files' field was injected as generic DictField
        assert "files" in serializer.fields
        assert serializer.fields["files"].write_only is True
        assert serializer.fields["files"].required is False
        # Should be a DictField for backward compatibility
        assert isinstance(serializer.fields["files"], serializers.DictField)

    def test_mixin_with_explicit_file_confirm_fields(self):
        """Test that mixin uses explicit file_confirm_fields when provided."""

        class DummySerializer(FileConfirmSerializerMixin, serializers.Serializer):
            """Test serializer with explicit file fields."""

            file_confirm_fields = ["attachment", "document", "photo"]
            title = serializers.CharField()

        # Create serializer instance
        serializer = DummySerializer()

        # Assert 'files' field was injected with nested structure
        assert "files" in serializer.fields
        files_field = serializer.fields["files"]

        # The files field should be a serializer instance
        assert hasattr(files_field, "fields")

        # Check that the nested fields match file_confirm_fields
        nested_fields = files_field.fields
        assert "attachment" in nested_fields
        assert "document" in nested_fields
        assert "photo" in nested_fields
        assert len(nested_fields) == 3

    @pytest.mark.skipif(
        not apps.is_installed("apps.hrm"),
        reason="HRM app not installed",
    )
    def test_mixin_with_job_description_auto_detection(self):
        """Test that mixin detects ForeignKey file fields for JobDescription.

        Since JobDescription.attachment is now a ForeignKey to FileModel (not CharField),
        the enhanced auto-detection will find it and create a structured field.
        This test is skipped if the JobDescription model is not available.
        """
        try:
            JobDescription = apps.get_model("hrm", "JobDescription")
        except LookupError:
            pytest.skip("JobDescription model not found")

        class JobDescriptionSerializer(FileConfirmSerializerMixin, serializers.ModelSerializer):
            """Test serializer for JobDescription with auto-detection."""

            class Meta:
                model = JobDescription
                fields = "__all__"

        # Create serializer instance
        serializer = JobDescriptionSerializer()

        # Assert 'files' field was injected
        assert "files" in serializer.fields
        files_field = serializer.fields["files"]

        # Since attachment is a ForeignKey to FileModel, the enhanced auto-detection
        # will find it and create a structured field (not a generic DictField)
        assert hasattr(files_field, "fields")
        nested_fields = files_field.fields
        assert "attachment" in nested_fields

    @pytest.mark.skipif(
        not apps.is_installed("apps.hrm"),
        reason="HRM app not installed",
    )
    def test_mixin_with_job_description_explicit_fields(self):
        """Test that mixin uses explicit fields over auto-detection for JobDescription.

        This test is skipped if the JobDescription model is not available.
        """
        try:
            JobDescription = apps.get_model("hrm", "JobDescription")
        except LookupError:
            pytest.skip("JobDescription model not found")

        class JobDescriptionSerializer(FileConfirmSerializerMixin, serializers.ModelSerializer):
            """Test serializer with explicit file fields."""

            # Override auto-detection with explicit fields
            file_confirm_fields = ["attachment"]

            class Meta:
                model = JobDescription
                fields = "__all__"

        # Create serializer instance
        serializer = JobDescriptionSerializer()

        # Assert 'files' field was injected
        assert "files" in serializer.fields
        files_field = serializer.fields["files"]

        # Check nested fields
        nested_fields = files_field.fields
        assert "attachment" in nested_fields
        # Should only have the explicitly defined field
        assert len(nested_fields) == 1

    def test_mixin_with_empty_file_confirm_fields(self):
        """Test that mixin handles empty file_confirm_fields list."""

        class DummySerializer(FileConfirmSerializerMixin, serializers.Serializer):
            """Test serializer with empty file fields list."""

            file_confirm_fields = []
            title = serializers.CharField()

        # Create serializer instance
        serializer = DummySerializer()

        # Since file_confirm_fields is empty, should fall back to generic dict
        assert "files" in serializer.fields
        assert isinstance(serializer.fields["files"], serializers.DictField)

    def test_mixin_field_properties_with_schema(self):
        """Test that injected 'files' field has correct properties when using schema."""

        class DummySerializer(FileConfirmSerializerMixin, serializers.Serializer):
            """Test serializer for field properties."""

            file_confirm_fields = ["attachment"]
            title = serializers.CharField()

        # Create serializer instance
        serializer = DummySerializer()

        # Assert field properties
        files_field = serializer.fields["files"]
        assert files_field.write_only is True
        assert files_field.required is False
        # Check help text is present
        assert files_field.help_text is not None
