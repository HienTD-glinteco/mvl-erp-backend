"""HR reports aggregation tasks.

This package contains Celery tasks for HR report aggregation:
- event_tasks: Event-driven incremental updates triggered by signals
- batch_tasks: Scheduled batch reconciliation tasks
- helpers: Helper functions for report aggregation
"""

from .batch_tasks import aggregate_hr_reports_batch
from .event_tasks import aggregate_hr_reports_for_work_history

__all__ = [
    "aggregate_hr_reports_for_work_history",
    "aggregate_hr_reports_batch",
]
