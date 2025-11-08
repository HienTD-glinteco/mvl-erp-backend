"""Event-driven Celery task for HR reports aggregation.

This module contains the event-driven task that fires whenever EmployeeWorkHistory
changes (create, edit, delete) via Django signals.
"""

import logging
from typing import Any

from celery import shared_task
from django.db import transaction

from .helpers import (
    AGGREGATION_MAX_RETRIES,
    AGGREGATION_RETRY_DELAY,
    _increment_employee_status,
    _increment_staff_growth,
)

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=AGGREGATION_MAX_RETRIES)
def aggregate_hr_reports_for_work_history(
    self, event_type: str, snapshot: dict[str, Any]
) -> dict[str, Any]:
    """Aggregate HR reports for a single work history event (smart incremental update).

    This event-driven task uses snapshot data to avoid race conditions where the
    work history record might be modified before the task processes.

    Args:
        self: Celery task instance
        event_type: Type of event - "create", "update", or "delete"
        snapshot: Dict containing previous and current state:
            - previous: Previous state (None for create, dict for update/delete)
            - current: Current state (dict for create/update, None for delete)

    Returns:
        dict: Aggregation result with success status and metadata
    """
    try:
        previous = snapshot.get("previous")
        current = snapshot.get("current")

        if not previous and not current:
            logger.warning(f"Invalid snapshot for event {event_type}")
            return {"success": False, "error": "Invalid snapshot"}

        # Extract data from current or previous state
        data = current if current else previous
        report_date = data["date"]

        logger.info(
            f"Incrementally updating HR reports for work history "
            f"(event: {event_type}, date: {report_date})"
        )

        # Perform incremental update
        with transaction.atomic():
            _increment_staff_growth(event_type, snapshot)
            _increment_employee_status(event_type, snapshot)

        return {
            "success": True,
            "event_type": event_type,
            "report_date": str(report_date),
        }

    except Exception as e:
        logger.exception(f"Error in incremental HR reports update: {str(e)}")
        try:
            raise self.retry(exc=e, countdown=AGGREGATION_RETRY_DELAY * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            return {"success": False, "error": str(e)}
