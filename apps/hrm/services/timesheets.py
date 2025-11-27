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

    # Generate all dates for the month
    all_dates = [date(year, month, d) for d in range(1, last_day + 1)]

    # Find existing entries to avoid duplicates
    existing_dates = set(
        TimeSheetEntry.objects.filter(employee_id=employee_id, date__in=all_dates).values_list("date", flat=True)
    )

    # Create entries for dates that don't exist yet
    entries_to_create = [
        TimeSheetEntry(employee_id=employee_id, date=entry_date)
        for entry_date in all_dates
        if entry_date not in existing_dates
    ]

    if entries_to_create:
        created = TimeSheetEntry.objects.bulk_create(entries_to_create, ignore_conflicts=True)
        return list(created)

    return []


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
    """Create or initialize a monthly timesheet row for an employee.

    Behavior and business rules:
    - Ensure an `EmployeeMonthlyTimesheet` exists for the given employee and
        month. The row's `report_date` is the first day of the month.
    - If the row already exists, return it unchanged.
    - If the row is newly created, initialize certain fields with business logic,
        but do not perform any additional persistence beyond the `get_or_create` that
        created the row.

    Initialization rules when the row is created:
    - For January (month == 1):
        - Attempt to find the previous year's December timesheet and read its
            `remaining_leave_days`. If found, set `carried_over_leave` to that value,
            otherwise set to `DECIMAL_ZERO`.
        - Set `opening_balance_leave_days` to 1.0 day.
    - For months other than January:
        - If the previous month's timesheet exists, set
            `opening_balance_leave_days` to (prev.remaining_leave_days + 1.0).
        - If no previous monthly exists, set `opening_balance_leave_days` to 1.0.
        - Set `carried_over_leave` to `DECIMAL_ZERO`.

    Args:
        employee_id: Identifier of the employee for whom to create the timesheet.
        year: Optional year (defaults to today's year if None).
        month: Optional month (defaults to today's month if None).

    Returns:
        The `EmployeeMonthlyTimesheet` instance that exists after creation logic.
    """
    year, month = _normalize_year_month(year, month)
    report_date = date(year, month, 1)
    obj, created = EmployeeMonthlyTimesheet.objects.get_or_create(employee_id=employee_id, report_date=report_date)

    # If created, initialize these fields according to the business rules
    if not created:
        return obj

    # TODO: need to fetch maximum number of available leave days from current employee's contract to use it for validation.
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
