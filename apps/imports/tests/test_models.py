"""Tests for ImportJob model."""

import pytest
from django.contrib.auth import get_user_model

from apps.files.models import FileModel
from apps.imports.constants import STATUS_QUEUED
from apps.imports.models import ImportJob

User = get_user_model()


@pytest.mark.django_db
class TestImportJobModel:
    """Test cases for ImportJob model."""

    def test_create_import_job(self):
        """Test creating an import job."""
        # Create user
        # Changed to superuser to bypass RoleBasedPermission for API tests
        user = User.objects.create_superuser(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        # Create file
        file_obj = FileModel.objects.create(
            purpose="test_import",
            file_name="test.csv",
            file_path="test/test.csv",
            is_confirmed=True,
            uploaded_by=user,
        )

        # Create import job
        job = ImportJob.objects.create(
            file=file_obj,
            created_by=user,
            options={"batch_size": 100},
        )

        assert job.id is not None
        assert job.status == STATUS_QUEUED
        assert job.file == file_obj
        assert job.created_by == user
        assert job.options == {"batch_size": 100}
        assert job.processed_rows == 0
        assert job.success_count == 0
        assert job.failure_count == 0

    def test_calculate_percentage(self):
        """Test percentage calculation."""
        # Create minimal job
        user = User.objects.create_superuser(username="testuser", email="test@example.com")
        file_obj = FileModel.objects.create(
            purpose="test",
            file_name="test.csv",
            file_path="test.csv",
            is_confirmed=True,
        )
        job = ImportJob.objects.create(file=file_obj, created_by=user)

        # No total rows
        job.calculate_percentage()
        assert job.percentage is None

        # With total rows
        job.total_rows = 100
        job.processed_rows = 50
        job.calculate_percentage()
        assert job.percentage == 50.0

        # 100% completion
        job.processed_rows = 100
        job.calculate_percentage()
        assert job.percentage == 100.0

    def test_import_job_string_representation(self):
        """Test string representation of ImportJob."""
        user = User.objects.create_superuser(username="testuser", email="test@example.com")
        file_obj = FileModel.objects.create(
            purpose="test",
            file_name="test.csv",
            file_path="test.csv",
            is_confirmed=True,
        )
        job = ImportJob.objects.create(file=file_obj, created_by=user)

        str_repr = str(job)
        assert "ImportJob" in str_repr
        assert str(job.id) in str_repr
        assert job.status in str_repr
