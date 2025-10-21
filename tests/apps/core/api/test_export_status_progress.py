"""
Tests for export status API view with progress tracking.
"""

from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from libs.export_xlsx.constants import REDIS_PROGRESS_KEY_PREFIX


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "test-progress-cache",
        }
    },
)
class ExportStatusViewTests(TestCase):
    """Test cases for ExportStatusView with progress tracking."""

    def setUp(self):
        """Set up test fixtures."""
        from apps.core.models import User
        
        self.client = APIClient()
        self.url = reverse("core:export_status")
        cache.clear()
        
        # Create and authenticate user
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            is_superuser=True,  # Superuser bypasses permission checks
        )
        self.client.force_authenticate(user=self.user)

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    def test_missing_task_id(self):
        """Test request without task_id parameter."""
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertIn("error", data["error"])

    @patch("apps.core.api.views.export_status.AsyncResult")
    def test_pending_status(self, mock_async_result):
        """Test status check for pending task."""
        # Mock Celery task result
        mock_task = MagicMock()
        mock_task.state = "PENDING"
        mock_task.info = None
        mock_async_result.return_value = mock_task

        response = self.client.get(self.url, {"task_id": "test-task-123"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["data"]["task_id"], "test-task-123")
        self.assertEqual(response.json()["data"]["status"], "PENDING")

    @patch("apps.core.api.views.export_status.AsyncResult")
    def test_progress_status_from_redis(self, mock_async_result):
        """Test status check with progress from Redis."""
        task_id = "test-task-456"

        # Mock Celery task result
        mock_task = MagicMock()
        mock_task.state = "PROGRESS"
        mock_task.info = None
        mock_async_result.return_value = mock_task

        # Set progress in Redis
        redis_key = f"{REDIS_PROGRESS_KEY_PREFIX}{task_id}"
        progress_data = {
            "status": "PROGRESS",
            "percent": 45,
            "processed_rows": 450,
            "total_rows": 1000,
            "speed_rows_per_sec": 50.5,
            "eta_seconds": 10.9,
            "updated_at": "2025-10-20T10:30:00",
        }
        cache.set(redis_key, progress_data, timeout=3600)

        response = self.client.get(self.url, {"task_id": task_id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["data"]["task_id"], task_id)
        self.assertEqual(response.json()["data"]["status"], "PROGRESS")
        self.assertEqual(response.json()["data"]["percent"], 45)
        self.assertEqual(response.json()["data"]["processed_rows"], 450)
        self.assertEqual(response.json()["data"]["total_rows"], 1000)
        self.assertEqual(response.json()["data"]["speed_rows_per_sec"], 50.5)
        self.assertEqual(response.json()["data"]["eta_seconds"], 10.9)

    @patch("apps.core.api.views.export_status.AsyncResult")
    def test_progress_status_from_celery_meta(self, mock_async_result):
        """Test status check with progress from Celery meta (fallback)."""
        task_id = "test-task-789"

        # Mock Celery task result with progress info
        mock_task = MagicMock()
        mock_task.state = "PROGRESS"
        mock_task.info = {
            "status": "PROGRESS",
            "percent": 60,
            "processed_rows": 600,
            "total_rows": 1000,
            "speed_rows_per_sec": 45.2,
        }
        mock_async_result.return_value = mock_task

        response = self.client.get(self.url, {"task_id": task_id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["data"]["status"], "PROGRESS")
        self.assertEqual(response.json()["data"]["percent"], 60)
        self.assertEqual(response.json()["data"]["processed_rows"], 600)
        self.assertEqual(response.json()["data"]["total_rows"], 1000)

    @patch("apps.core.api.views.export_status.AsyncResult")
    def test_success_status(self, mock_async_result):
        """Test status check for completed task."""
        task_id = "test-task-success"

        # Mock Celery task result
        mock_task = MagicMock()
        mock_task.state = "SUCCESS"
        mock_task.result = {
            "status": "success",
            "file_url": "https://example.com/exports/test.xlsx",
            "file_path": "exports/test.xlsx",
        }
        mock_async_result.return_value = mock_task

        response = self.client.get(self.url, {"task_id": task_id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["data"]["status"], "SUCCESS")
        self.assertEqual(response.json()["data"]["file_url"], "https://example.com/exports/test.xlsx")
        self.assertEqual(response.json()["data"]["file_path"], "exports/test.xlsx")
        self.assertEqual(response.json()["data"]["percent"], 100)

    @patch("apps.core.api.views.export_status.AsyncResult")
    def test_success_status_with_redis_progress(self, mock_async_result):
        """Test that Redis progress data is included for SUCCESS state."""
        task_id = "test-task-success-redis"

        # Mock Celery task result
        mock_task = MagicMock()
        mock_task.state = "SUCCESS"
        mock_task.result = {
            "status": "success",
            "file_url": "https://example.com/exports/test.xlsx",
            "file_path": "exports/test.xlsx",
        }
        mock_async_result.return_value = mock_task

        # Set completed progress in Redis
        redis_key = f"{REDIS_PROGRESS_KEY_PREFIX}{task_id}"
        progress_data = {
            "status": "SUCCESS",
            "percent": 100,
            "processed_rows": 1000,
            "total_rows": 1000,
            "file_url": "https://example.com/exports/test.xlsx",
            "file_path": "exports/test.xlsx",
        }
        cache.set(redis_key, progress_data, timeout=3600)

        response = self.client.get(self.url, {"task_id": task_id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["data"]["status"], "SUCCESS")
        self.assertEqual(response.json()["data"]["percent"], 100)
        self.assertEqual(response.json()["data"]["processed_rows"], 1000)
        self.assertEqual(response.json()["data"]["total_rows"], 1000)

    @patch("apps.core.api.views.export_status.AsyncResult")
    def test_failure_status(self, mock_async_result):
        """Test status check for failed task."""
        task_id = "test-task-failure"

        # Mock Celery task result
        mock_task = MagicMock()
        mock_task.state = "FAILURE"
        mock_task.result = Exception("Export failed: database error")
        mock_async_result.return_value = mock_task

        response = self.client.get(self.url, {"task_id": task_id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["data"]["status"], "FAILURE")
        self.assertIn("Export failed", response.json()["data"]["error"])

    @patch("apps.core.api.views.export_status.AsyncResult")
    def test_failure_status_with_redis_progress(self, mock_async_result):
        """Test that Redis progress data is included for FAILURE state."""
        task_id = "test-task-failure-redis"

        # Mock Celery task result
        mock_task = MagicMock()
        mock_task.state = "FAILURE"
        mock_task.result = Exception("Export failed")
        mock_async_result.return_value = mock_task

        # Set failed progress in Redis
        redis_key = f"{REDIS_PROGRESS_KEY_PREFIX}{task_id}"
        progress_data = {
            "status": "FAILURE",
            "percent": 75,
            "processed_rows": 750,
            "total_rows": 1000,
            "error": "Export failed: database error",
        }
        cache.set(redis_key, progress_data, timeout=3600)

        response = self.client.get(self.url, {"task_id": task_id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["data"]["status"], "FAILURE")
        self.assertEqual(response.json()["data"]["processed_rows"], 750)
        self.assertEqual(response.json()["data"]["total_rows"], 1000)
        self.assertEqual(response.json()["data"]["error"], "Export failed: database error")

    @patch("apps.core.api.views.export_status.AsyncResult")
    def test_redis_priority_over_celery_meta(self, mock_async_result):
        """Test that Redis data takes priority over Celery meta."""
        task_id = "test-task-redis-priority"

        # Mock Celery task with outdated info
        mock_task = MagicMock()
        mock_task.state = "PROGRESS"
        mock_task.info = {
            "percent": 30,
            "processed_rows": 300,
        }
        mock_async_result.return_value = mock_task

        # Set newer progress in Redis
        redis_key = f"{REDIS_PROGRESS_KEY_PREFIX}{task_id}"
        progress_data = {
            "status": "PROGRESS",
            "percent": 80,
            "processed_rows": 800,
            "total_rows": 1000,
        }
        cache.set(redis_key, progress_data, timeout=3600)

        response = self.client.get(self.url, {"task_id": task_id})

        # Should use Redis data
        self.assertEqual(response.json()["data"]["percent"], 80)
        self.assertEqual(response.json()["data"]["processed_rows"], 800)

    @patch("apps.core.api.views.export_status.get_progress")
    @patch("apps.core.api.views.export_status.AsyncResult")
    def test_redis_unavailable_fallback(self, mock_async_result, mock_get_progress):
        """Test fallback to Celery meta when Redis is unavailable."""
        task_id = "test-task-fallback"

        # Mock Redis unavailable
        mock_get_progress.return_value = None

        # Mock Celery task with progress
        mock_task = MagicMock()
        mock_task.state = "PROGRESS"
        mock_task.info = {
            "percent": 50,
            "processed_rows": 500,
            "total_rows": 1000,
        }
        mock_async_result.return_value = mock_task

        response = self.client.get(self.url, {"task_id": task_id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["data"]["percent"], 50)
        self.assertEqual(response.json()["data"]["processed_rows"], 500)

    @patch("apps.core.api.views.export_status.AsyncResult")
    def test_response_includes_all_progress_fields(self, mock_async_result):
        """Test that response includes all progress tracking fields."""
        task_id = "test-task-full-fields"

        # Mock Celery task result
        mock_task = MagicMock()
        mock_task.state = "PROGRESS"
        mock_task.info = None
        mock_async_result.return_value = mock_task

        # Set complete progress in Redis
        redis_key = f"{REDIS_PROGRESS_KEY_PREFIX}{task_id}"
        progress_data = {
            "status": "PROGRESS",
            "percent": 65,
            "processed_rows": 650,
            "total_rows": 1000,
            "speed_rows_per_sec": 48.5,
            "eta_seconds": 7.2,
            "updated_at": "2025-10-20T11:00:00",
        }
        cache.set(redis_key, progress_data, timeout=3600)

        response = self.client.get(self.url, {"task_id": task_id})
        data = response.json()["data"]

        # Verify all fields are present
        self.assertIn("task_id", data)
        self.assertIn("status", data)
        self.assertIn("percent", data)
        self.assertIn("processed_rows", data)
        self.assertIn("total_rows", data)
        self.assertIn("speed_rows_per_sec", data)
        self.assertIn("eta_seconds", data)
        self.assertIn("updated_at", data)
