"""Progress tracking utilities for import jobs."""

import logging
from datetime import datetime
from typing import Optional

from django.core.cache import cache

from .constants import IMPORT_PROGRESS_KEY_TEMPLATE, REDIS_PROGRESS_EXPIRE_SECONDS

logger = logging.getLogger(__name__)


class ImportProgressTracker:
    """
    Tracks and publishes import progress to Redis and database.

    Similar to ExportProgressTracker but tailored for imports with
    success_count and failure_count tracking.
    """

    def __init__(self, import_job_id: str):
        """
        Initialize progress tracker.

        Args:
            import_job_id: UUID of the ImportJob
        """
        self.import_job_id = import_job_id
        self.redis_key = IMPORT_PROGRESS_KEY_TEMPLATE.format(import_job_id=import_job_id)
        self.total_rows = 0
        self.processed_rows = 0
        self.success_count = 0
        self.failure_count = 0
        self.start_time = datetime.now()

    def set_total(self, total_rows: int) -> None:
        """
        Set total number of rows to process.

        Args:
            total_rows: Total number of rows
        """
        self.total_rows = max(1, total_rows)
        self.processed_rows = 0
        self.success_count = 0
        self.failure_count = 0
        self.start_time = datetime.now()
        self._publish_progress()

    def update(self, success_increment: int = 0, failure_increment: int = 0) -> None:
        """
        Update processed rows count.

        Args:
            success_increment: Number of successfully processed rows
            failure_increment: Number of failed rows
        """
        self.success_count += success_increment
        self.failure_count += failure_increment
        self.processed_rows = self.success_count + self.failure_count
        self._publish_progress()

    def set_completed(self) -> None:
        """Mark import as completed."""
        progress_data = self._build_progress_data()
        progress_data["status"] = "completed"
        self._publish_to_redis(progress_data)

    def set_failed(self, error_message: str) -> None:
        """
        Mark import as failed.

        Args:
            error_message: Error message
        """
        progress_data = self._build_progress_data()
        progress_data["status"] = "failed"
        progress_data["error"] = error_message
        self._publish_to_redis(progress_data)

    def _publish_progress(self) -> None:
        """Publish current progress to Redis."""
        progress_data = self._build_progress_data()
        self._publish_to_redis(progress_data)

    def _build_progress_data(self) -> dict:
        """
        Build progress data dictionary.

        Returns:
            dict: Progress data with processed, total, success, failure counts, etc.
        """
        progress_data = {
            "processed_rows": self.processed_rows,
            "total_rows": self.total_rows if self.total_rows > 0 else None,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "last_updated": datetime.now().isoformat(),
        }

        # Calculate percentage if total is known
        if self.total_rows and self.total_rows > 0:
            percentage = (self.processed_rows / self.total_rows) * 100.0
            progress_data["percentage"] = round(percentage, 2)  # type: ignore[assignment]

        return progress_data

    def _publish_to_redis(self, progress_data: dict) -> None:
        """
        Publish progress to Redis.

        Args:
            progress_data: Progress data dictionary
        """
        try:
            cache.set(
                self.redis_key,
                progress_data,
                timeout=REDIS_PROGRESS_EXPIRE_SECONDS,
            )
        except Exception as e:
            logger.warning(f"Failed to publish progress to Redis for job {self.import_job_id}: {e}")


def get_import_progress(import_job_id: str) -> Optional[dict]:
    """
    Retrieve import progress from Redis.

    Args:
        import_job_id: UUID of the ImportJob

    Returns:
        dict: Progress data or None if not found
    """
    redis_key = IMPORT_PROGRESS_KEY_TEMPLATE.format(import_job_id=import_job_id)
    try:
        return cache.get(redis_key)
    except Exception as e:
        logger.warning(f"Failed to retrieve progress from Redis for job {import_job_id}: {e}")
        return None
