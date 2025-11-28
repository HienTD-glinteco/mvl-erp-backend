"""HRM tasks module."""

# Import tasks for public API
from apps.hrm.tasks.attendance_report import (
    recalculate_daily_attendance_reports_task,
    update_attendance_daily_report_task,
)
from apps.hrm.tasks.attendances import sync_all_attendance_devices, sync_attendance_logs_for_device
from apps.hrm.tasks.certificates import update_certificate_statuses
from apps.hrm.tasks.contracts import check_contract_status
from apps.hrm.tasks.reports_hr import aggregate_hr_reports_batch, aggregate_hr_reports_for_work_history
from apps.hrm.tasks.reports_recruitment import (
    aggregate_recruitment_reports_batch,
    aggregate_recruitment_reports_for_candidate,
)

__all__ = [
    "sync_all_attendance_devices",
    "sync_attendance_logs_for_device",
    "update_attendance_daily_report_task",
    "recalculate_daily_attendance_reports_task",
    "update_certificate_statuses",
    "check_contract_status",
    "aggregate_hr_reports_for_work_history",
    "aggregate_hr_reports_batch",
    "aggregate_recruitment_reports_for_candidate",
    "aggregate_recruitment_reports_batch",
]
