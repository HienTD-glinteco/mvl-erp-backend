import logging
from datetime import date

from apps.hrm.models import (
    AttendanceDailyReport,
    AttendanceRecord,
    Employee,
)

logger = logging.getLogger(__name__)


def aggregate_attendance_daily_report(employee_id: int, report_date: date) -> None:
    """Aggregate attendance data for a specific employee and date.

    Finds the first attendance record for the employee on the given date.
    Determines the organizational structure (branch, block, department) valid at that date.
    Creates or updates the AttendanceDailyReport.

    Args:
        employee_id: ID of the employee
        report_date: Date to aggregate
    """
    # Find all attendance records for the employee on the date
    records = (
        AttendanceRecord.objects.filter(
            employee_id=employee_id,
            timestamp__date=report_date,
            is_valid=True,
        )
        .select_related("attendance_geolocation")
        .order_by("timestamp")
    )

    first_record = records.first()

    if not first_record:
        # No attendance records, delete existing report if any
        AttendanceDailyReport.objects.filter(
            employee_id=employee_id,
            report_date=report_date,
        ).delete()
        return

    # Determine organization info at the time of report_date
    # Always use current employee data as it is the source of truth
    try:
        employee = Employee.objects.get(id=employee_id)
        branch_id = employee.branch_id
        block_id = employee.block_id
        department_id = employee.department_id
    except Employee.DoesNotExist:
        logger.error(f"Employee {employee_id} not found during aggregation")
        return

    # Determine project from attendance record's geolocation
    project_id = None
    if first_record.attendance_geolocation:
        project_id = first_record.attendance_geolocation.project_id

    # Create or update the report
    record, _ = AttendanceDailyReport.objects.get_or_create(
        employee_id=employee_id,
        report_date=report_date,
    )

    # Ensure record's attributes always be set using latest values.
    record.branch_id = branch_id
    record.block_id = block_id
    record.department_id = department_id
    record.project_id = project_id
    record.attendance_method = first_record.attendance_type
    record.attendance_record = first_record

    record.save()
