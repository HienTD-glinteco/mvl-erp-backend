"""Recruitment reports aggregation tasks.

This package contains Celery tasks for recruitment report aggregation:
- event_tasks: Event-driven incremental updates triggered by signals
- batch_tasks: Scheduled batch reconciliation tasks
- helpers: Helper functions for report aggregation
"""

from .batch_tasks import aggregate_recruitment_reports_batch
from .event_tasks import aggregate_recruitment_reports_for_candidate

__all__ = [
    "aggregate_recruitment_reports_for_candidate",
    "aggregate_recruitment_reports_batch",
]
