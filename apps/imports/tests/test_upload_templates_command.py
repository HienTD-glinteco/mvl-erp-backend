"""Tests for upload_import_templates management command."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.files.models import FileModel
from apps.imports.constants import FILE_PURPOSE_IMPORT_TEMPLATE

User = get_user_model()


@pytest.fixture
def user(db):
    """Create test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def temp_template_dir():
    """Create a temporary directory with template files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test template files
        template_dir = Path(tmpdir)

        # Create CSV template
        csv_file = template_dir / "hrm_employees_template.csv"
        csv_file.write_text("name,email,department\nJohn Doe,john@example.com,Engineering\n")

        # Create XLSX template (mock content)
        xlsx_file = template_dir / "crm_customers_template.xlsx"
        xlsx_file.write_bytes(b"fake xlsx content")

        # Create another CSV template
        csv_file2 = template_dir / "core_users_template.csv"
        csv_file2.write_text("username,email,first_name,last_name\n")

        # Create file with invalid naming convention
        invalid_file = template_dir / "invalid_file.csv"
        invalid_file.write_text("invalid content")

        yield tmpdir


@pytest.mark.django_db
class TestUploadImportTemplatesCommand:
    """Test cases for upload_import_templates management command."""

    @patch("apps.imports.management.commands.upload_import_templates.S3FileUploadService")
    def test_upload_templates_success(self, mock_s3_service, temp_template_dir, capsys):
        """Test successful upload of template files."""
        # Mock S3 service
        mock_s3_instance = MagicMock()
        mock_s3_service.return_value = mock_s3_instance

        # Call command
        call_command("upload_import_templates", temp_template_dir)

        # Capture output
        captured = capsys.readouterr()

        # Verify files were found
        assert "Found 3 template file(s)" in captured.out
        assert "hrm_employees_template.csv" in captured.out
        assert "crm_customers_template.xlsx" in captured.out
        assert "core_users_template.csv" in captured.out

        # Verify S3 upload was called
        assert mock_s3_instance.upload_file.call_count == 3

        # Verify FileModel records were created
        assert FileModel.objects.filter(purpose=FILE_PURPOSE_IMPORT_TEMPLATE).count() == 3

        # Verify success message
        assert "Successfully uploaded 3 template file(s)" in captured.out

    @patch("apps.imports.management.commands.upload_import_templates.S3FileUploadService")
    def test_upload_templates_with_user(self, mock_s3_service, temp_template_dir, user, capsys):
        """Test upload with specified user."""
        mock_s3_instance = MagicMock()
        mock_s3_service.return_value = mock_s3_instance

        # Call command with user_id
        call_command("upload_import_templates", temp_template_dir, user_id=user.id)

        # Verify user association
        templates = FileModel.objects.filter(purpose=FILE_PURPOSE_IMPORT_TEMPLATE)
        assert templates.count() == 3
        for template in templates:
            assert template.uploaded_by == user

    @patch("apps.imports.management.commands.upload_import_templates.S3FileUploadService")
    def test_upload_templates_custom_s3_prefix(self, mock_s3_service, temp_template_dir, capsys):
        """Test upload with custom S3 prefix."""
        mock_s3_instance = MagicMock()
        mock_s3_service.return_value = mock_s3_instance

        # Call command with custom prefix
        custom_prefix = "custom/templates/"
        call_command("upload_import_templates", temp_template_dir, s3_prefix=custom_prefix)

        # Verify S3 paths include custom prefix
        templates = FileModel.objects.filter(purpose=FILE_PURPOSE_IMPORT_TEMPLATE)
        for template in templates:
            assert template.file_path.startswith(custom_prefix)

    @patch("apps.imports.management.commands.upload_import_templates.S3FileUploadService")
    def test_upload_templates_dry_run(self, mock_s3_service, temp_template_dir, capsys):
        """Test dry run mode."""
        mock_s3_instance = MagicMock()
        mock_s3_service.return_value = mock_s3_instance

        # Call command with dry_run
        call_command("upload_import_templates", temp_template_dir, dry_run=True)

        # Capture output
        captured = capsys.readouterr()

        # Verify files were found but not uploaded
        assert "Found 3 template file(s)" in captured.out
        assert "Dry run mode - no files will be uploaded" in captured.out

        # Verify no S3 upload
        assert mock_s3_instance.upload_file.call_count == 0

        # Verify no FileModel records
        assert FileModel.objects.filter(purpose=FILE_PURPOSE_IMPORT_TEMPLATE).count() == 0

    @patch("apps.imports.management.commands.upload_import_templates.S3FileUploadService")
    def test_upload_templates_replace_existing(self, mock_s3_service, temp_template_dir, user, capsys):
        """Test replacing existing templates."""
        mock_s3_instance = MagicMock()
        mock_s3_service.return_value = mock_s3_instance

        # Create existing template
        existing_template = FileModel.objects.create(
            purpose=FILE_PURPOSE_IMPORT_TEMPLATE,
            file_name="hrm_old_template.csv",
            file_path="templates/imports/hrm_old_template.csv",
            size=512,
            is_confirmed=True,
            uploaded_by=user,
        )

        # Call command with replace flag
        call_command("upload_import_templates", temp_template_dir, replace=True)

        # Capture output
        captured = capsys.readouterr()

        # Verify existing template was archived (marked as not confirmed)
        existing_template.refresh_from_db()
        assert existing_template.is_confirmed is False

        # Verify new templates were created
        new_templates = FileModel.objects.filter(purpose=FILE_PURPOSE_IMPORT_TEMPLATE, is_confirmed=True)
        assert new_templates.count() == 3

        # Verify output includes replacement message
        assert "Archived" in captured.out

    def test_upload_templates_invalid_directory(self):
        """Test with non-existent directory."""
        with pytest.raises(CommandError) as exc_info:
            call_command("upload_import_templates", "/nonexistent/directory")

        assert "Directory does not exist" in str(exc_info.value)

    def test_upload_templates_invalid_user_id(self):
        """Test with invalid user ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(CommandError) as exc_info:
                call_command("upload_import_templates", tmpdir, user_id=99999)

            assert "User with ID 99999 does not exist" in str(exc_info.value)

    @patch("apps.imports.management.commands.upload_import_templates.S3FileUploadService")
    def test_upload_templates_skips_invalid_naming(self, mock_s3_service, temp_template_dir, capsys):
        """Test that files with invalid naming convention are skipped."""
        mock_s3_instance = MagicMock()
        mock_s3_service.return_value = mock_s3_instance

        # Call command
        call_command("upload_import_templates", temp_template_dir)

        # Capture output
        captured = capsys.readouterr()

        # Verify warning about invalid file
        assert "Skipping file with invalid naming convention: invalid_file.csv" in captured.out

        # Verify only valid templates were uploaded
        assert FileModel.objects.filter(purpose=FILE_PURPOSE_IMPORT_TEMPLATE).count() == 3

    @patch("apps.imports.management.commands.upload_import_templates.S3FileUploadService")
    def test_upload_templates_content_types(self, mock_s3_service, temp_template_dir):
        """Test that correct content types are used for different file extensions."""
        mock_s3_instance = MagicMock()
        mock_s3_service.return_value = mock_s3_instance

        # Call command
        call_command("upload_import_templates", temp_template_dir)

        # Get all upload_file calls
        upload_calls = mock_s3_instance.upload_file.call_args_list

        # Check content types
        content_types_used = set()
        for call_args, call_kwargs in upload_calls:
            content_types_used.add(call_kwargs.get("content_type"))

        # CSV files should use text/csv
        assert "text/csv" in content_types_used

        # XLSX files should use the correct MIME type
        assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in content_types_used

    def test_upload_templates_empty_directory(self, capsys):
        """Test with empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Call command
            call_command("upload_import_templates", tmpdir)

            # Capture output
            captured = capsys.readouterr()

            # Verify warning about no files
            assert "No template files found in directory" in captured.out

    @patch("apps.imports.management.commands.upload_import_templates.S3FileUploadService")
    def test_upload_templates_extract_app_name(self, mock_s3_service, capsys):
        """Test correct extraction of app name from filename."""
        mock_s3_instance = MagicMock()
        mock_s3_service.return_value = mock_s3_instance

        with tempfile.TemporaryDirectory() as tmpdir:
            template_dir = Path(tmpdir)

            # Create templates with various naming patterns
            (template_dir / "hrm_employees_template.csv").write_text("test")
            (template_dir / "crm_complex_name_template.xlsx").write_text("test")
            (template_dir / "core_users_data_template.csv").write_text("test")

            # Call command
            call_command("upload_import_templates", tmpdir)

            # Capture output
            captured = capsys.readouterr()

            # Verify app names were extracted correctly
            assert "(app: hrm)" in captured.out
            assert "(app: crm)" in captured.out
            assert "(app: core)" in captured.out
