"""Event-driven Celery task for recruitment reports aggregation.

This module contains the event-driven task that fires whenever RecruitmentCandidate
changes (create, edit, status change, delete) via Django signals.
"""

import logging
from typing import Any, cast

from celery import shared_task

from .helpers import _increment_recruitment_reports

logger = logging.getLogger(__name__)


@shared_task(queue="reports_event")
def aggregate_recruitment_reports_for_candidate(action_type: str, snapshot: dict[str, Any]) -> None:
    """Business logic for recruitment event aggregation.

    Performs incremental updates to recruitment reports based on candidate events.

    Args:
        action_type: Type of action - "create", "update", or "delete"
        snapshot: Dict containing previous and current state
    """
    previous = snapshot.get("previous")
    current = snapshot.get("current")

    # Extract data from current or previous state and validate
    data = current if current is not None else previous
    status = None
    if isinstance(data, dict):
        data_dict = cast(dict[str, Any], data)
        status = data_dict.get("status")
    else:
        status = "unknown"

    logger.info(f"Incrementally updating recruitment reports for candidate (action: {action_type}, status: {status})")

    # Perform incremental updates
    _increment_recruitment_reports(action_type, snapshot)
