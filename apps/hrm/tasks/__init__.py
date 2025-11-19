"""HRM tasks module."""

# Import tasks for public API
from apps.hrm.tasks.attendances import sync_all_attendance_devices, sync_attendance_logs_for_device
from apps.hrm.tasks.certificates import update_certificate_statuses
from apps.hrm.tasks.reports_hr import aggregate_hr_reports_batch, aggregate_hr_reports_for_work_history
from apps.hrm.tasks.reports_recruitment import (
    aggregate_recruitment_reports_batch,
    aggregate_recruitment_reports_for_candidate,
)

from .timesheets import increment_available_leave_days

__all__ = [
    "sync_all_attendance_devices",
    "sync_attendance_logs_for_device",
    "update_certificate_statuses",
    "aggregate_hr_reports_for_work_history",
    "aggregate_hr_reports_batch",
    "aggregate_recruitment_reports_for_candidate",
    "aggregate_recruitment_reports_batch",
    "increment_available_leave_days",
]
