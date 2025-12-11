from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.hrm.models import AttendanceRecord
from apps.hrm.tasks.attendance_report import update_attendance_daily_report_task


@receiver(post_save, sender=AttendanceRecord)
def trigger_attendance_report_update_on_save(sender, instance, created, **kwargs):
    """Trigger attendance report update when an attendance record is saved."""
    if instance.employee_id and instance.timestamp:
        update_attendance_daily_report_task.apply_async(
            args=(
                instance.employee_id,
                instance.timestamp.date().strftime("%Y-%m-%d"),
            ),
            countdown=5,
        )


@receiver(post_delete, sender=AttendanceRecord)
def trigger_attendance_report_update_on_delete(sender, instance, **kwargs):
    """Trigger attendance report update when an attendance record is deleted."""
    if instance.employee_id and instance.timestamp:
        update_attendance_daily_report_task.apply_async(
            args=(
                instance.employee_id,
                instance.timestamp.date().strftime("%Y-%m-%d"),
            ),
            countdown=5,
        )
