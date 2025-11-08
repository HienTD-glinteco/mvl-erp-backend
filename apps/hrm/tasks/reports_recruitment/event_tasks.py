"""Celery tasks for recruitment reports aggregation.

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from celery import shared_task
from django.db import models, transaction
from django.db.models import Count, F, Min, Q, Sum
from django.utils import timezone

from apps.hrm.constants import RecruitmentSourceType
from apps.hrm.models import (
    Block,
    Branch,
    Department,
    HiredCandidateReport,
    RecruitmentCandidate,
    RecruitmentChannel,
    RecruitmentChannelReport,
    RecruitmentCostReport,
    RecruitmentExpense,
    RecruitmentSource,
    RecruitmentSourceReport,
    StaffGrowthReport,
)

logger = logging.getLogger(__name__)

# Constants
AGGREGATION_MAX_RETRIES = 3
AGGREGATION_RETRY_DELAY = 60  # 1 minute
MAX_REPORT_LOOKBACK_DAYS = 365  # Maximum 1 year lookback for batch reports


from .helpers import _increment_recruitment_reports

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