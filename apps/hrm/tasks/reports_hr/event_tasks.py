"""Event-driven Celery task for HR reports aggregation.

This module contains the event-driven task that fires whenever EmployeeWorkHistory
changes (create, edit, delete) via Django signals.
"""

import logging
from typing import Any, cast

from celery import shared_task

from .helpers import (
    _increment_employee_status,
    _increment_staff_growth,
    _increment_employee_resigned_reason,
)

logger = logging.getLogger(__name__)


@shared_task(queue="reports_event")
def aggregate_hr_reports_for_work_history(action_type: str, snapshot: dict[str, Any]) -> None:
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

    # Extract data from current or previous state and validate
    data = current if current is not None else previous
    if not isinstance(data, dict):
        logger.warning(f"Invalid snapshot payload for action {action_type}")
        raise ValueError("Invalid snapshot payload")

    data_dict = cast(dict[str, Any], data)
    report_date = data_dict["date"]

    logger.info(f"Incrementally updating HR reports for work history (action: {action_type}, date: {report_date})")

    # Perform incremental updates
    _increment_staff_growth(action_type, snapshot)
    _increment_employee_status(action_type, snapshot)
    _increment_employee_resigned_reason(action_type, snapshot)
