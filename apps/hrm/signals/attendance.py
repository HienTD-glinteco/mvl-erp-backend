
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.hrm.models import AttendanceRecord, Employee, EmployeeMonthlyTimesheet, TimeSheetEntry
from apps.hrm.tasks.timesheets import update_monthly_timesheet_async


@receiver(post_save, sender=AttendanceRecord)
def handle_attendance_record_save(sender, instance: AttendanceRecord, created, **kwargs):
    """Handle attendance record save event.

    When an attendance record is created or updated, update the corresponding TimeSheetEntry
    by setting start_time (if missing), end_time (latest), and recalculating hours.
    Also flag the monthly timesheet to need_refresh and schedule a task.
    """
    # Match employee by attendance_code
    employee = Employee.objects.filter(attendance_code=instance.attendance_code).first()
    if not employee:
        return

    # find or create timesheet entry for the date
    entry, _ = TimeSheetEntry.objects.get_or_create(employee_id=employee.id, date=instance.timestamp.date())

    if not entry.start_time or instance.timestamp < entry.start_time:
        entry.start_time = instance.timestamp
    if not entry.end_time or instance.timestamp > entry.end_time:
        entry.end_time = instance.timestamp

    # Calculate hours using the WorkSchedule integration
    entry.calculate_hours_from_schedule()

    entry.save()

    # Mark monthly timesheet for refresh
    yr = entry.date.year
    mo = entry.date.month
    month_key = f"{yr:04d}{mo:02d}"
    m_obj, _ = EmployeeMonthlyTimesheet.objects.get_or_create(
        employee=employee, month_key=month_key, report_date=entry.date.replace(day=1)
    )
    m_obj.need_refresh = True
    m_obj.save(update_fields=["need_refresh"])

    # schedule async update
    update_monthly_timesheet_async.delay(
        employee.id,
        yr,
        mo,
        [
            "probation_working_days",
            "official_working_days",
            "total_working_days",
            "total_worked_hours",
            "overtime_hours",
        ],
    )


@receiver(post_delete, sender=AttendanceRecord)
def handle_attendance_record_delete(sender, instance: AttendanceRecord, **kwargs):
    """Handle attendance record delete event.

    When attendance record is deleted, recalculate the timesheet entry for that date.
    """
    employee = Employee.objects.filter(attendance_code=instance.attendance_code).first()
    if not employee:
        return

    entry = TimeSheetEntry.objects.filter(employee=employee, date=instance.timestamp.date()).first()
    if not entry:
        return

    # Recompute timesheet entry: find all attendance records for that date and update entry
    records = AttendanceRecord.objects.filter(
        attendance_code=instance.attendance_code, timestamp__date=instance.timestamp.date()
    ).order_by("timestamp")

    first = records.first().timestamp
    last = records.last().timestamp

    entry.update_times(first, last)
    entry.calculate_hours_from_schedule()
    entry.save()

    # Mark monthly timesheet for refresh and schedule update
    yr = instance.timestamp.date().year
    mo = instance.timestamp.date().month

    m_obj = EmployeeMonthlyTimesheet.objects.filter(employee_id=employee.id, month_key=f"{yr:04d}{mo:02d}").first()
    if m_obj:
        m_obj.need_refresh = True
        m_obj.save(update_fields=["need_refresh"])
        update_monthly_timesheet_async.delay(
            employee.id,
            yr,
            mo,
            [
                "probation_working_days",
                "official_working_days",
                "total_working_days",
                "total_worked_hours",
                "overtime_hours",
            ],
        )
