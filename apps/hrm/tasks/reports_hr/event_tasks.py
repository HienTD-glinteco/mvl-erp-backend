"""Event-driven Celery task for HR reports aggregation.

This module contains the event-driven task that fires whenever EmployeeWorkHistory
changes (create, edit, delete) via Django signals.
"""

import logging
from typing import Any

from ..report_framework import create_event_task
from .helpers import (
    _increment_employee_status,
    _increment_staff_growth,
)

logger = logging.getLogger(__name__)


def _hr_event_aggregation(action_type: str, snapshot: dict[str, Any]) -> None:
    """Business logic for HR event aggregation.
    
    Performs incremental updates to HR reports based on work history events.
    
    Args:
        action_type: Type of action - "create", "update", or "delete"
        snapshot: Dict containing previous and current state
    """
    previous = snapshot.get("previous")
    current = snapshot.get("current")

    if not previous and not current:
        logger.warning(f"Invalid snapshot for action {action_type}")
        raise ValueError("Invalid snapshot: both previous and current are None")

    # Extract data from current or previous state
    data = current if current else previous
    report_date = data["date"]

    logger.info(
        f"Incrementally updating HR reports for work history "
        f"(action: {action_type}, date: {report_date})"
    )

    # Perform incremental updates
    _increment_staff_growth(action_type, snapshot)
    _increment_employee_status(action_type, snapshot)


# Create the actual Celery task using the framework
aggregate_hr_reports_for_work_history = create_event_task(
    task_name='aggregate_hr_reports_for_work_history',
    aggregation_function=_hr_event_aggregation,
    queue='reports_event'
)
