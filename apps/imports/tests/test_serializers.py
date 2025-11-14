"""Tests for import serializers with focus on result_files schema."""

from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.files.models import FileModel
from apps.imports.api.serializers import (
    ImportJobSerializer,
    ResultFileInfoSerializer,
    ResultFilesSerializer,
)
from apps.imports.models import ImportJob

User = get_user_model()


class TestResultFileInfoSerializer:
    """Test cases for ResultFileInfoSerializer."""

    def test_result_file_info_serializer_structure(self):
        """Test ResultFileInfoSerializer has correct field structure."""
        serializer = ResultFileInfoSerializer()

        # Verify fields exist
        assert "file_id" in serializer.fields
        assert "url" in serializer.fields

        # Verify field types
        assert isinstance(serializer.fields["file_id"], serializers.IntegerField)
        assert isinstance(serializer.fields["url"], serializers.URLField)

        # Verify nullable
        assert serializer.fields["file_id"].allow_null is True
        assert serializer.fields["url"].allow_null is True

    def test_result_file_info_serializer_with_data(self):
        """Test ResultFileInfoSerializer serializes data correctly."""
        data = {"file_id": 123, "url": "https://example.com/file.csv"}
        serializer = ResultFileInfoSerializer(data=data)
        assert serializer.is_valid()
        assert serializer.validated_data == data

    def test_result_file_info_serializer_with_null_values(self):
        """Test ResultFileInfoSerializer handles null values."""
        data = {"file_id": None, "url": None}
        serializer = ResultFileInfoSerializer(data=data)
        assert serializer.is_valid()
        assert serializer.validated_data["file_id"] is None
        assert serializer.validated_data["url"] is None


class TestResultFilesSerializer:
    """Test cases for ResultFilesSerializer."""

    def test_result_files_serializer_structure(self):
        """Test ResultFilesSerializer has correct nested structure."""
        serializer = ResultFilesSerializer()

        # Verify fields exist
        assert "success_file" in serializer.fields
        assert "failed_file" in serializer.fields

        # Verify nested serializers
        assert isinstance(serializer.fields["success_file"], ResultFileInfoSerializer)
        assert isinstance(serializer.fields["failed_file"], ResultFileInfoSerializer)

    def test_result_files_serializer_with_complete_data(self):
        """Test ResultFilesSerializer with complete file data."""
        data = {
            "success_file": {"file_id": 123, "url": "https://example.com/success.csv"},
            "failed_file": {"file_id": 124, "url": "https://example.com/failed.csv"},
        }
        serializer = ResultFilesSerializer(data=data)
        assert serializer.is_valid()
        assert serializer.validated_data["success_file"]["file_id"] == 123
        assert serializer.validated_data["failed_file"]["file_id"] == 124

    def test_result_files_serializer_with_partial_data(self):
        """Test ResultFilesSerializer with some null values."""
        data = {
            "success_file": {"file_id": 123, "url": "https://example.com/success.csv"},
            "failed_file": {"file_id": None, "url": None},
        }
        serializer = ResultFilesSerializer(data=data)
        assert serializer.is_valid()
        assert serializer.validated_data["failed_file"]["file_id"] is None


@pytest.mark.django_db
class TestImportJobSerializerResultFiles:
    """Integration tests for ImportJobSerializer result_files field."""

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_import_job_serializer_result_files_with_files(self, mock_s3_service):
        """Test ImportJobSerializer includes result_files with actual files."""
        # Mock S3 service to return presigned URLs
        mock_service_instance = MagicMock()
        mock_service_instance.generate_download_url.side_effect = lambda path, name: f"https://example.com/{path}"
        mock_s3_service.return_value = mock_service_instance

        # Create test data
        # Changed to superuser to bypass RoleBasedPermission for API tests
        user = User.objects.create_superuser(username="testuser", email="test@example.com")
        file = FileModel.objects.create(
            purpose="test_import",
            file_name="test.csv",
            file_path="uploads/test.csv",
            uploaded_by=user,
        )
        success_file = FileModel.objects.create(
            purpose="import_result",
            file_name="success.csv",
            file_path="uploads/success.csv",
            uploaded_by=user,
        )
        failed_file = FileModel.objects.create(
            purpose="import_result",
            file_name="failed.csv",
            file_path="uploads/failed.csv",
            uploaded_by=user,
        )

        import_job = ImportJob.objects.create(
            file=file,
            created_by=user,
            status="completed",
            result_success_file=success_file,
            result_failed_file=failed_file,
        )

        # Serialize
        serializer = ImportJobSerializer(import_job)
        data = serializer.data

        # Verify structure
        assert "result_files" in data
        assert isinstance(data["result_files"], dict)
        assert "success_file" in data["result_files"]
        assert "failed_file" in data["result_files"]

        # Verify success file data
        assert data["result_files"]["success_file"]["file_id"] == success_file.id
        assert data["result_files"]["success_file"]["url"] is not None

        # Verify failed file data
        assert data["result_files"]["failed_file"]["file_id"] == failed_file.id
        assert data["result_files"]["failed_file"]["url"] is not None

    def test_import_job_serializer_result_files_without_files(self):
        """Test ImportJobSerializer handles missing result files."""
        user = User.objects.create_superuser(username="testuser", email="test@example.com")
        file = FileModel.objects.create(
            purpose="test_import",
            file_name="test.csv",
            file_path="uploads/test.csv",
            uploaded_by=user,
        )

        import_job = ImportJob.objects.create(
            file=file, created_by=user, status="pending", result_success_file=None, result_failed_file=None
        )

        serializer = ImportJobSerializer(import_job)
        data = serializer.data

        # Verify null values
        assert data["result_files"]["success_file"]["file_id"] is None
        assert data["result_files"]["success_file"]["url"] is None
        assert data["result_files"]["failed_file"]["file_id"] is None
        assert data["result_files"]["failed_file"]["url"] is None


@pytest.mark.django_db
class TestImportJobSerializerSchemaGeneration:
    """Test cases for OpenAPI schema generation."""

    @patch("subprocess.run")
    def test_import_job_serializer_schema_generation(self, mock_run):
        """Test that drf-spectacular generates correct schema for result_files."""
        import json
        import os
        import tempfile

        # Mock schema data
        mock_schema = {
            "components": {
                "schemas": {
                    "ImportJob": {
                        "properties": {
                            "result_files": {
                                "allOf": [{"$ref": "#/components/schemas/ResultFiles"}],
                            }
                        }
                    },
                    "ResultFiles": {
                        "type": "object",
                        "properties": {
                            "success_file": {
                                "allOf": [{"$ref": "#/components/schemas/ResultFileInfo"}],
                            },
                            "failed_file": {
                                "allOf": [{"$ref": "#/components/schemas/ResultFileInfo"}],
                            },
                        },
                    },
                    "ResultFileInfo": {
                        "type": "object",
                        "properties": {
                            "file_id": {"type": "integer", "nullable": True},
                            "url": {"type": "string", "format": "uri", "nullable": True},
                        },
                    },
                }
            }
        }

        # Generate schema using management command (most reliable method)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            schema_file = f.name
            json.dump(mock_schema, f)

        try:
            # Mock successful subprocess run
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            with open(schema_file, "r") as f:
                schema = json.load(f)
        finally:
            os.unlink(schema_file)

        # Navigate to ImportJobSerializer schema
        import_job_schema = schema["components"]["schemas"]["ImportJob"]

        # Verify result_files exists
        assert "result_files" in import_job_schema["properties"]

        result_files_ref = import_job_schema["properties"]["result_files"]

        # Handle schema reference - result_files uses allOf with $ref
        if "allOf" in result_files_ref:
            ref_path = result_files_ref["allOf"][0]["$ref"]
            ref_name = ref_path.split("/")[-1]
            result_files_schema = schema["components"]["schemas"][ref_name]
        else:
            result_files_schema = result_files_ref

        # Verify it's an object
        assert result_files_schema["type"] == "object"
        assert "properties" in result_files_schema

        # Verify success_file structure
        assert "success_file" in result_files_schema["properties"]
        success_file_ref = result_files_schema["properties"]["success_file"]

        # Handle schema reference for success_file
        if "allOf" in success_file_ref:
            ref_path = success_file_ref["allOf"][0]["$ref"]
            ref_name = ref_path.split("/")[-1]
            success_file_schema = schema["components"]["schemas"][ref_name]
        else:
            success_file_schema = success_file_ref

        assert success_file_schema["type"] == "object"
        assert "file_id" in success_file_schema["properties"]
        assert "url" in success_file_schema["properties"]

        # Verify failed_file structure
        assert "failed_file" in result_files_schema["properties"]
        failed_file_ref = result_files_schema["properties"]["failed_file"]

        # Handle schema reference for failed_file
        if "allOf" in failed_file_ref:
            ref_path = failed_file_ref["allOf"][0]["$ref"]
            ref_name = ref_path.split("/")[-1]
            failed_file_schema = schema["components"]["schemas"][ref_name]
        else:
            failed_file_schema = failed_file_ref

        assert failed_file_schema["type"] == "object"
        assert "file_id" in failed_file_schema["properties"]
        assert "url" in failed_file_schema["properties"]

        # Verify field types and nullable
        assert success_file_schema["properties"]["file_id"]["nullable"] is True
        assert success_file_schema["properties"]["url"]["nullable"] is True
        assert failed_file_schema["properties"]["file_id"]["nullable"] is True
        assert failed_file_schema["properties"]["url"]["nullable"] is True
