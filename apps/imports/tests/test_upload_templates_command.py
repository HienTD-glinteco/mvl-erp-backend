"""Tests for upload_import_templates management command."""

import tempfile
from pathlib import Path
from unittest.mock import patch

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
    # Changed to superuser to bypass RoleBasedPermission for API tests
    return User.objects.create_superuser(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def mock_apps_structure():
    """Create a temporary directory structure mimicking apps/*/fixtures/import_templates/."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create apps structure
        apps_dir = Path(tmpdir) / "apps"
        apps_dir.mkdir()

        # Create hrm app with fixtures/import_templates
        hrm_dir = apps_dir / "hrm" / "fixtures" / "import_templates"
        hrm_dir.mkdir(parents=True)
        (hrm_dir / "employees_template.csv").write_text("name,email\n")
        (hrm_dir / "departments_template.xlsx").write_bytes(b"fake xlsx")

        # Create crm app with fixtures/import_templates
        crm_dir = apps_dir / "crm" / "fixtures" / "import_templates"
        crm_dir.mkdir(parents=True)
        (crm_dir / "customers_template.csv").write_text("name,email\n")

        # Create app without import_templates
        core_dir = apps_dir / "core"
        core_dir.mkdir()

        yield tmpdir


@pytest.mark.django_db
class TestUploadImportTemplatesCommand:
    """Test cases for upload_import_templates management command."""

    @patch("apps.imports.management.commands.upload_import_templates.default_storage")
    @patch("os.getcwd")
    def test_upload_templates_success(self, mock_getcwd, mock_storage, mock_apps_structure, capsys):
        """Test successful upload of template files."""
        # Mock getcwd to return our test directory
        mock_getcwd.return_value = mock_apps_structure

        # Mock default_storage.save to return the path
        mock_storage.save.side_effect = lambda path, content: path

        # Call command
        call_command("upload_import_templates")

        # Capture output
        captured = capsys.readouterr()

        # Verify files were found with app prefixes
        assert "Found 3 template file(s)" in captured.out
        assert "hrm_employees_template.csv" in captured.out
        assert "hrm_departments_template.xlsx" in captured.out
        assert "crm_customers_template.csv" in captured.out

        # Verify storage.save was called
        assert mock_storage.save.call_count == 3

        # Verify FileModel records were created with app prefixes
        assert FileModel.objects.filter(purpose=FILE_PURPOSE_IMPORT_TEMPLATE).count() == 3
        assert FileModel.objects.filter(file_name="hrm_employees_template.csv").exists()
        assert FileModel.objects.filter(file_name="hrm_departments_template.xlsx").exists()
        assert FileModel.objects.filter(file_name="crm_customers_template.csv").exists()

    @patch("apps.imports.management.commands.upload_import_templates.default_storage")
    @patch("os.getcwd")
    def test_upload_templates_single_app(self, mock_getcwd, mock_storage, mock_apps_structure, capsys):
        """Test upload with --app filter."""
        mock_getcwd.return_value = mock_apps_structure
        mock_storage.save.side_effect = lambda path, content: path

        # Call command with app filter
        call_command("upload_import_templates", app="hrm")

        # Capture output
        captured = capsys.readouterr()

        # Verify only hrm files were found
        assert "Found 2 template file(s)" in captured.out
        assert "hrm_employees_template.csv" in captured.out
        assert "hrm_departments_template.xlsx" in captured.out
        assert "crm_customers_template.csv" not in captured.out

    @patch("apps.imports.management.commands.upload_import_templates.default_storage")
    @patch("os.getcwd")
    def test_upload_templates_with_user(self, mock_getcwd, mock_storage, mock_apps_structure, user, capsys):
        """Test upload with specified user."""
        mock_getcwd.return_value = mock_apps_structure
        mock_storage.save.side_effect = lambda path, content: path

        # Call command with user_id
        call_command("upload_import_templates", user_id=user.id)

        # Verify user association
        templates = FileModel.objects.filter(purpose=FILE_PURPOSE_IMPORT_TEMPLATE)
        assert templates.count() == 3
        for template in templates:
            assert template.uploaded_by == user

    @patch("apps.imports.management.commands.upload_import_templates.default_storage")
    @patch("os.getcwd")
    def test_upload_templates_dry_run(self, mock_getcwd, mock_storage, mock_apps_structure, capsys):
        """Test dry run mode."""
        mock_getcwd.return_value = mock_apps_structure
        mock_storage.save.side_effect = lambda path, content: path

        # Call command with dry_run
        call_command("upload_import_templates", dry_run=True)

        # Capture output
        captured = capsys.readouterr()

        # Verify files were found but not uploaded
        assert "Found 3 template file(s)" in captured.out
        assert "Dry run mode - no files will be uploaded" in captured.out

        # Verify no S3 upload
        assert mock_storage.save.call_count == 0

        # Verify no FileModel records
        assert FileModel.objects.filter(purpose=FILE_PURPOSE_IMPORT_TEMPLATE).count() == 0

    @patch("apps.imports.management.commands.upload_import_templates.default_storage")
    @patch("os.getcwd")
    def test_upload_templates_replace_existing(self, mock_getcwd, mock_storage, mock_apps_structure, user, capsys):
        """Test replacing existing templates."""
        mock_getcwd.return_value = mock_apps_structure
        mock_storage.save.side_effect = lambda path, content: path

        # Create existing template
        existing_template = FileModel.objects.create(
            purpose=FILE_PURPOSE_IMPORT_TEMPLATE,
            file_name="hrm_employees_template.csv",
            file_path="templates/imports/hrm_employees_template.csv",
            size=512,
            is_confirmed=True,
            uploaded_by=user,
        )

        # Call command with replace flag
        call_command("upload_import_templates", replace=True)

        # Verify existing template was archived (marked as not confirmed)
        existing_template.refresh_from_db()
        assert existing_template.is_confirmed is False

        # Verify new templates were created
        new_templates = FileModel.objects.filter(purpose=FILE_PURPOSE_IMPORT_TEMPLATE, is_confirmed=True)
        assert new_templates.count() == 3

    @patch("os.getcwd")
    def test_upload_templates_no_apps_dir(self, mock_getcwd, capsys):
        """Test when apps directory doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_getcwd.return_value = tmpdir

            # Call command
            call_command("upload_import_templates")

            # Capture output
            captured = capsys.readouterr()

            # Verify warning
            assert "Apps directory not found" in captured.out

    def test_upload_templates_invalid_user_id(self):
        """Test with invalid user ID."""
        with pytest.raises(CommandError) as exc_info:
            call_command("upload_import_templates", user_id=99999)

        assert "User with ID 99999 does not exist" in str(exc_info.value)
