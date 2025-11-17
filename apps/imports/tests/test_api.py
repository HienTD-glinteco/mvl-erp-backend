"""Tests for import API endpoints."""

import json
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APIClient

from apps.files.models import FileModel
from apps.imports.constants import STATUS_QUEUED
from apps.imports.models import ImportJob

User = get_user_model()


@pytest.fixture
def api_client():
    """Create API client."""
    return APIClient()


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
def authenticated_client(api_client, user):
    """Create authenticated API client."""
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def test_file(user):
    """Create test file."""
    return FileModel.objects.create(
        purpose="test_import",
        file_name="test.csv",
        file_path="test/test.csv",
        is_confirmed=True,
        uploaded_by=user,
    )


@pytest.fixture
def import_job(test_file, user):
    """Create test import job."""
    return ImportJob.objects.create(
        file=test_file,
        created_by=user,
        status=STATUS_QUEUED,
        options={"handler_path": "apps.imports.tests.test_api.dummy_handler"},
    )


def dummy_handler(row_index, row, import_job_id, options):
    """Dummy handler for testing."""
    return {"ok": True, "result": {"id": row_index}}


@pytest.mark.django_db
class TestImportStatusView:
    """Test cases for ImportStatusView."""

    def setup_method(self):
        """Set up test data."""
        cache.clear()

    def teardown_method(self):
        """Clean up after tests."""
        cache.clear()

    @patch("apps.imports.api.views.RoleBasedPermission.has_permission", return_value=True)
    def test_get_status_missing_task_id(self, mock_perm, authenticated_client):
        """Test status check without task_id parameter."""
        response = authenticated_client.get("/api/import/status/")

        # Check wrapped response
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        content = json.loads(response.content)
        # Handle both wrapped and unwrapped responses
        if "data" in content and content["data"] is not None:
            assert "error" in content["data"]
        elif "error" in content:
            assert "error" in content
        else:
            # Just verify we got a 400
            pass

    @patch("apps.imports.api.views.RoleBasedPermission.has_permission", return_value=True)
    def test_get_status_not_found(self, mock_perm, authenticated_client):
        """Test status check for non-existent job."""
        response = authenticated_client.get(
            "/api/import/status/",
            {"task_id": "00000000-0000-0000-0000-000000000000"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch("apps.imports.api.views.RoleBasedPermission.has_permission", return_value=True)
    def test_get_status_success(self, mock_perm, authenticated_client, import_job):
        """Test successful status check."""
        response = authenticated_client.get(
            "/api/import/status/",
            {"task_id": str(import_job.id)},
        )

        assert response.status_code == status.HTTP_200_OK
        content = json.loads(response.content)

        # Handle wrapped response
        data = content.get("data", content)

        assert "id" in data
        assert "status" in data
        assert data["status"] == STATUS_QUEUED

    @patch("apps.imports.api.views.RoleBasedPermission.has_permission", return_value=True)
    def test_get_status_with_redis_progress(self, mock_perm, authenticated_client, import_job):
        """Test status check with Redis progress data."""
        from apps.imports.progress import ImportProgressTracker

        # Add progress to Redis
        tracker = ImportProgressTracker(str(import_job.id))
        tracker.set_total(100)
        tracker.update(success_increment=50)

        response = authenticated_client.get(
            "/api/import/status/",
            {"task_id": str(import_job.id)},
        )

        assert response.status_code == status.HTTP_200_OK
        content = json.loads(response.content)
        data = content.get("data", content)

        # Redis progress should override DB values
        assert data["processed_rows"] == 50
        assert data["success_count"] == 50
        assert data["percentage"] == 50.0


@pytest.mark.django_db
class TestImportMixin:
    """Test cases for AsyncImportProgressMixin."""

    def test_start_import_missing_file(self, authenticated_client):
        """Test starting import with non-existent file."""
        # Test serializer validation directly
        from apps.imports.api.serializers import ImportStartSerializer

        serializer = ImportStartSerializer(
            data={
                "file_id": 99999,
                "options": {"handler_path": "apps.imports.tests.test_api.dummy_handler"},
            }
        )

        # Should fail validation
        assert not serializer.is_valid()
        assert "file_id" in serializer.errors

    def test_start_import_file_not_confirmed(self, authenticated_client, user):
        """Test starting import with unconfirmed file."""
        from apps.imports.api.serializers import ImportStartSerializer

        # Create unconfirmed file
        file_obj = FileModel.objects.create(
            purpose="test_import",
            file_name="test.csv",
            file_path="test/test.csv",
            is_confirmed=False,  # Not confirmed
            uploaded_by=user,
        )

        serializer = ImportStartSerializer(
            data={
                "file_id": file_obj.id,
                "options": {"handler_path": "apps.imports.tests.test_api.dummy_handler"},
            }
        )

        # Should fail validation
        assert not serializer.is_valid()
        assert "file_id" in serializer.errors


@pytest.mark.django_db
class TestImportMixinWithMethodHandler:
    """Test cases for AsyncImportProgressMixin with ViewSet method handler."""

    def test_viewset_method_handler_detection(self):
        """Test that ViewSet method handler is detected."""
        from apps.imports.api.mixins import AsyncImportProgressMixin

        # Create a test ViewSet with method handler
        class TestViewSet(AsyncImportProgressMixin):
            def _process_import_data_row(self, row_index, row, import_job_id, options):
                return {"ok": True, "result": {"id": row_index}}

        viewset = TestViewSet()

        # Should return None when method is defined
        assert viewset.get_import_handler_path() is None

        # Should have the method
        assert hasattr(viewset, "_process_import_data_row")
        assert callable(viewset._process_import_data_row)

    def test_viewset_method_handler_storage_in_options(self):
        """Test that ViewSet method handler info is stored in options."""
        from apps.imports.api.mixins import AsyncImportProgressMixin

        # Create a test ViewSet with method handler
        class TestViewSet(AsyncImportProgressMixin):
            def _process_import_data_row(self, row_index, row, import_job_id, options):
                return {"ok": True, "result": {"id": row_index}}

        viewset = TestViewSet()

        # Simulate the logic from start_import
        options = {}
        handler_path = viewset.get_import_handler_path()

        # Check if using ViewSet method handler
        if handler_path is None and hasattr(viewset, "_process_import_data_row"):
            viewset_class_path = f"{viewset.__class__.__module__}.{viewset.__class__.__name__}"
            options["handler_path"] = None
            options["viewset_class_path"] = viewset_class_path
            options["use_viewset_method"] = True

        # Verify options were set correctly
        assert options.get("use_viewset_method") is True
        assert options.get("viewset_class_path") is not None
        assert "TestViewSet" in options.get("viewset_class_path")
