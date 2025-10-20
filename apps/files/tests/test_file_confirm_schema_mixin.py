"""Tests for FileConfirmSchemaMixin.

This test module validates that the FileConfirmSchemaMixin properly injects
a 'files' field into serializer schemas for OpenAPI documentation purposes.
"""

import pytest
from django.apps import apps
from rest_framework import serializers

from libs import FileConfirmSchemaMixin


class TestFileConfirmSchemaMixin:
    """Test cases for FileConfirmSchemaMixin schema generation."""

    def test_mixin_injects_files_field(self):
        """Test that mixin injects a 'files' field into the serializer."""

        class DummySerializer(FileConfirmSchemaMixin, serializers.Serializer):
            """Test serializer with explicit file fields."""

            file_confirm_fields = ["attachment", "document"]
            title = serializers.CharField()

        # Create serializer instance
        serializer = DummySerializer()

        # Assert 'files' field was injected
        assert "files" in serializer.fields
        assert serializer.fields["files"].write_only is True
        assert serializer.fields["files"].required is False

    def test_mixin_does_not_overwrite_existing_files_field(self):
        """Test that mixin does not overwrite an existing 'files' field."""

        class DummySerializer(FileConfirmSchemaMixin, serializers.Serializer):
            """Test serializer with pre-existing files field."""

            file_confirm_fields = ["attachment"]
            title = serializers.CharField()
            files = serializers.CharField(required=True)

        # Create serializer instance
        serializer = DummySerializer()

        # Assert existing 'files' field was not overwritten
        assert "files" in serializer.fields
        # The field should remain as CharField (not the injected structure)
        assert isinstance(serializer.fields["files"], serializers.CharField)
        assert serializer.fields["files"].required is True

    def test_mixin_with_explicit_file_confirm_fields(self):
        """Test that mixin uses explicit file_confirm_fields when provided."""

        class DummySerializer(FileConfirmSchemaMixin, serializers.Serializer):
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

    def test_mixin_without_file_confirm_fields(self):
        """Test that mixin handles serializers without file_confirm_fields."""

        class DummySerializer(FileConfirmSchemaMixin, serializers.Serializer):
            """Test serializer without file fields."""

            title = serializers.CharField()

        # Create serializer instance
        serializer = DummySerializer()

        # Since no file_confirm_fields and no model, 'files' should not be injected
        assert "files" not in serializer.fields

    @pytest.mark.skipif(
        not apps.is_installed("apps.hrm"),
        reason="HRM app not installed",
    )
    def test_mixin_with_job_description_auto_detection(self):
        """Test that mixin auto-detects file fields from JobDescription model.

        This test is skipped if the JobDescription model is not available.
        """
        try:
            JobDescription = apps.get_model("hrm", "JobDescription")
        except LookupError:
            pytest.skip("JobDescription model not found")

        class JobDescriptionSerializer(FileConfirmSchemaMixin, serializers.ModelSerializer):
            """Test serializer for JobDescription with auto-detection."""

            class Meta:
                model = JobDescription
                fields = "__all__"

        # Create serializer instance
        serializer = JobDescriptionSerializer()

        # Assert 'files' field was injected
        assert "files" in serializer.fields
        files_field = serializer.fields["files"]

        # The files field should have nested fields
        assert hasattr(files_field, "fields")
        nested_fields = files_field.fields

        # JobDescription has an 'attachment' field - verify it was detected
        assert "attachment" in nested_fields
        assert isinstance(nested_fields["attachment"], serializers.CharField)

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

        class JobDescriptionSerializer(FileConfirmSchemaMixin, serializers.ModelSerializer):
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

        class DummySerializer(FileConfirmSchemaMixin, serializers.Serializer):
            """Test serializer with empty file fields list."""

            file_confirm_fields = []
            title = serializers.CharField()

        # Create serializer instance
        serializer = DummySerializer()

        # Since file_confirm_fields is empty, 'files' should not be injected
        assert "files" not in serializer.fields

    def test_mixin_field_properties(self):
        """Test that injected 'files' field has correct properties."""

        class DummySerializer(FileConfirmSchemaMixin, serializers.Serializer):
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
