"""HRM tasks module."""

# Import tasks for public API
from apps.hrm.tasks.attendances import sync_all_attendance_devices, sync_attendance_logs_for_device
from apps.hrm.tasks.reports_hr import aggregate_hr_reports_batch, aggregate_hr_reports_for_work_history
from apps.hrm.tasks.reports_recruitment import (
    aggregate_recruitment_reports_batch,
    aggregate_recruitment_reports_for_candidate,
)

__all__ = [
    "sync_all_attendance_devices",
    "sync_attendance_logs_for_device",
    "aggregate_hr_reports_for_work_history",
    "aggregate_hr_reports_batch",
    "aggregate_recruitment_reports_for_candidate",
    "aggregate_recruitment_reports_batch",
]
