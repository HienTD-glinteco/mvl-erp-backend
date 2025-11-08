"""HR Reports Aggregation Tasks Package.

This package contains Celery tasks for aggregating HR reporting data into
StaffGrowthReport and EmployeeStatusBreakdownReport models.

Public API exports:
- aggregate_hr_reports_for_work_history: Event-driven task for work history changes
- aggregate_hr_reports_batch: Scheduled batch task for daily reconciliation
"""

from .batch_tasks import aggregate_hr_reports_batch
from .event_tasks import aggregate_hr_reports_for_work_history

__all__ = [
    "aggregate_hr_reports_for_work_history",
    "aggregate_hr_reports_batch",
]
