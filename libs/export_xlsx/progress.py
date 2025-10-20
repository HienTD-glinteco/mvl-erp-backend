"""
Progress tracking utilities for XLSX export.
"""

import logging
from datetime import datetime
from typing import Any, Optional

from django.core.cache import cache

from .constants import REDIS_PROGRESS_EXPIRE_SECONDS, REDIS_PROGRESS_KEY_PREFIX

logger = logging.getLogger(__name__)


class ExportProgressTracker:
    """
    Tracks and publishes export progress to Redis and Celery task meta.
    """

    def __init__(self, task_id: str, celery_task=None):
        """
        Initialize progress tracker.

        Args:
            task_id: Celery task ID
            celery_task: Celery task instance (for update_state)
        """
        self.task_id = task_id
        self.celery_task = celery_task
        self.redis_key = f"{REDIS_PROGRESS_KEY_PREFIX}{task_id}"
        self.total_rows = 0
        self.processed_rows = 0
        self.start_time = None

    def set_total(self, total_rows: int) -> None:
        """
        Set total number of rows to process.

        Args:
            total_rows: Total number of rows
        """
        self.total_rows = max(1, total_rows)
        self.processed_rows = 0
        self.start_time = datetime.now()
        self._publish_progress()

    def update(self, rows_processed: int) -> None:
        """
        Update processed rows count.

        Args:
            rows_processed: Number of rows processed in this update
        """
        self.processed_rows += rows_processed
        self._publish_progress()

    def set_completed(self, file_url: str = None, file_path: str = None) -> None:
        """
        Mark export as completed.

        Args:
            file_url: Download URL for the generated file
            file_path: File path in storage
        """
        self.processed_rows = self.total_rows
        progress_data = self._build_progress_data()
        progress_data["status"] = "SUCCESS"
        progress_data["file_url"] = file_url
        progress_data["file_path"] = file_path

        self._publish_to_redis(progress_data)

    def set_failed(self, error_message: str) -> None:
        """
        Mark export as failed.

        Args:
            error_message: Error message
        """
        progress_data = self._build_progress_data()
        progress_data["status"] = "FAILURE"
        progress_data["error"] = error_message

        self._publish_to_redis(progress_data)

    def _publish_progress(self) -> None:
        """Publish current progress to Redis and Celery."""
        progress_data = self._build_progress_data()

        # Publish to Redis
        self._publish_to_redis(progress_data)

        # Publish to Celery task meta
        self._publish_to_celery(progress_data)

    def _build_progress_data(self) -> dict:
        """
        Build progress data dictionary.

        Returns:
            dict: Progress data with percent, processed, total, etc.
        """
        percent = int((self.processed_rows / self.total_rows) * 100) if self.total_rows > 0 else 0

        progress_data = {
            "status": "PROGRESS",
            "percent": percent,
            "processed_rows": self.processed_rows,
            "total_rows": self.total_rows,
            "updated_at": datetime.now().isoformat(),
        }

        # Calculate speed and ETA if start time is available
        if self.start_time and self.processed_rows > 0:
            elapsed_seconds = (datetime.now() - self.start_time).total_seconds()
            if elapsed_seconds > 0:
                speed = self.processed_rows / elapsed_seconds
                progress_data["speed_rows_per_sec"] = round(speed, 2)

                remaining_rows = self.total_rows - self.processed_rows
                if speed > 0:
                    eta_seconds = remaining_rows / speed
                    progress_data["eta_seconds"] = round(eta_seconds, 0)

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
            logger.warning(f"Failed to publish progress to Redis: {e}")

    def _publish_to_celery(self, progress_data: dict) -> None:
        """
        Publish progress to Celery task meta.

        Args:
            progress_data: Progress data dictionary
        """
        if self.celery_task:
            try:
                self.celery_task.update_state(
                    state="PROGRESS",
                    meta=progress_data,
                )
            except Exception as e:
                logger.warning(f"Failed to publish progress to Celery: {e}")


def get_progress(task_id: str) -> Optional[dict]:
    """
    Retrieve export progress from Redis.

    Args:
        task_id: Celery task ID

    Returns:
        dict: Progress data or None if not found
    """
    redis_key = f"{REDIS_PROGRESS_KEY_PREFIX}{task_id}"
    try:
        return cache.get(redis_key)
    except Exception as e:
        logger.warning(f"Failed to retrieve progress from Redis: {e}")
        return None
