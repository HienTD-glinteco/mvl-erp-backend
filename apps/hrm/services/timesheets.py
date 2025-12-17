import logging
from calendar import monthrange
from datetime import date
from decimal import Decimal
from typing import List

from django.db import transaction
from django.db.models import Max, Min, Q, Sum

from apps.hrm.models import AttendanceRecord, Contract, Employee, EmployeeMonthlyTimesheet, TimeSheetEntry
from libs.decimals import DECIMAL_ZERO, quantize_decimal

logger = logging.getLogger(__name__)


def _normalize_year_month(year: int | None, month: int | None) -> tuple[int, int]:
    today = date.today()
    return (year or today.year, month or today.month)


@transaction.atomic
def create_entries_for_employee_month(
    employee_id: int, year: int | None = None, month: int | None = None
) -> List[TimeSheetEntry]:
    year, month = _normalize_year_month(year, month)
    _, last_day = monthrange(year, month)

    # Guard: ensure employee still exists to avoid FK violations when inserting
    if not Employee.objects.filter(pk=employee_id).exists():
        logger.warning("create_entries_for_employee_month: employee id %s not found, skipping", employee_id)
        return []

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


def calculate_generated_leave(employee_id: int, year: int, month: int) -> Decimal:
    """Calculate the leave days generated for the employee in the given month."""
    start_of_month = date(year, month, 1)
    _, last_day = monthrange(year, month)
    end_of_month = date(year, month, last_day)

    # Find active contract for the month
    contract = (
        Contract.objects.filter(
            employee_id=employee_id,
            status__in=[Contract.ContractStatus.ACTIVE, Contract.ContractStatus.ABOUT_TO_EXPIRE],
            effective_date__lte=end_of_month,
        )
        .filter(Q(expiration_date__isnull=True) | Q(expiration_date__gte=start_of_month))
        .first()
    )

    if not contract:
        return DECIMAL_ZERO

    # Check start date logic for partial months
    if contract.effective_date.year == year and contract.effective_date.month == month:
        if contract.effective_date.day > 1:
            return DECIMAL_ZERO

    # Calculate generated amount: annual_leave_days / 12
    generated = Decimal(contract.annual_leave_days) / Decimal(12)
    return quantize_decimal(generated)


def create_monthly_timesheet_for_employee(
    employee_id: int, year: int | None = None, month: int | None = None
) -> EmployeeMonthlyTimesheet | None:
    """Create or update a monthly timesheet row for an employee with leave balance calculations.

    This function updates `generated_leave_days`, `opening_balance_leave_days`, and
    `carried_over_leave` based on business rules:
    - Generated leave: Calculated from active contract (annual_leave_days / 12).
    - Opening/Carried/Remaining logic:
      - January: Carried = Dec(Prev).Remaining; Opening = 0.
      - April: Check for expiration of Carried Over leave (FIFO rule).
        Expired = Max(0, InitialCarried - Consumed(Jan-Mar)).
        Opening = Mar.Remaining - Expired.
      - Other months: Opening = Prev.Remaining; Carried = 0.

    Args:
        employee_id: Identifier of the employee.
        year: Optional year.
        month: Optional month.

    Returns:
        The updated `EmployeeMonthlyTimesheet` instance.
    """
    year, month = _normalize_year_month(year, month)
    report_date = date(year, month, 1)

    if not Employee.objects.filter(pk=employee_id).exists():
        logger.warning("create_monthly_timesheet_for_employee: employee id %s not found, skipping", employee_id)
        return None

    month_key = f"{year:04d}{month:02d}"
    obj, _ = EmployeeMonthlyTimesheet.objects.get_or_create(
        employee_id=employee_id, report_date=report_date, defaults={"month_key": month_key}
    )

    # 1. Generated Leave
    obj.generated_leave_days = calculate_generated_leave(employee_id, year, month)

    # 2. Opening & Carried
    if month == 1:
        prev = EmployeeMonthlyTimesheet.objects.filter(employee_id=employee_id, month_key=f"{year - 1:04d}12").first()
        carried = prev.remaining_leave_days if prev else DECIMAL_ZERO
        obj.carried_over_leave = quantize_decimal(carried)
        obj.opening_balance_leave_days = DECIMAL_ZERO
    elif month == 4:
        # April: Expire unused carried over
        prev = EmployeeMonthlyTimesheet.objects.filter(
            employee_id=employee_id, month_key=f"{year:04d}{month - 1:02d}"
        ).first()
        prev_remaining = prev.remaining_leave_days if prev else DECIMAL_ZERO

        # Get Initial Carried Over (from Jan)
        jan_ts = EmployeeMonthlyTimesheet.objects.filter(employee_id=employee_id, month_key=f"{year:04d}01").first()
        initial_carried = jan_ts.carried_over_leave if jan_ts else DECIMAL_ZERO

        # Get Total Consumed Jan-Mar
        consumed_jan_mar = (
            EmployeeMonthlyTimesheet.objects.filter(
                employee_id=employee_id, report_date__year=year, report_date__month__lt=4
            ).aggregate(total=Sum("consumed_leave_days"))["total"]
            or DECIMAL_ZERO
        )

        # Unused Carried Over
        unused_carried = max(initial_carried - consumed_jan_mar, DECIMAL_ZERO)

        # Opening Balance = Prev Remaining - Unused Carried
        obj.opening_balance_leave_days = quantize_decimal(max(prev_remaining - unused_carried, DECIMAL_ZERO))
        obj.carried_over_leave = DECIMAL_ZERO
    else:
        # Other months
        prev = EmployeeMonthlyTimesheet.objects.filter(
            employee_id=employee_id, month_key=f"{year:04d}{month - 1:02d}"
        ).first()
        opening = prev.remaining_leave_days if prev else DECIMAL_ZERO
        obj.opening_balance_leave_days = quantize_decimal(opening)
        obj.carried_over_leave = DECIMAL_ZERO

    # Update Remaining locally
    obj.remaining_leave_days = quantize_decimal(
        obj.carried_over_leave + obj.opening_balance_leave_days + obj.generated_leave_days - obj.consumed_leave_days
    )

    obj.save()

    return obj


def create_monthly_timesheets_for_month_all(
    year: int | None = None, month: int | None = None
) -> List[EmployeeMonthlyTimesheet]:
    year, month = _normalize_year_month(year, month)
    employees = Employee.objects.filter(status__in=[Employee.Status.ACTIVE, Employee.Status.ONBOARDING])
    created = []
    for emp in employees.iterator():
        result = create_monthly_timesheet_for_employee(emp.id, year, month)
        if result:
            created.append(result)
    return created


def update_start_end_times(attendance_code: str, timehsheet_entry: TimeSheetEntry):
    # Use aggregated values to determine start_time and end_time.
    # - If `first_ts` exists, use it for `start_time`.
    # - If no `last_ts` or `last_ts == first_ts`, set `end_time = None`.
    # - Otherwise set `end_time = last_ts`.

    agg = AttendanceRecord.objects.filter(
        attendance_code=attendance_code, timestamp__date=timehsheet_entry.date
    ).aggregate(first_ts=Min("timestamp"), last_ts=Max("timestamp"))

    first_ts = agg.get("first_ts")
    last_ts = agg.get("last_ts")

    check_in = first_ts if first_ts is not None else None

    if last_ts is None or last_ts == first_ts:
        check_out = None
    else:
        check_out = last_ts

    timehsheet_entry.check_in_time = check_in
    timehsheet_entry.check_out_time = check_out

    if not timehsheet_entry.is_manually_corrected:
        timehsheet_entry.update_times(check_in, check_out)

    timehsheet_entry.calculate_hours_from_schedule()
    timehsheet_entry.save()


def trigger_timesheet_updates_from_records(records: List[AttendanceRecord]) -> None:
    """Trigger timesheet updates for newly created attendance records.

    This mimics the logic in apps.hrm.signals.attendance.handle_attendance_record_save
    which is skipped during bulk_create.
    """
    # Identify unique (employee, date) pairs to update
    updates_needed = {}
    monthly_refreshes = set()

    for record in records:
        if not record.employee_id:
            continue

        # timestamp is a datetime object
        record_date = record.timestamp.date()
        key = (record.employee_id, record_date)

        # Store attendance_code to pass to update function
        # All records for same employee should have same attendance_code
        updates_needed[key] = record.attendance_code

        # Collect monthly refresh keys
        month_key = f"{record_date.year:04d}{record_date.month:02d}"
        monthly_refreshes.add((record.employee_id, month_key, record_date.replace(day=1)))

    # Process timesheet updates
    for (emp_id, rec_date), auth_code in updates_needed.items():
        try:
            entry, _ = TimeSheetEntry.objects.get_or_create(employee_id=emp_id, date=rec_date)
            update_start_end_times(auth_code, entry)
        except Exception as e:
            logger.error(f"Failed to update timesheet for employee {emp_id} on {rec_date}: {e}")

    # Process monthly refreshes
    for emp_id, month_key, report_date in monthly_refreshes:
        try:
            EmployeeMonthlyTimesheet.objects.get_or_create(
                employee_id=emp_id, month_key=month_key, report_date=report_date
            )[0].mark_refresh()
        except Exception as e:
            logger.error(f"Failed to mark monthly refresh for employee {emp_id} month {month_key}: {e}")
