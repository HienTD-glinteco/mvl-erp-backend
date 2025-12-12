import logging
from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Tuple

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.hrm.constants import (
    ProposalStatus,
    ProposalType,
    ProposalWorkShift,
    TimesheetReason,
    TimesheetStatus,
)
from apps.hrm.models import Contract, Employee, EmployeeMonthlyTimesheet, TimeSheetEntry
from apps.hrm.models.holiday import CompensatoryWorkday, Holiday
from apps.hrm.models.proposal import Proposal
from apps.hrm.utils.work_schedule_cache import get_work_schedule_by_weekday
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
        obj.carried_over_leave
        + obj.opening_balance_leave_days
        + obj.generated_leave_days
        - obj.consumed_leave_days
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


# ---------------------------------------------------------------------------
# Timesheet status calculation service
# ---------------------------------------------------------------------------


def _determine_sessions(work_schedule, compensatory, half_day_shift):
    has_morning = bool(work_schedule and work_schedule.morning_start_time and work_schedule.morning_end_time)
    has_afternoon = bool(work_schedule and work_schedule.afternoon_start_time and work_schedule.afternoon_end_time)

    if compensatory:
        # compensatory overrides: mark as working according to session
        if compensatory.session == CompensatoryWorkday.Session.FULL_DAY:
            has_morning = True
            has_afternoon = True
        elif compensatory.session == CompensatoryWorkday.Session.MORNING:
            has_morning = True
            has_afternoon = False
        else:
            has_morning = False
            has_afternoon = True

    # half-day proposal overrides
    if half_day_shift == ProposalWorkShift.MORNING:
        has_morning = False
        has_afternoon = True
    elif half_day_shift == ProposalWorkShift.AFTERNOON:
        has_morning = True
        has_afternoon = False

    return has_morning, has_afternoon


def _handle_full_day_leaves(entry, paid, unpaid, maternity) -> bool:
    if paid or unpaid or maternity:
        entry.status = TimesheetStatus.ABSENT
        if maternity:
            entry.absent_reason = TimesheetReason.MATERNITY_LEAVE
        elif unpaid:
            entry.absent_reason = TimesheetReason.UNPAID_LEAVE
        else:
            entry.absent_reason = TimesheetReason.PAID_LEAVE
        entry.count_for_payroll = False
        return True
    return False


def _handle_non_working_day(entry, day_defined_as_working, times_outside_schedule, is_holiday) -> bool:
    non_working_day = (not day_defined_as_working) or times_outside_schedule or is_holiday
    if non_working_day:
        if not entry.start_time:
            entry.status = None
        else:
            entry.status = TimesheetStatus.ON_TIME
        return True
    return False


def _handle_single_punch(entry) -> bool:
    if (entry.start_time and not entry.end_time) or (not entry.start_time and entry.end_time):
        entry.status = TimesheetStatus.NOT_ON_TIME
        return True
    return False


def _evaluate_work_duration(entry, work_schedule, has_morning, has_afternoon, allowed_late_minutes):
    def _make(dt_time):
        return timezone.make_aware(datetime.combine(entry.date, dt_time)) if dt_time else None

    m_start = _make(work_schedule.morning_start_time) if work_schedule else None
    m_end = _make(work_schedule.morning_end_time) if work_schedule else None
    a_start = _make(work_schedule.afternoon_start_time) if work_schedule else None
    a_end = _make(work_schedule.afternoon_end_time) if work_schedule else None

    scheduled_seconds = 0.0
    if has_morning and m_start and m_end:
        scheduled_seconds += (m_end - m_start).total_seconds()
    if has_afternoon and a_start and a_end:
        scheduled_seconds += (a_end - a_start).total_seconds()

    break_seconds = 0.0
    if m_end and a_start:
        break_seconds = (a_start - m_end).total_seconds()

    if not entry.end_time:
        entry.status = TimesheetStatus.NOT_ON_TIME
        return

    actual_work_seconds = (entry.end_time - entry.start_time).total_seconds() - break_seconds
    allowed_seconds = allowed_late_minutes * 60

    if scheduled_seconds - actual_work_seconds > allowed_seconds:
        entry.status = TimesheetStatus.NOT_ON_TIME
    else:
        entry.status = TimesheetStatus.ON_TIME


def compute_timesheet_status(entry) -> None:
    """Compute and set `entry.status`, `entry.absent_reason`, and `entry.count_for_payroll`.

    This function is behavior-preserving with the previous `TimeSheetEntry.calculate_status`.
    It intentionally accepts a `TimeSheetEntry` instance to avoid importing the model here
    (prevents circular imports when the model imports this service).
    """
    # gather base inputs
    weekday = entry.date.isoweekday() + 1
    work_schedule = get_work_schedule_by_weekday(weekday)
    is_holiday = Holiday.objects.filter(start_date__lte=entry.date, end_date__gte=entry.date).exists()
    compensatory = CompensatoryWorkday.objects.filter(date=entry.date).first()
    compensatory_day = compensatory is not None

    (
        has_full_day_paid_leave,
        has_full_day_unpaid_leave,
        has_maternity_leave,
        late_exemption_minutes,
        half_day_shift,
    ) = _fetch_approved_proposals_flags_for_entry(entry)

    # preserve externally-set absent (early exit)
    if _preserve_explicit_absent(entry):
        return

    # determine which sessions are defined for this date
    has_morning, has_afternoon = _determine_sessions(work_schedule, compensatory, half_day_shift)

    # handle full-day leaves
    if _handle_full_day_leaves(entry, has_full_day_paid_leave, has_full_day_unpaid_leave, has_maternity_leave):
        return

    # non-working day or attendance outside scheduled sessions
    times_outside_schedule = _is_attendance_outside_schedule_for_entry(entry, work_schedule, compensatory_day)
    if _handle_non_working_day(entry, has_morning or has_afternoon, times_outside_schedule, is_holiday):
        return

    # working day: require start_time
    if not entry.start_time:
        entry.status = TimesheetStatus.ABSENT
        return

    # single-punch detection
    if _handle_single_punch(entry):
        return

    base_start_time = _determine_base_start_time_for_entry(work_schedule, has_morning, has_afternoon)

    # if we don't have a concrete base start time, attempt compensatory fallback
    if base_start_time is None:
        if compensatory_day and (has_morning or has_afternoon):
            if _compensatory_fallback_punctuality_for_entry(entry, late_exemption_minutes, has_maternity_leave):
                return
            entry.status = TimesheetStatus.ON_TIME
            return

        if not work_schedule:
            entry.status = None if not entry.start_time else TimesheetStatus.ON_TIME
            return

        if not entry.status:
            entry.status = TimesheetStatus.ABSENT
        return

    # Determine allowed lateness
    schedule_allowed = (
        work_schedule.allowed_late_minutes if work_schedule and work_schedule.allowed_late_minutes is not None else 5
    )
    allowed_late_minutes = max(schedule_allowed, late_exemption_minutes or 0)
    if has_maternity_leave:
        allowed_late_minutes = max(allowed_late_minutes, 60)

    allowed_start_time = timezone.make_aware(datetime.combine(entry.date, base_start_time)) + timedelta(
        minutes=allowed_late_minutes
    )

    if entry.start_time <= allowed_start_time:
        entry.status = TimesheetStatus.ON_TIME
        return

    # Fall through to evaluate actual worked seconds vs scheduled seconds
    _evaluate_work_duration(entry, work_schedule, has_morning, has_afternoon, allowed_late_minutes)


def _fetch_approved_proposals_flags_for_entry(entry) -> Tuple[bool, bool, bool, int, object]:
    approved_proposals = _get_approved_proposals_for_entry(entry)
    return _aggregate_proposal_flags(approved_proposals, entry)


def _get_approved_proposals_for_entry(entry):
    """Return queryset of approved proposals that may affect the given entry date."""
    if not getattr(entry, "employee_id", None):
        return Proposal.objects.none()

    return Proposal.objects.filter(created_by_id=entry.employee_id, proposal_status=ProposalStatus.APPROVED).filter(
        Q(paid_leave_start_date__lte=entry.date, paid_leave_end_date__gte=entry.date)
        | Q(unpaid_leave_start_date__lte=entry.date, unpaid_leave_end_date__gte=entry.date)
        | Q(maternity_leave_start_date__lte=entry.date, maternity_leave_end_date__gte=entry.date)
        | Q(late_exemption_start_date__lte=entry.date, late_exemption_end_date__gte=entry.date)
    )


def _aggregate_proposal_flags(approved_proposals, entry) -> Tuple[bool, bool, bool, int, object]:
    """Aggregate approved proposals into flags used by the timesheet calculation.

    Returns: (has_full_day_paid_leave, has_full_day_unpaid_leave, has_maternity_leave,
              late_exemption_minutes, half_day_shift)
    """
    has_full_day_paid_leave = False
    has_full_day_unpaid_leave = False
    has_maternity_leave = False
    late_exemption_minutes = 0
    half_day_shift = None

    for p in approved_proposals:
        if p.proposal_type == ProposalType.PAID_LEAVE and p.paid_leave_start_date and p.paid_leave_end_date:
            if p.paid_leave_start_date <= entry.date <= p.paid_leave_end_date:
                if not p.paid_leave_shift or p.paid_leave_shift == ProposalWorkShift.FULL_DAY:
                    has_full_day_paid_leave = True
                else:
                    half_day_shift = p.paid_leave_shift

        if p.proposal_type == ProposalType.UNPAID_LEAVE and p.unpaid_leave_start_date and p.unpaid_leave_end_date:
            if p.unpaid_leave_start_date <= entry.date <= p.unpaid_leave_end_date:
                if not p.unpaid_leave_shift or p.unpaid_leave_shift == ProposalWorkShift.FULL_DAY:
                    has_full_day_unpaid_leave = True
                else:
                    half_day_shift = p.unpaid_leave_shift

        if (
            p.proposal_type == ProposalType.MATERNITY_LEAVE
            and p.maternity_leave_start_date
            and p.maternity_leave_end_date
        ):
            if p.maternity_leave_start_date <= entry.date <= p.maternity_leave_end_date:
                has_maternity_leave = True

        if (
            p.proposal_type == ProposalType.LATE_EXEMPTION
            and p.late_exemption_start_date
            and p.late_exemption_end_date
        ):
            if p.late_exemption_start_date <= entry.date <= p.late_exemption_end_date and p.late_exemption_minutes:
                late_exemption_minutes = max(late_exemption_minutes, p.late_exemption_minutes)

    return (
        has_full_day_paid_leave,
        has_full_day_unpaid_leave,
        has_maternity_leave,
        late_exemption_minutes,
        half_day_shift,
    )


def _preserve_explicit_absent(entry) -> bool:
    if (
        entry.absent_reason
        in (TimesheetReason.PAID_LEAVE, TimesheetReason.UNPAID_LEAVE, TimesheetReason.MATERNITY_LEAVE)
        or entry.status == TimesheetStatus.ABSENT
    ):
        entry.count_for_payroll = False
        return True
    return False


def _is_attendance_outside_schedule_for_entry(entry, work_schedule, compensatory_day) -> bool:
    if (not compensatory_day) and work_schedule and entry.start_time and entry.end_time:

        def _make(dt_time):
            return timezone.make_aware(datetime.combine(entry.date, dt_time)) if dt_time else None

        m_start = _make(work_schedule.morning_start_time)
        m_end = _make(work_schedule.morning_end_time)
        a_start = _make(work_schedule.afternoon_start_time)
        a_end = _make(work_schedule.afternoon_end_time)

        within_morning = False
        within_afternoon = False
        if m_start and m_end:
            within_morning = not (entry.end_time <= m_start or entry.start_time >= m_end)
        if a_start and a_end:
            within_afternoon = not (entry.end_time <= a_start or entry.start_time >= a_end)

        return not (within_morning or within_afternoon)
    return False


def _determine_base_start_time_for_entry(work_schedule, has_morning, has_afternoon):
    if not work_schedule:
        return None
    if has_morning and getattr(work_schedule, "morning_start_time", None):
        return work_schedule.morning_start_time
    if has_afternoon and getattr(work_schedule, "afternoon_start_time", None):
        return work_schedule.afternoon_start_time
    if getattr(work_schedule, "morning_start_time", None):
        return work_schedule.morning_start_time
    if getattr(work_schedule, "afternoon_start_time", None):
        return work_schedule.afternoon_start_time
    return None


def _compensatory_fallback_punctuality_for_entry(
    entry, late_exemption_minutes: int, has_maternity_leave: bool
) -> bool:
    fallback_start = None
    fallback_allowed = 0
    for wd in range(2, 7):
        fallback = get_work_schedule_by_weekday(wd)
        if not fallback:
            continue
        if getattr(fallback, "morning_start_time", None):
            fallback_start = fallback.morning_start_time
            fallback_allowed = fallback.allowed_late_minutes or 0
            break
        if getattr(fallback, "afternoon_start_time", None):
            fallback_start = fallback.afternoon_start_time
            fallback_allowed = fallback.allowed_late_minutes or 0
            break

    if fallback_start is not None:
        fallback_allowed_final = max(fallback_allowed or 5, late_exemption_minutes or 0)
        if has_maternity_leave:
            fallback_allowed_final = max(fallback_allowed_final, 60)

        allowed_start_time = timezone.make_aware(datetime.combine(entry.date, fallback_start)) + timedelta(
            minutes=fallback_allowed_final
        )
        if entry.start_time <= allowed_start_time:
            entry.status = TimesheetStatus.ON_TIME
        else:
            entry.status = TimesheetStatus.NOT_ON_TIME
        return True
    return False
