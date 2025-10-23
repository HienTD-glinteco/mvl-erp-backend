"""Tests for import progress tracking."""

import pytest
from django.core.cache import cache

from apps.imports.progress import ImportProgressTracker, get_import_progress


@pytest.mark.django_db
class TestImportProgressTracker:
    """Test cases for ImportProgressTracker."""

    def setup_method(self):
        """Set up test data."""
        cache.clear()

    def teardown_method(self):
        """Clean up after tests."""
        cache.clear()

    def test_tracker_initialization(self):
        """Test tracker initialization."""
        tracker = ImportProgressTracker("test-job-id")
        assert tracker.import_job_id == "test-job-id"
        assert tracker.total_rows == 0
        assert tracker.processed_rows == 0
        assert tracker.success_count == 0
        assert tracker.failure_count == 0

    def test_set_total(self):
        """Test setting total rows."""
        tracker = ImportProgressTracker("test-job-id")
        tracker.set_total(100)

        assert tracker.total_rows == 100
        assert tracker.processed_rows == 0
        assert tracker.start_time is not None

        # Check Redis
        progress = get_import_progress("test-job-id")
        assert progress is not None
        assert progress["total_rows"] == 100
        assert progress["processed_rows"] == 0

    def test_update_progress(self):
        """Test updating progress."""
        tracker = ImportProgressTracker("test-job-id")
        tracker.set_total(100)

        # Update with successes
        tracker.update(success_increment=10)
        assert tracker.success_count == 10
        assert tracker.failure_count == 0
        assert tracker.processed_rows == 10

        # Update with failures
        tracker.update(failure_increment=5)
        assert tracker.success_count == 10
        assert tracker.failure_count == 5
        assert tracker.processed_rows == 15

        # Update with both
        tracker.update(success_increment=20, failure_increment=3)
        assert tracker.success_count == 30
        assert tracker.failure_count == 8
        assert tracker.processed_rows == 38

        # Check Redis
        progress = get_import_progress("test-job-id")
        assert progress["processed_rows"] == 38
        assert progress["success_count"] == 30
        assert progress["failure_count"] == 8

    def test_percentage_calculation(self):
        """Test percentage calculation in progress data."""
        tracker = ImportProgressTracker("test-job-id")
        tracker.set_total(100)

        tracker.update(success_increment=25)

        progress = get_import_progress("test-job-id")
        assert progress["percentage"] == 25.0

        tracker.update(success_increment=25)
        progress = get_import_progress("test-job-id")
        assert progress["percentage"] == 50.0

    def test_set_completed(self):
        """Test marking import as completed."""
        tracker = ImportProgressTracker("test-job-id")
        tracker.set_total(100)
        tracker.update(success_increment=100)
        tracker.set_completed()

        progress = get_import_progress("test-job-id")
        assert progress["status"] == "completed"

    def test_set_failed(self):
        """Test marking import as failed."""
        tracker = ImportProgressTracker("test-job-id")
        tracker.set_total(100)
        tracker.update(success_increment=30)
        tracker.set_failed("Something went wrong")

        progress = get_import_progress("test-job-id")
        assert progress["status"] == "failed"
        assert progress["error"] == "Something went wrong"

    def test_get_import_progress_not_found(self):
        """Test getting progress for non-existent job."""
        progress = get_import_progress("non-existent-job-id")
        assert progress is None
