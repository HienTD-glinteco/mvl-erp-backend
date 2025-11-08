"""Event-driven Celery task for recruitment reports aggregation.

This module contains the event-driven task that fires whenever RecruitmentCandidate
changes (create, edit, status change, delete) via Django signals.
"""

import logging
from typing import Any

from celery import shared_task
from django.db import transaction

from .helpers import (
    AGGREGATION_MAX_RETRIES,
    AGGREGATION_RETRY_DELAY,
    _increment_recruitment_reports,
)

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=AGGREGATION_MAX_RETRIES)
def aggregate_recruitment_reports_for_candidate(
    self, event_type: str, snapshot: dict[str, Any]
) -> dict[str, Any]:
    """Aggregate recruitment reports for a single candidate event (smart incremental update).

    This event-driven task uses snapshot data to avoid race conditions where the
    candidate record might be modified before the task processes.

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

        logger.info(
            f"Incrementally updating recruitment reports for candidate "
            f"(event: {event_type}, status: {data.get('status')})"
        )

        # Perform incremental update
        with transaction.atomic():
            _increment_recruitment_reports(event_type, snapshot)

        return {
            "success": True,
            "event_type": event_type,
        }

    except Exception as e:
        logger.exception(f"Error in incremental recruitment reports update: {str(e)}")
        try:
            raise self.retry(exc=e, countdown=AGGREGATION_RETRY_DELAY * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            return {"success": False, "error": str(e)}


