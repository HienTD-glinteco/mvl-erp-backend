"""Event-driven Celery task for recruitment reports aggregation.

This module contains the event-driven task that fires whenever RecruitmentCandidate
changes (create, edit, status change, delete) via Django signals.
"""

import logging
from typing import Any

from ..report_framework import create_event_task
from .helpers import _increment_recruitment_reports

logger = logging.getLogger(__name__)


def _recruitment_event_aggregation(action_type: str, snapshot: dict[str, Any]) -> None:
    """Business logic for recruitment event aggregation.
    
    Performs incremental updates to recruitment reports based on candidate events.
    
    Args:
        action_type: Type of action - "create", "update", or "delete"
        snapshot: Dict containing previous and current state
    """
    previous = snapshot.get("previous")
    current = snapshot.get("current")

    # Extract data from current or previous state
    data = current if current else previous
    status = data.get('status') if data else 'unknown'

    logger.info(
        f"Incrementally updating recruitment reports for candidate "
        f"(action: {action_type}, status: {status})"
    )

    # Perform incremental updates
    _increment_recruitment_reports(action_type, snapshot)


# Create the actual Celery task using the framework
aggregate_recruitment_reports_for_candidate = create_event_task(
    task_name='aggregate_recruitment_reports_for_candidate',
    aggregation_function=_recruitment_event_aggregation,
    queue='reports_event'
)


