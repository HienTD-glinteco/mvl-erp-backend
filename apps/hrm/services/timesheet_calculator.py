import logging
from datetime import timedelta
from decimal import Decimal
from fractions import Fraction
from typing import Optional, Tuple

from django.db.models import Q

from apps.hrm.constants import (
    STANDARD_WORKING_HOURS_PER_DAY,
    EmployeeType,
    ProposalStatus,
    ProposalType,
    ProposalWorkShift,
    TimesheetReason,
    TimesheetStatus,
)
from apps.hrm.models.contract import Contract
from apps.hrm.models.contract_type import ContractType
from apps.hrm.models.employee import Employee
from apps.hrm.models.holiday import CompensatoryWorkday
from apps.hrm.models.proposal import Proposal, ProposalOvertimeEntry
from apps.hrm.models.timesheet import TimeSheetEntry
from apps.hrm.models.work_schedule import WorkSchedule
from apps.hrm.utils.work_schedule_cache import get_work_schedule_by_weekday
from libs.datetimes import combine_datetime, compute_intersection_hours
from libs.decimals import quantize_decimal

logger = logging.getLogger(__name__)


class TimesheetCalculator:
    """Calculator for timesheet entry logic.

    Encapsulates logic for:
    - Calculating work duration (morning, afternoon, overtime, total).
    - Determining timesheet status (on time, late, absent, etc.).
    - Computing working days (for payroll).
    - Setting full salary flag based on contract.
    """

    def __init__(self, entry: "TimeSheetEntry"):
        self.entry = entry

    def compute_all(self) -> None:
        """Run all calculations for the entry."""
        self.calculate_hours()
        self.compute_status()
        self.compute_working_days()
        self.set_is_full_salary_from_contract()

    # ---------------------------------------------------------------------------
    # Hours Calculation
    # ---------------------------------------------------------------------------

    def calculate_hours(self, work_schedule: Optional["WorkSchedule"] = None) -> None:
        """Calculate morning_hours, afternoon_hours, and overtime_hours based on WorkSchedule.

        Moves logic from TimeSheetEntry.calculate_hours_from_schedule.
        """
        if work_schedule is None:
            # Convert Python's isoweekday (1=Monday, 7=Sunday) to WorkSchedule.Weekday (2=Monday, 8=Sunday)
            if self.entry.date:
                weekday = self.entry.date.isoweekday() + 1
                work_schedule = get_work_schedule_by_weekday(weekday)

        if not self.entry.start_time:
            self._reset_hours()
            return

        # TODO: implement case missing end time (from original code comment)
        if not self.entry.end_time:
            self._reset_hours()
            return

        self._compute_scheduled_hours(work_schedule)
        self._compute_overtime_hours(work_schedule)
        self._finalize_hour_fields()

    def _reset_hours(self) -> None:
        self.entry.morning_hours = Decimal("0.00")
        self.entry.afternoon_hours = Decimal("0.00")
        self.entry.overtime_hours = Decimal("0.00")

    def _compute_scheduled_hours(self, work_schedule: Optional["WorkSchedule"]) -> None:
        work_date = self.entry.date
        start = self.entry.start_time
        end = self.entry.end_time

        morning_hours = Fraction(0)
        afternoon_hours = Fraction(0)

        if work_schedule:
            morning_start, morning_end, afternoon_start, afternoon_end = self._get_schedule_times(
                work_schedule, work_date
            )

            if morning_start and morning_end:
                morning_hours = compute_intersection_hours(start, end, morning_start, morning_end)

            if afternoon_start and afternoon_end:
                afternoon_hours = compute_intersection_hours(start, end, afternoon_start, afternoon_end)

        # Store as Fractions for now, will quantize later
        self._temp_morning_hours = morning_hours
        self._temp_afternoon_hours = afternoon_hours

    def _compute_overtime_hours(self, work_schedule: Optional["WorkSchedule"]) -> None:
        overtime_hours = Fraction(0)
        start = self.entry.start_time
        end = self.entry.end_time
        work_date = self.entry.date

        morning_start, morning_end, afternoon_start, afternoon_end = (None, None, None, None)
        if work_schedule:
            morning_start, morning_end, afternoon_start, afternoon_end = self._get_schedule_times(
                work_schedule, work_date
            )

        approved_overtime_entries = ProposalOvertimeEntry.objects.filter(
            proposal__created_by=self.entry.employee_id,
            proposal__proposal_status=ProposalStatus.APPROVED,
            date=self.entry.date,
        )

        for entry in approved_overtime_entries:
            ot_start = combine_datetime(work_date, entry.start_time)
            ot_end = combine_datetime(work_date, entry.end_time)

            raw_ot_hours = compute_intersection_hours(start, end, ot_start, ot_end)

            overlap_morning = Fraction(0)
            overlap_afternoon = Fraction(0)

            effective_ot_start = max(start, ot_start)
            effective_ot_end = min(end, ot_end)

            if effective_ot_start < effective_ot_end:
                if morning_start and morning_end:
                    overlap_morning = compute_intersection_hours(
                        effective_ot_start, effective_ot_end, morning_start, morning_end
                    )
                if afternoon_start and afternoon_end:
                    overlap_afternoon = compute_intersection_hours(
                        effective_ot_start, effective_ot_end, afternoon_start, afternoon_end
                    )

            overtime_hours += raw_ot_hours - overlap_morning - overlap_afternoon

        self._temp_overtime_hours = overtime_hours

    def _finalize_hour_fields(self) -> None:
        m = self._temp_morning_hours
        a = self._temp_afternoon_hours
        o = self._temp_overtime_hours

        self.entry.morning_hours = quantize_decimal(Decimal(m.numerator) / Decimal(m.denominator))
        self.entry.afternoon_hours = quantize_decimal(Decimal(a.numerator) / Decimal(a.denominator))
        self.entry.overtime_hours = quantize_decimal(Decimal(o.numerator) / Decimal(o.denominator))

    def _get_schedule_times(self, work_schedule, work_date):
        morning_start = (
            combine_datetime(work_date, work_schedule.morning_start_time) if work_schedule.morning_start_time else None
        )
        morning_end = (
            combine_datetime(work_date, work_schedule.morning_end_time) if work_schedule.morning_end_time else None
        )
        afternoon_start = (
            combine_datetime(work_date, work_schedule.afternoon_start_time)
            if work_schedule.afternoon_start_time
            else None
        )
        afternoon_end = (
            combine_datetime(work_date, work_schedule.afternoon_end_time) if work_schedule.afternoon_end_time else None
        )
        return morning_start, morning_end, afternoon_start, afternoon_end

    # ---------------------------------------------------------------------------
    # Status Calculation
    # ---------------------------------------------------------------------------

    def compute_status(self) -> None:
        """Compute and set `entry.status`, `entry.absent_reason`, and `entry.count_for_payroll`."""
        entry = self.entry
        weekday = entry.date.isoweekday() + 1
        work_schedule = get_work_schedule_by_weekday(weekday)

        is_compensatory = entry.is_compensatory
        is_holiday = entry.is_holiday

        compensatory = None
        if is_compensatory:
            compensatory = CompensatoryWorkday.objects.filter(date=entry.date).first()

        self._set_payroll_count_flag()

        (
            has_full_day_paid_leave,
            has_full_day_unpaid_leave,
            has_maternity_leave,
            late_exemption_minutes,
            half_day_shift,
        ) = self._fetch_approved_proposals_flags()

        if self._preserve_explicit_absent():
            return

        has_morning, has_afternoon = self._determine_sessions(work_schedule, compensatory, half_day_shift)

        if self._handle_full_day_leaves(has_full_day_paid_leave, has_full_day_unpaid_leave, has_maternity_leave):
            return

        if self._handle_single_punch():
            return

        times_outside_schedule = self._is_attendance_outside_schedule(work_schedule, is_compensatory)
        if self._handle_non_working_day(has_morning or has_afternoon, times_outside_schedule, is_holiday):
            return

        if self._handle_absent_no_start_time():
            return

        base_start_time = self._determine_base_start_time(work_schedule, has_morning, has_afternoon)

        if base_start_time is None:
            self._handle_no_base_start_time(
                is_compensatory,
                has_morning,
                has_afternoon,
                late_exemption_minutes,
                has_maternity_leave,
                work_schedule,
            )
            return

        allowed_late_minutes = self._calculate_allowed_late_minutes(
            work_schedule, late_exemption_minutes, has_maternity_leave
        )

        self._determine_punctuality(base_start_time, allowed_late_minutes, work_schedule, has_morning, has_afternoon)

    def _handle_absent_no_start_time(self) -> bool:
        if not self.entry.start_time:
            self.entry.status = TimesheetStatus.ABSENT
            return True
        return False

    def _handle_no_base_start_time(
        self,
        compensatory_day,
        has_morning,
        has_afternoon,
        late_exemption_minutes,
        has_maternity_leave,
        work_schedule,
    ) -> None:
        if compensatory_day and (has_morning or has_afternoon):
            if self._compensatory_fallback_punctuality(
                late_exemption_minutes, has_maternity_leave, has_morning, has_afternoon
            ):
                return
            self.entry.status = TimesheetStatus.ON_TIME
            return

        if not work_schedule:
            self.entry.status = None if not self.entry.start_time else TimesheetStatus.ON_TIME
            return

        if not self.entry.status:
            self.entry.status = TimesheetStatus.ABSENT

    def _calculate_allowed_late_minutes(self, work_schedule, late_exemption_minutes, has_maternity_leave) -> int:
        schedule_allowed = (
            work_schedule.allowed_late_minutes
            if work_schedule and work_schedule.allowed_late_minutes is not None
            else 5
        )
        allowed_late_minutes = max(schedule_allowed, late_exemption_minutes or 0)
        if has_maternity_leave:
            allowed_late_minutes = max(allowed_late_minutes, 60)
        return allowed_late_minutes

    def _determine_punctuality(
        self, base_start_time, allowed_late_minutes, work_schedule, has_morning, has_afternoon
    ) -> None:
        allowed_start_time = combine_datetime(self.entry.date, base_start_time) + timedelta(
            minutes=allowed_late_minutes
        )

        if self.entry.start_time <= allowed_start_time:
            self.entry.status = TimesheetStatus.ON_TIME
            return

        self._evaluate_work_duration(work_schedule, has_morning, has_afternoon, allowed_late_minutes)

    def _set_payroll_count_flag(self) -> None:
        """Determine default `count_for_payroll` based on employee classification."""
        try:
            emp_obj = getattr(self.entry, "employee", None)
            if emp_obj is not None:
                emp_type_val = emp_obj.employee_type
            else:
                emp_type_val = (
                    Employee.objects.filter(pk=self.entry.employee_id).values_list("employee_type", flat=True).first()
                )
        except Exception:
            emp_type_val = None

        self.entry.count_for_payroll = True
        if emp_type_val in (EmployeeType.UNPAID_OFFICIAL, EmployeeType.UNPAID_PROBATION):
            self.entry.count_for_payroll = False

    def _fetch_approved_proposals_flags(self) -> Tuple[bool, bool, bool, int, object]:
        approved_proposals = self._get_approved_proposals()
        return self._aggregate_proposal_flags(approved_proposals)

    def _get_approved_proposals(self):
        if not getattr(self.entry, "employee_id", None):
            return Proposal.objects.none()

        return Proposal.objects.filter(
            created_by_id=self.entry.employee_id, proposal_status=ProposalStatus.APPROVED
        ).filter(
            Q(paid_leave_start_date__lte=self.entry.date, paid_leave_end_date__gte=self.entry.date)
            | Q(unpaid_leave_start_date__lte=self.entry.date, unpaid_leave_end_date__gte=self.entry.date)
            | Q(maternity_leave_start_date__lte=self.entry.date, maternity_leave_end_date__gte=self.entry.date)
            | Q(late_exemption_start_date__lte=self.entry.date, late_exemption_end_date__gte=self.entry.date)
        )

    def _aggregate_proposal_flags(self, approved_proposals) -> Tuple[bool, bool, bool, int, object]:
        has_full_day_paid_leave = False
        has_full_day_unpaid_leave = False
        has_maternity_leave = False
        late_exemption_minutes = 0
        half_day_shift = None

        date_chk = self.entry.date

        for p in approved_proposals:
            is_full, shift = self._check_paid_leave(p, date_chk)
            if is_full:
                has_full_day_paid_leave = True
            if shift:
                half_day_shift = shift

            is_full_unpaid, shift_unpaid = self._check_unpaid_leave(p, date_chk)
            if is_full_unpaid:
                has_full_day_unpaid_leave = True
            if shift_unpaid:
                half_day_shift = shift_unpaid

            if self._check_maternity_leave(p, date_chk):
                has_maternity_leave = True

            minutes = self._check_late_exemption(p, date_chk)
            if minutes > 0:
                late_exemption_minutes = max(late_exemption_minutes, minutes)

        return (
            has_full_day_paid_leave,
            has_full_day_unpaid_leave,
            has_maternity_leave,
            late_exemption_minutes,
            half_day_shift,
        )

    def _check_paid_leave(self, proposal, date_chk) -> Tuple[bool, Optional[str]]:
        if (
            proposal.proposal_type == ProposalType.PAID_LEAVE
            and proposal.paid_leave_start_date
            and proposal.paid_leave_end_date
            and proposal.paid_leave_start_date <= date_chk <= proposal.paid_leave_end_date
        ):
            if not proposal.paid_leave_shift or proposal.paid_leave_shift == ProposalWorkShift.FULL_DAY:
                return True, None
            return False, proposal.paid_leave_shift
        return False, None

    def _check_unpaid_leave(self, proposal, date_chk) -> Tuple[bool, Optional[str]]:
        if (
            proposal.proposal_type == ProposalType.UNPAID_LEAVE
            and proposal.unpaid_leave_start_date
            and proposal.unpaid_leave_end_date
            and proposal.unpaid_leave_start_date <= date_chk <= proposal.unpaid_leave_end_date
        ):
            if not proposal.unpaid_leave_shift or proposal.unpaid_leave_shift == ProposalWorkShift.FULL_DAY:
                return True, None
            return False, proposal.unpaid_leave_shift
        return False, None

    def _check_maternity_leave(self, proposal, date_chk) -> bool:
        if (
            proposal.proposal_type == ProposalType.MATERNITY_LEAVE
            and proposal.maternity_leave_start_date
            and proposal.maternity_leave_end_date
            and proposal.maternity_leave_start_date <= date_chk <= proposal.maternity_leave_end_date
        ):
            return True
        return False

    def _check_late_exemption(self, proposal, date_chk) -> int:
        if (
            proposal.proposal_type == ProposalType.LATE_EXEMPTION
            and proposal.late_exemption_start_date
            and proposal.late_exemption_end_date
            and proposal.late_exemption_start_date <= date_chk <= proposal.late_exemption_end_date
            and proposal.late_exemption_minutes
        ):
            return proposal.late_exemption_minutes
        return 0

    def _preserve_explicit_absent(self) -> bool:
        if self.entry.absent_reason in (
            TimesheetReason.PAID_LEAVE,
            TimesheetReason.UNPAID_LEAVE,
            TimesheetReason.MATERNITY_LEAVE,
        ):
            self.entry.count_for_payroll = False
            return True
        return False

    def _determine_sessions(self, work_schedule, compensatory, half_day_shift):
        has_morning = bool(work_schedule and work_schedule.morning_start_time and work_schedule.morning_end_time)
        has_afternoon = bool(work_schedule and work_schedule.afternoon_start_time and work_schedule.afternoon_end_time)

        if compensatory:
            if compensatory.session == CompensatoryWorkday.Session.FULL_DAY:
                has_morning = True
                has_afternoon = True
            elif compensatory.session == CompensatoryWorkday.Session.MORNING:
                has_morning = True
                has_afternoon = False
            else:
                has_morning = False
                has_afternoon = True

        if half_day_shift == ProposalWorkShift.MORNING:
            has_morning = False
            has_afternoon = True
        elif half_day_shift == ProposalWorkShift.AFTERNOON:
            has_morning = True
            has_afternoon = False

        return has_morning, has_afternoon

    def _handle_full_day_leaves(self, paid, unpaid, maternity) -> bool:
        if paid or unpaid or maternity:
            self.entry.status = TimesheetStatus.ABSENT
            if maternity:
                self.entry.absent_reason = TimesheetReason.MATERNITY_LEAVE
            elif unpaid:
                self.entry.absent_reason = TimesheetReason.UNPAID_LEAVE
            else:
                self.entry.absent_reason = TimesheetReason.PAID_LEAVE
            self.entry.count_for_payroll = False
            return True
        return False

    def _handle_single_punch(self) -> bool:
        entry = self.entry
        if (entry.start_time and not entry.end_time) or (not entry.start_time and entry.end_time):
            entry.status = TimesheetStatus.SINGLE_PUNCH
            return True
        return False

    def _is_attendance_outside_schedule(self, work_schedule, compensatory_day) -> bool:
        entry = self.entry
        if (not compensatory_day) and work_schedule and entry.start_time and entry.end_time:
            m_start = combine_datetime(entry.date, work_schedule.morning_start_time)
            m_end = combine_datetime(entry.date, work_schedule.morning_end_time)
            a_start = combine_datetime(entry.date, work_schedule.afternoon_start_time)
            a_end = combine_datetime(entry.date, work_schedule.afternoon_end_time)

            within_morning = False
            within_afternoon = False

            if m_start and m_end:
                within_morning = not (entry.end_time <= m_start or entry.start_time >= m_end)
            if a_start and a_end:
                within_afternoon = not (entry.end_time <= a_start or entry.start_time >= a_end)

            return not (within_morning or within_afternoon)
        return False

    def _handle_non_working_day(self, day_defined_as_working, times_outside_schedule, is_holiday) -> bool:
        non_working_day = (not day_defined_as_working) or times_outside_schedule or is_holiday
        if non_working_day:
            if not self.entry.start_time:
                self.entry.status = None
            else:
                self.entry.status = TimesheetStatus.ON_TIME
            return True
        return False

    def _determine_base_start_time(self, work_schedule, has_morning, has_afternoon):
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

    def _compensatory_fallback_punctuality(
        self, late_exemption_minutes: int, has_maternity_leave: bool, has_morning: bool, has_afternoon: bool
    ) -> bool:
        fallback_start = None
        fallback_allowed = 0
        for wd in range(2, 7):
            fallback = get_work_schedule_by_weekday(wd)
            if not fallback:
                continue

            # If compensatory day has specific session (Morning/Afternoon), look for that session in fallback
            # If Full Day (both True), prefer Morning start time (standard logic)

            found_morning = getattr(fallback, "morning_start_time", None)
            found_afternoon = getattr(fallback, "afternoon_start_time", None)

            if has_morning and found_morning:
                fallback_start = fallback.morning_start_time
                fallback_allowed = fallback.allowed_late_minutes or 0
                break

            if has_afternoon and not has_morning and found_afternoon:
                fallback_start = fallback.afternoon_start_time
                fallback_allowed = fallback.allowed_late_minutes or 0
                break

            # Fallback if specific session not found but maybe we should look harder?
            # Current logic: breaks on first valid match.

        if fallback_start is not None:
            fallback_allowed_final = max(fallback_allowed or 5, late_exemption_minutes or 0)
            if has_maternity_leave:
                fallback_allowed_final = max(fallback_allowed_final, 60)

            dt = combine_datetime(self.entry.date, fallback_start)

            allowed_start_time = dt + timedelta(minutes=fallback_allowed_final)
            if self.entry.start_time <= allowed_start_time:
                self.entry.status = TimesheetStatus.ON_TIME
            else:
                self.entry.status = TimesheetStatus.NOT_ON_TIME
            return True
        return False

    def _evaluate_work_duration(self, work_schedule, has_morning, has_afternoon, allowed_late_minutes):
        entry = self.entry
        m_start = combine_datetime(entry.date, work_schedule.morning_start_time) if work_schedule else None
        m_end = combine_datetime(entry.date, work_schedule.morning_end_time) if work_schedule else None
        a_start = combine_datetime(entry.date, work_schedule.afternoon_start_time) if work_schedule else None
        a_end = combine_datetime(entry.date, work_schedule.afternoon_end_time) if work_schedule else None

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

    # ---------------------------------------------------------------------------
    # Working Days Calculation
    # ---------------------------------------------------------------------------

    def compute_working_days(self) -> None:
        """Compute `entry.working_days`."""
        entry = self.entry
        weekday = entry.date.isoweekday() + 1
        work_schedule = get_work_schedule_by_weekday(weekday)

        is_compensatory = entry.is_compensatory
        is_holiday = entry.is_holiday

        compensatory = None
        if is_compensatory:
            compensatory = CompensatoryWorkday.objects.filter(date=entry.date).first()

        (
            has_full_day_paid_leave,
            has_full_day_unpaid_leave,
            has_maternity_leave,
            _late_exemption_minutes,
            half_day_shift,
        ) = self._fetch_approved_proposals_flags()

        has_morning, has_afternoon = self._determine_sessions(work_schedule, compensatory, None)
        session_count = self._count_sessions(has_morning, has_afternoon)
        daily_max_days = Decimal("1.00")

        if session_count == 0:
            self._handle_zero_sessions(is_holiday)
            return

        if is_holiday:
            self._handle_holiday_working_days(session_count)
            return

        if has_full_day_paid_leave:
            entry.working_days = quantize_decimal(Decimal("1.00"))
            return

        if half_day_shift:
            if self._handle_half_day_shift_working_days(half_day_shift, daily_max_days):
                return

        working_days = self._calculate_standard_working_days()

        if entry.status == TimesheetStatus.SINGLE_PUNCH and work_schedule:
            working_days = self._apply_single_punch_adjustment(
                working_days, work_schedule, has_morning, has_afternoon, session_count, half_day_shift
            )

        working_days = self._apply_maternity_leave_adjustment(working_days, has_maternity_leave)
        working_days = min(working_days, daily_max_days)
        entry.working_days = quantize_decimal(working_days)

    def _count_sessions(self, has_morning, has_afternoon) -> int:
        return (1 if has_morning else 0) + (1 if has_afternoon else 0)

    def _handle_zero_sessions(self, is_holiday) -> None:
        if is_holiday:
            self.entry.working_days = quantize_decimal(Decimal("1.00"))
            return

        if self.entry.official_hours > 0:
            self.entry.working_days = quantize_decimal(
                Decimal(self.entry.official_hours) / Decimal(STANDARD_WORKING_HOURS_PER_DAY)
            )
            return

        self.entry.working_days = quantize_decimal(Decimal("0.00"))

    def _handle_holiday_working_days(self, session_count) -> None:
        if session_count == 1:
            self.entry.working_days = quantize_decimal(Decimal("0.50"))
        else:
            self.entry.working_days = quantize_decimal(Decimal("1.00"))

    def _handle_half_day_shift_working_days(self, half_day_shift, daily_max_days) -> bool:
        try:
            base = Decimal("0.5") + (Decimal(self.entry.official_hours) / Decimal(STANDARD_WORKING_HOURS_PER_DAY))
        except Exception:
            base = Decimal("0.5")
        self.entry.working_days = quantize_decimal(min(base, daily_max_days))

        return self.entry.status != TimesheetStatus.SINGLE_PUNCH

    def _calculate_standard_working_days(self) -> Decimal:
        try:
            return Decimal(self.entry.official_hours) / Decimal(STANDARD_WORKING_HOURS_PER_DAY)
        except Exception:
            return Decimal("0.00")

    def _apply_single_punch_adjustment(
        self, working_days, work_schedule, has_morning, has_afternoon, session_count, half_day_shift
    ) -> Decimal:
        single_punch_contribution = self._calculate_single_punch_contribution(
            work_schedule, has_morning, has_afternoon, session_count, half_day_shift
        )
        if half_day_shift:
            return Decimal("0.5") + single_punch_contribution
        else:
            return single_punch_contribution

    def _apply_maternity_leave_adjustment(self, working_days, has_maternity_leave) -> Decimal:
        if has_maternity_leave:
            return working_days + Decimal("0.125")
        return working_days

    def _calculate_single_punch_contribution(
        self, work_schedule, has_morning, has_afternoon, session_count, half_day_shift
    ) -> Decimal:
        entry = self.entry
        punch_time = entry.start_time

        if not punch_time:
            return Decimal("0.00")

        hypothetical_end = None
        if has_afternoon and work_schedule.afternoon_end_time:
            hypothetical_end = combine_datetime(entry.date, work_schedule.afternoon_end_time)
        elif has_morning and work_schedule.morning_end_time:
            hypothetical_end = combine_datetime(entry.date, work_schedule.morning_end_time)

        if not hypothetical_end or punch_time >= hypothetical_end:
            return Decimal("0.00")

        morning_start = (
            combine_datetime(entry.date, work_schedule.morning_start_time)
            if work_schedule.morning_start_time
            else None
        )
        morning_end = (
            combine_datetime(entry.date, work_schedule.morning_end_time) if work_schedule.morning_end_time else None
        )
        afternoon_start = (
            combine_datetime(entry.date, work_schedule.afternoon_start_time)
            if work_schedule.afternoon_start_time
            else None
        )
        afternoon_end = (
            combine_datetime(entry.date, work_schedule.afternoon_end_time)
            if work_schedule.afternoon_end_time
            else None
        )

        hypothetical_hours = Fraction(0)

        if has_morning and morning_start and morning_end:
            hypothetical_hours += compute_intersection_hours(punch_time, hypothetical_end, morning_start, morning_end)

        if has_afternoon and afternoon_start and afternoon_end:
            hypothetical_hours += compute_intersection_hours(
                punch_time, hypothetical_end, afternoon_start, afternoon_end
            )

        hypothetical_days = (
            Decimal(hypothetical_hours.numerator)
            / Decimal(hypothetical_hours.denominator)
            / Decimal(STANDARD_WORKING_HOURS_PER_DAY)
        )

        max_cap = Decimal("0.00")
        if session_count == 2:
            if half_day_shift:
                max_cap = Decimal("0.25")
            else:
                max_cap = Decimal("0.50")
        elif session_count == 1:
            max_cap = Decimal("0.25")

        return min(hypothetical_days, max_cap)

    # ---------------------------------------------------------------------------
    # Contract / Salary Logic
    # ---------------------------------------------------------------------------

    def set_is_full_salary_from_contract(self) -> None:
        """Set is_full_salary based on the active contract's net_percentage.

        Moves logic from TimeSheetEntry._set_is_full_salary_from_contract.
        """
        # Only set is_full_salary from contract when creating a new entry
        if self.entry.pk is not None:
            return

        # Check if is_full_salary was explicitly set to a non-default value (False)
        if hasattr(self.entry, "_initial_is_full_salary") and self.entry._initial_is_full_salary is False:
            return

        if not self.entry.employee_id or not self.entry.date:
            return

        active_contract = (
            Contract.objects.filter(
                employee_id=self.entry.employee_id,
                status__in=[Contract.ContractStatus.ACTIVE, Contract.ContractStatus.ABOUT_TO_EXPIRE],
                effective_date__lte=self.entry.date,
            )
            .filter(Q(expiration_date__gte=self.entry.date) | Q(expiration_date__isnull=True))
            .order_by("-effective_date")
            .first()
        )

        if active_contract:
            if active_contract.net_percentage == ContractType.NetPercentage.REDUCED:  # "85"
                self.entry.is_full_salary = False
            else:
                self.entry.is_full_salary = True
        else:
            self.entry.is_full_salary = True
