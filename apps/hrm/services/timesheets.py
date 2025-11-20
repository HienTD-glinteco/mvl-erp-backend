from calendar import monthrange
from datetime import date
from typing import List

from django.db import transaction

from apps.hrm.models import Employee, EmployeeMonthlyTimesheet, TimeSheetEntry
from libs.decimals import DECIMAL_ZERO, quantize_decimal


def _normalize_year_month(year: int | None, month: int | None) -> tuple[int, int]:
    today = date.today()
    return (year or today.year, month or today.month)


@transaction.atomic
def create_entries_for_employee_month(
    employee_id: int, year: int | None = None, month: int | None = None
) -> List[TimeSheetEntry]:
    year, month = _normalize_year_month(year, month)
    _, last_day = monthrange(year, month)
    created = []

    for d in range(1, last_day + 1):
        entry_date = date(year, month, d)
        obj, was_created = TimeSheetEntry.objects.get_or_create(employee_id=employee_id, date=entry_date)
        if was_created:
            created.append(obj)

    return created


def create_entries_for_month_all(year: int | None = None, month: int | None = None) -> List[TimeSheetEntry]:
    year, month = _normalize_year_month(year, month)
    created = []
    employees = Employee.objects.filter(status__in=[Employee.Status.ACTIVE, Employee.Status.ONBOARDING])
    for emp in employees.iterator():
        created.extend(create_entries_for_employee_month(emp.id, year, month))
    return created


def create_monthly_timesheet_for_employee(
    employee_id: int, year: int | None = None, month: int | None = None
) -> EmployeeMonthlyTimesheet:
    year, month = _normalize_year_month(year, month)
    report_date = date(year, month, 1)
    obj, created = EmployeeMonthlyTimesheet.objects.get_or_create(employee_id=employee_id, report_date=report_date)

    # If created, initialize these fields according to the business rules
    if not created:
        return obj

    if month == 1:
        # attempt to get previous year's December remaining
        prev = EmployeeMonthlyTimesheet.objects.filter(employee_id=employee_id, month_key=f"{year - 1:04d}12").first()
        carried = prev.remaining_leave_days if prev else DECIMAL_ZERO
        obj.carried_over_leave = quantize_decimal(carried)
        obj.opening_balance_leave_days = quantize_decimal(1)
    else:
        prev = EmployeeMonthlyTimesheet.objects.filter(
            employee_id=employee_id, month_key=f"{year:04d}{month - 1:02d}"
        ).first()
        opening = (prev.remaining_leave_days + quantize_decimal(1)) if prev else quantize_decimal(1)
        obj.opening_balance_leave_days = quantize_decimal(opening)
        obj.carried_over_leave = quantize_decimal(DECIMAL_ZERO)

    return obj


def create_monthly_timesheets_for_month_all(
    year: int | None = None, month: int | None = None
) -> List[EmployeeMonthlyTimesheet]:
    year, month = _normalize_year_month(year, month)
    employees = Employee.objects.filter(status__in=[Employee.Status.ACTIVE, Employee.Status.ONBOARDING])
    created = []
    for emp in employees.iterator():
        created.append(create_monthly_timesheet_for_employee(emp.id, year, month))
    return created
