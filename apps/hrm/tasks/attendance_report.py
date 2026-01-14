import logging
from datetime import date, datetime

from celery import shared_task
from django.db import transaction
from django.db.models import F, Window
from django.db.models.functions import RowNumber

from apps.hrm.models import AttendanceDailyReport, AttendanceRecord, Employee
from apps.hrm.services.attendance_report import aggregate_attendance_daily_report

logger = logging.getLogger(__name__)


@shared_task(name="hrm.tasks.attendance_report.update_attendance_daily_report")
def update_attendance_daily_report_task(employee_id: int, report_date_str: str) -> None:
    """Update attendance daily report for a specific employee and date.

    Args:
        employee_id: ID of the employee
        report_date_str: Date string in YYYY-MM-DD format
    """
    try:
        report_date = datetime.strptime(report_date_str, "%Y-%m-%d").date()
        aggregate_attendance_daily_report(employee_id, report_date)
    except Exception as e:
        logger.exception(
            f"Error updating attendance daily report for employee {employee_id} on {report_date_str}: {e}"
        )


@shared_task(name="hrm.tasks.attendance_report.recalculate_daily_attendance_reports")
def recalculate_daily_attendance_reports_task(report_date_str: str | None = None) -> None:
    """Recalculate attendance daily reports for all employees for a specific date.

    Optimized to use bulk operations and window functions (via distinct on Postgres).

    Args:
        report_date_str: Date string in YYYY-MM-DD format (optional)
    """
    if report_date_str:
        try:
            report_date = datetime.strptime(report_date_str, "%Y-%m-%d").date()
        except ValueError:
            logger.error(f"Invalid date format: {report_date_str}")
            return
    else:
        report_date = date.today()

    logger.info(f"Starting batch recalculation of attendance daily reports for {report_date}")

    # 1. Fetch all valid attendance records for the date
    # Use distinct('employee_id') with order_by to get the first record per employee
    # This works on PostgreSQL and is equivalent to using a window function for this purpose
    qs = (
        AttendanceRecord.objects.filter(
            timestamp__date=report_date,
            is_valid=True,
            employee_id__isnull=False,
        )
        .select_related("attendance_geolocation")
        .annotate(
            row_number=Window(
                expression=RowNumber(),
                partition_by=[F("employee_id")],
                order_by=F("timestamp").asc(),
            )
        )
        .filter(row_number=1)
        .order_by("employee_id", "timestamp")
    )

    if not qs:
        logger.info(f"No attendance records found for {report_date}")
        return

    # 2. Fetch only relevant employees to get current org structure
    employee_ids = {r.employee_id for r in qs}
    employees = Employee.objects.in_bulk(employee_ids)

    new_reports = []

    for record in qs:
        if record.employee_id is None:
            continue

        employee = employees.get(record.employee_id)
        if not employee:
            continue

        project_id = None
        if record.attendance_geolocation:
            project_id = record.attendance_geolocation.project_id

        new_reports.append(
            AttendanceDailyReport(
                employee_id=record.employee_id,
                report_date=report_date,
                branch_id=employee.branch_id,
                block_id=employee.block_id,
                department_id=employee.department_id,
                project_id=project_id,
                attendance_method=record.attendance_type,
                attendance_record=record,
            )
        )

    # 3. Perform loop update/create inside a transaction
    with transaction.atomic():
        # Delete existing reports for this date - replaced with loop delete
        existing_reports = AttendanceDailyReport.objects.filter(report_date=report_date)
        for report in existing_reports:
            report.delete()

        for report in new_reports:
            report.save()

    logger.info(f"Recalculated reports for {len(new_reports)} employees on {report_date}")
