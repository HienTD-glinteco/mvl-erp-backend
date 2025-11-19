from datetime import datetime
from decimal import Decimal

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from apps.hrm.models import AttendanceRecord, Employee, EmployeeMonthlyTimesheet, TimeSheetEntry
from apps.hrm.tasks.timesheets import update_monthly_timesheet_async


# TODO: switch to use WorkSchedule
def _split_hours_by_period(start: datetime, end: datetime) -> tuple[float, float]:
    """Split total hours between morning and afternoon based on noon boundary.

    Simple heuristic: split based on whether an interval crosses 12:00.
    """
    if not start or not end:
        return 0.0, 0.0

    # Convert to naive times (server tz aware) — assume timezone-aware datetimes
    tz = timezone.get_current_timezone()
    start = start.astimezone(tz)
    end = end.astimezone(tz)
    noon = start.replace(hour=12, minute=0, second=0, microsecond=0)

    if end <= start:
        return 0.0, 0.0

    total_seconds = (end - start).total_seconds()

    if end <= noon:
        # All in morning
        return total_seconds / 3600.0, 0.0
    if start >= noon:
        # All in afternoon
        return 0.0, total_seconds / 3600.0

    # Across noon: split
    morn_seconds = (noon - start).total_seconds()
    aft_seconds = (end - noon).total_seconds()
    return morn_seconds / 3600.0, aft_seconds / 3600.0


@receiver(post_save, sender=AttendanceRecord)
def handle_attendance_record_save(sender, instance: AttendanceRecord, created, **kwargs):
    # When an attendance record is created or updated, update the corresponding TimeSheetEntry
    # by setting start_time (if missing), end_time (latest), and recalculating hours.
    # Also flag the monthly timesheet to need_refresh and schedule a task.

    # Match employee by attendance_code
    employee = Employee.objects.filter(attendance_code=instance.attendance_code).first()
    if not employee:
        return

    # find or create timesheet entry for the date
    entry, _ = TimeSheetEntry.objects.get_or_create(employee_id=employee.id, date=instance.timestamp.date())

    # TODO: tạo method trong TimesheetEntry, thực hiện update start_time, end_time
    # Update start_time and end_time
    if not entry.start_time or instance.timestamp < entry.start_time:
        entry.start_time = instance.timestamp
    if not entry.end_time or instance.timestamp > entry.end_time:
        entry.end_time = instance.timestamp

    # compute morning/afternoon split
    # TODO: tạo method trong TimesheetEntry, thực hiện logic tính toán các giá trị morning hours, afternoon_hours, total_hours
    morning_hours, afternoon_hours = _split_hours_by_period(entry.start_time, entry.end_time)
    entry.morning_hours = entry._quantize(entry.morning_hours + Decimal(str(morning_hours)))
    entry.afternoon_hours = entry._quantize(entry.afternoon_hours + Decimal(str(afternoon_hours)))
    entry.total_hours = entry._quantize(entry.morning_hours + entry.afternoon_hours)

    entry.save()

    # Mark monthly timesheet for refresh
    yr = entry.date.year
    mo = entry.date.month
    month_key = f"{yr:04d}{mo:02d}"
    m_obj, _ = EmployeeMonthlyTimesheet.objects.get_or_create(
        employee=employee, month_key=month_key, report_date=entry.date.replace(day=1)
    )
    # TODO: tạo method trong monthly timesheet, thực hiện update need_refresh
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
    # When attendance record is deleted, we should recalculate the timesheet entry for that date.
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

    # TODO: tạo method trong TimesheetEntry, thực hiện update start_time, end_time
    # Update start_time and end_time
    entry.start_time = first
    entry.end_time = last
    morning_hours, afternoon_hours = _split_hours_by_period(first, last)
    entry.morning_hours = entry._quantize(morning_hours)
    entry.afternoon_hours = entry._quantize(afternoon_hours)
    entry.total_hours = entry._quantize(morning_hours + afternoon_hours)
    entry.save()

    # mark monthly timesheet need_refresh and schedule update
    yr = instance.timestamp.date().year
    mo = instance.timestamp.date().month

    m_obj = EmployeeMonthlyTimesheet.objects.filter(employee_id=employee.id, month_key=f"{yr:04d}{mo:02d}").first()
    if m_obj:
        # TODO: tạo method trong monthly timesheet, thực hiện update need_refresh
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
