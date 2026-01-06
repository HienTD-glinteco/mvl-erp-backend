"""Event-driven Celery task for recruitment reports aggregation.

This module contains the event-driven task that fires whenever RecruitmentCandidate
changes (create, edit, status change, delete) via Django signals.
"""

import logging
from typing import Any

from celery import shared_task

from .helpers import _increment_recruitment_reports, _increment_returning_employee_reports

logger = logging.getLogger(__name__)


@shared_task(queue="reports_event")
def aggregate_recruitment_reports_for_candidate(action_type: str, snapshot: dict[str, Any]) -> None:
    """Business logic for recruitment event aggregation from work history.

    Performs incremental updates to recruitment reports based on work history events.
    Args:
        action_type: Type of action - "create", "update", or "delete"
        snapshot: Dict containing previous and current state
    """
    previous = snapshot.get("previous")
    current = snapshot.get("current")

    # Extract data from current or previous state and validate
    data = current if current is not None else previous
    if not isinstance(data, dict):
        logger.warning(f"Invalid snapshot payload for action {action_type}")
        return

    logger.info(f"Incrementally updating recruitment reports for work history (action: {action_type})")

    _increment_recruitment_reports(action_type, snapshot)


@shared_task(queue="reports_event")
def aggregate_recruitment_reports_for_work_history(action_type: str, snapshot: dict[str, Any]) -> None:
    """Business logic for recruitment event aggregation from work history.

    Performs incremental updates to recruitment reports based on work history RETURN_TO_WORK events.

    Args:
        action_type: Type of action - "create", "update", or "delete"
        snapshot: Dict containing previous and current state
    """
    previous = snapshot.get("previous")
    current = snapshot.get("current")

    # Extract data from current or previous state and validate
    data = current if current is not None else previous
    if not isinstance(data, dict):
        logger.warning(f"Invalid snapshot payload for action {action_type}")
        return

    logger.info(f"Incrementally updating recruitment reports for work history (action: {action_type})")

    # Perform incremental updates
    _increment_returning_employee_reports(action_type, snapshot)
