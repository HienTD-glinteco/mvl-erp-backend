from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.hrm.models import AttendanceRecord, Employee
from apps.hrm.services.timesheets import trigger_timesheet_updates_from_records

__all__ = ["handle_attendance_record_save", "handle_attendance_record_delete"]


@receiver(post_save, sender=AttendanceRecord)
def handle_attendance_record_save(sender, instance: AttendanceRecord, created, **kwargs):
    """Handle attendance record save event.

    When an attendance record is created or updated, update the corresponding TimeSheetEntry
    by setting start_time (if missing), end_time (latest), and recalculating hours.
    Also flag the monthly timesheet to need_refresh and schedule a task.

    Note: If a timesheet entry is marked as manually corrected (from approved proposals),
    this signal will not overwrite the times to preserve manual corrections.
    """
    # Match employee by attendance_code
    employee = Employee.objects.filter(attendance_code=instance.attendance_code).first()
    if not employee:
        return

    # Post-processing: Trigger timesheet updates (sinces bulk_create doesn't fire signals)
    trigger_timesheet_updates_from_records([instance])


@receiver(post_delete, sender=AttendanceRecord)
def handle_attendance_record_delete(sender, instance: AttendanceRecord, **kwargs):
    """Handle attendance record delete event.

    When attendance record is deleted, recalculate the timesheet entry for that date.
    """
    employee = Employee.objects.filter(attendance_code=instance.attendance_code).first()
    if not employee:
        return

    # Post-processing: Trigger timesheet updates (sinces bulk_create doesn't fire signals)
    trigger_timesheet_updates_from_records([instance])
