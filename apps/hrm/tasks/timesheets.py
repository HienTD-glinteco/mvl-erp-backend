"""Celery tasks for creating/updating timesheet entries and monthly aggregates.

This file contains two main tasks:
- prepare_monthly_timesheets: creates timesheet entries and monthly rows for all or a specific employee/month
- update_monthly_timesheet_async: refreshes monthly aggregates and clears need_refresh flags
"""

import logging
from datetime import date

from celery import shared_task
from django.db.models import F

from apps.hrm.models import Employee, EmployeeMonthlyTimesheet
from apps.hrm.services.timesheets import (
    create_entries_for_employee_month,
    create_entries_for_month_all,
    create_monthly_timesheet_for_employee,
    create_monthly_timesheets_for_month_all,
)

logger = logging.getLogger(__name__)


@shared_task
def prepare_monthly_timesheets(
    employee_id: int | None = None,
    year: int | None = None,
    month: int | None = None,
    increment_leave: bool = True,
):
    """Prepare timesheet entries and monthly rows either for a single employee or all active employees.

    Also handles incrementing available_leave_days for eligible employees when processing all employees.

    - If employee_id is None: create entries for all active employees for given year/month (defaults to current)
    - If employee_id provided: create entries for that employee and month
    - If increment_leave is True (default): increment available_leave_days by 1 for eligible employees
    """
    today = date.today()
    if not year or not month:
        year = today.year
        month = today.month

    if employee_id:
        create_entries_for_employee_month(employee_id, year, month)
        create_monthly_timesheet_for_employee(employee_id, year, month)
        return {"success": True, "employee_id": employee_id, "year": year, "month": month}

    # otherwise do for all employees
    create_entries_for_month_all(year, month)
    create_monthly_timesheets_for_month_all(year, month)

    # Increment available leave days for eligible employees
    # TODO: rework on this after SRS for available leave day is clear.
    updated_leave = 0
    if increment_leave:
        updated_leave = Employee.objects.filter(status__in=[Employee.Status.ACTIVE, Employee.Status.ONBOARDING]).update(
            available_leave_days=F("available_leave_days") + 1
        )
        logger.info("prepare_monthly_timesheets: incremented leave days for %s employees", updated_leave)

    return {"success": True, "employee_id": None, "year": year, "month": month, "leave_incremented": updated_leave}


@shared_task
def update_monthly_timesheet_async(
    employee_id: int | None = None, year: int | None = None, month: int | None = None, fields: list[str] | None = None
):
    """Refresh monthly timesheet rows. If employee/month not provided, process all rows with need_refresh=True.

    This task can be called by signals or scheduled periodically.
    """
    if employee_id and year and month:
        EmployeeMonthlyTimesheet.refresh_for_employee_month(employee_id, year, month, fields)
        return {"success": True, "employee_id": employee_id, "year": year, "month": month}

    # process all flagged rows
    qs = EmployeeMonthlyTimesheet.objects.filter(need_refresh=True)
    count = 0
    for row in qs.iterator():
        try:
            yr = row.report_date.year
            mo = row.report_date.month
            EmployeeMonthlyTimesheet.refresh_for_employee_month(row.employee_id, yr, mo, fields)
            row.need_refresh = False
            row.save(update_fields=["need_refresh"])
            count += 1
        except Exception as e:
            logger.exception("Failed to refresh monthly timesheet for %s: %s", row, e)
    return {"success": True, "processed": count}


@shared_task
def increment_available_leave_days():
    """DEPRECATED: Use prepare_monthly_timesheets with increment_leave=True instead.

    Monthly scheduled task: increment available_leave_days by 1 for eligible employees.
    Eligible employees: Status Active or Onboarding (not Resigned).

    This task has been merged into prepare_monthly_timesheets for better cohesion.
    """
    # TODO: rework on this after SRS for avaliable leave day is clear.
    updated = Employee.objects.filter(status__in=[Employee.Status.ACTIVE, Employee.Status.ONBOARDING]).update(
        available_leave_days=F("available_leave_days") + 1
    )
    logger.info("increment_available_leave_days: updated %s employees", updated)
    return {"success": True, "updated": updated}
