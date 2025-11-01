"""HRM tasks module."""

# Import tasks for public API
from apps.hrm.tasks.attendances import sync_all_attendance_devices, sync_attendance_logs_for_device

__all__ = [
    "sync_all_attendance_devices",
    "sync_attendance_logs_for_device",
]
