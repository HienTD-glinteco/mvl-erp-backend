import logging
from decimal import Decimal
from fractions import Fraction
from typing import Optional

from django.utils import timezone

from apps.hrm.constants import (
    STANDARD_WORKING_HOURS_PER_DAY,
    AllowedLateMinutesReason,
    TimesheetDayType,
    TimesheetReason,
    TimesheetStatus,
)
from apps.hrm.models.proposal import Proposal, ProposalType
from apps.hrm.models.timesheet import TimeSheetEntry
from apps.hrm.models.work_schedule import WorkSchedule
from apps.hrm.services.timesheet_snapshot_service import TimesheetSnapshotService
from apps.hrm.utils.work_schedule_cache import get_work_schedule_by_weekday
from libs.datetimes import combine_datetime, compute_intersection_hours
from libs.decimals import quantize_decimal

logger = logging.getLogger(__name__)


class TimesheetCalculator:
    """Calculator for timesheet entry logic.

    Encapsulates logic for:
    - Hours Calculation (Morning, Afternoon, Overtime with TC1/TC2/TC3 split)
    - Status Calculation (On Time, Late, Single Punch, Absent)
    - Working Days Computing (including Exempt logic)
    - Penalties (Late/Early with Grace Periods)
    """

    # TODO: Pass in related objects to pre-fetch data and reuse it when processing multiple entries,
    # especially for multiple days of the same employee or multiple employees on the same day.
    def __init__(self, entry: "TimeSheetEntry"):
        self.entry = entry
        self._work_schedule: Optional[WorkSchedule] = None
        self._fetched_schedule = False

    @property
    def work_schedule(self) -> Optional[WorkSchedule]:
        """Lazy load work schedule based on entry date."""
        if not self._fetched_schedule:
            if self.entry.date:
                weekday = self.entry.date.isoweekday() + 1  # 1=Mon -> 2=Mon in WorkSchedule
                self._work_schedule = get_work_schedule_by_weekday(weekday)
            self._fetched_schedule = True
        return self._work_schedule

    def compute_all(self, work_schedule: Optional[WorkSchedule] = None, is_finalizing: bool = False) -> None:
        """Run all calculations for the entry.

        Args:
            work_schedule: Optional WorkSchedule to use.
            is_finalizing: If True, enforces end-of-day logic (e.g. setting ABSENT if no logs).
        """
        if work_schedule:
            self._work_schedule = work_schedule
            self._fetched_schedule = True

        snapshot_service = TimesheetSnapshotService()
        snapshot_service.snapshot_data(self.entry)

        # 1. Check Exemption Short-circuit
        if self.handle_exemption():
            return

        # 2. Calculate Base Hours (Morning/Afternoon)
        self.calculate_hours()

        # 3. Calculate Overtime (TC1/TC2/TC3)
        self.calculate_overtime()

        # 4. Recalculate total_worked_hours after OT is calculated
        self.entry.total_worked_hours = quantize_decimal(
            (self.entry.official_hours or Decimal(0)) + (self.entry.overtime_hours or Decimal(0))
        )

        # 5. Calculate Penalties
        self.calculate_penalties()

        # 6. Compute Status & Working Days
        self.compute_status(is_finalizing=is_finalizing)
        self.compute_working_days(is_finalizing=is_finalizing)

    def handle_exemption(self) -> bool:
        """Check if employee is exempt. If so, grant full credit and exit."""
        if self.entry.is_exempt:
            # NEW: Don't finalize future dates
            if self.entry.date > timezone.localdate():
                self.entry.status = None
                self.entry.working_days = None
                return True

            self.entry.status = TimesheetStatus.ON_TIME
            self.entry.working_days = self._get_max_working_days()
            # Reset penalties/absent reasons just in case
            self.entry.late_minutes = 0
            self.entry.early_minutes = 0
            self.entry.is_punished = False
            self.entry.absent_reason = None
            return True
        return False

    def _get_max_working_days(self) -> Decimal:
        """Return max working days for the day (usually 1.0 or 0.5 based on schedule)."""
        return Decimal("1.00")

    # ---------------------------------------------------------------------------
    # Hours Calculation
    # ---------------------------------------------------------------------------

    def calculate_hours(self, work_schedule: Optional[WorkSchedule] = None) -> None:
        """Calculate morning_hours and afternoon_hours based on WorkSchedule."""
        if work_schedule:
            self._work_schedule = work_schedule
            self._fetched_schedule = True

        # Only calculate if we have both start and end times
        # This preserves manually set hours when start_time/end_time are not available
        if not self.entry.start_time or not self.entry.end_time:
            return

        if not self.work_schedule:
            return

        # Reset hours before calculating (only reached when we have valid times)
        self.entry.morning_hours = Decimal("0.00")
        self.entry.afternoon_hours = Decimal("0.00")

        start = self.entry.start_time
        end = self.entry.end_time

        morning_hours = Fraction(0)
        afternoon_hours = Fraction(0)

        morning_start, morning_end, afternoon_start, afternoon_end = self._get_schedule_times()

        if morning_start and morning_end:
            morning_hours = compute_intersection_hours(start, end, morning_start, morning_end)

        if afternoon_start and afternoon_end:
            afternoon_hours = compute_intersection_hours(start, end, afternoon_start, afternoon_end)

        self.entry.morning_hours = quantize_decimal(
            Decimal(morning_hours.numerator) / Decimal(morning_hours.denominator)
        )
        self.entry.afternoon_hours = quantize_decimal(
            Decimal(afternoon_hours.numerator) / Decimal(afternoon_hours.denominator)
        )
        self.entry.official_hours = quantize_decimal(self.entry.morning_hours + self.entry.afternoon_hours)
        self.entry.total_worked_hours = quantize_decimal(self.entry.official_hours + self.entry.overtime_hours)

    def _get_schedule_times(self):
        morning_start = (
            combine_datetime(self.entry.date, self.work_schedule.morning_start_time)
            if self.work_schedule.morning_start_time
            else None
        )
        morning_end = (
            combine_datetime(self.entry.date, self.work_schedule.morning_end_time)
            if self.work_schedule.morning_end_time
            else None
        )
        afternoon_start = (
            combine_datetime(self.entry.date, self.work_schedule.afternoon_start_time)
            if self.work_schedule.afternoon_start_time
            else None
        )
        afternoon_end = (
            combine_datetime(self.entry.date, self.work_schedule.afternoon_end_time)
            if self.work_schedule.afternoon_end_time
            else None
        )
        return morning_start, morning_end, afternoon_start, afternoon_end

    # ---------------------------------------------------------------------------
    # Overtime Calculation
    # ---------------------------------------------------------------------------

    def calculate_overtime(self) -> None:
        """Calculate overtime hours based on SNAPSHOTTED approved range (TC1/TC2/TC3)."""
        # Only calculate if we have both start and end times
        # This preserves manually set OT hours when start_time/end_time are not available
        if not self.entry.start_time or not self.entry.end_time:
            return

        # Reset OT fields before calculating (only reached when we have valid times)
        self.entry.ot_tc1_hours = Decimal("0.00")
        self.entry.ot_tc2_hours = Decimal("0.00")
        self.entry.ot_tc3_hours = Decimal("0.00")
        self.entry.overtime_hours = Decimal("0.00")
        self.entry.ot_start_time = None
        self.entry.ot_end_time = None

        # Use Snapshotted Approved Range
        approved_start = self.entry.approved_ot_start_time
        approved_end = self.entry.approved_ot_end_time
        approved_minutes = self.entry.approved_ot_minutes

        if not approved_start or not approved_end or (approved_minutes or 0) <= 0:
            return

        # Intersection: Actual Work vs APPROVED Range
        work_date = self.entry.date
        check_in = self.entry.start_time
        check_out = self.entry.end_time

        ot_start = combine_datetime(work_date, approved_start)
        ot_end = combine_datetime(work_date, approved_end)

        actual_ot_start = max(check_in, ot_start)
        actual_ot_end = min(check_out, ot_end)

        if actual_ot_start < actual_ot_end:
            self.entry.ot_start_time = actual_ot_start
            self.entry.ot_end_time = actual_ot_end

            # Calculate raw intersection duration in hours
            duration = (actual_ot_end - actual_ot_start).total_seconds() / 3600.0

            # Subtract overlap with standard hours (if not holiday)
            net_ot_hours = Decimal(duration)
            if self.work_schedule and self.entry.day_type not in [
                TimesheetDayType.HOLIDAY,
                TimesheetDayType.COMPENSATORY,
            ]:
                morning_start, morning_end, afternoon_start, afternoon_end = self._get_schedule_times()
                # Only consider REQUIRED shifts for overlap subtraction
                # This ensures half-day schedules (e.g., Saturday morning only) don't
                # incorrectly subtract non-required shift times from valid OT
                shifts_to_check = []
                if self.work_schedule.is_morning_required and morning_start and morning_end:
                    shifts_to_check.append((morning_start, morning_end))
                if self.work_schedule.is_afternoon_required and afternoon_start and afternoon_end:
                    shifts_to_check.append((afternoon_start, afternoon_end))
                for s_start, s_end in shifts_to_check:
                    overlap_start = max(actual_ot_start, s_start or actual_ot_start)
                    overlap_end = min(actual_ot_end, s_end or actual_ot_end)
                    if overlap_start < overlap_end:
                        ov_dur = (overlap_end - overlap_start).total_seconds() / 3600.0
                        net_ot_hours -= Decimal(ov_dur)

            # Final total and cap
            total_ot = max(Decimal("0.00"), net_ot_hours)
            max_ot = Decimal(approved_minutes) / Decimal("60.0")
            self.entry.overtime_hours = quantize_decimal(min(total_ot, max_ot))

            # Split by category
            self._split_overtime_by_category(self.entry.overtime_hours)

    def _split_overtime_by_category(self, hours: Decimal) -> None:
        """Helper to split total OT hours into TC1/TC2/TC3.

        Logic:
        - TC1 (1.5x): Weekday and Saturday.
        - TC2 (2.0x): Sunday.
        - TC3 (3.0x): Holiday.
        """
        if hours <= 0:
            return

        day_type = self.entry.day_type
        if day_type == TimesheetDayType.HOLIDAY:
            self.entry.ot_tc3_hours = quantize_decimal(hours)
        elif self.entry.date and self.entry.date.weekday() == 6 and day_type != TimesheetDayType.COMPENSATORY:
            # Sunday only
            self.entry.ot_tc2_hours = quantize_decimal(hours)
        else:
            # Weekday and Saturday
            self.entry.ot_tc1_hours = quantize_decimal(hours)

    def _is_weekend_ot(self, work_schedule) -> bool:
        """Determine if it's TC2 (Weekend)."""
        # "TC2: Days not defined as working days in WorkSchedule"
        if not work_schedule:
            # If no schedule defined for this weekday, it's a weekend/off-day -> TC2
            return True
        return False

    # ---------------------------------------------------------------------------
    # Penalties Calculation
    # ---------------------------------------------------------------------------

    def calculate_penalties(self) -> None:
        """Calculate late/early minutes and determine punishment status.

        Supports single punch scenarios:
        - If only start_time exists: calculate late_minutes only
        - If only end_time exists: calculate early_minutes only
        - If both exist: calculate both late_minutes and early_minutes

        Also accounts for Partial Leaves (Morning/Afternoon) by adjusting the
        expected schedule boundaries.
        """
        self.entry.late_minutes = 0
        self.entry.early_minutes = 0
        self.entry.is_punished = False

        # Need at least one punch to calculate penalties
        if not self.entry.start_time and not self.entry.end_time:
            return

        if not self.work_schedule:
            return

        morning_start, morning_end, afternoon_start, afternoon_end = self._get_schedule_times()

        # 1. Determine Grace Period from Snapshot (or default)
        grace_period = self.entry.allowed_late_minutes or 0

        # 2. Determine Adjusted Schedule Boundaries based on Leave Proposals
        sched_start, sched_end = self._determine_adjusted_schedule_boundaries(
            morning_start, morning_end, afternoon_start, afternoon_end
        )

        late_min = 0
        early_min = 0

        # 3. Calculate Minutes based on Adjusted Boundaries

        # Calculate late minutes if start_time exists and we have an expected start
        if self.entry.start_time and sched_start:
            check_in = self.entry.start_time
            # Late: check_in > sched_start
            late_sec = max(0.0, (check_in - sched_start).total_seconds())
            late_min = int(late_sec // 60)
            self.entry.late_minutes = late_min

        # Calculate early minutes if end_time exists and we have an expected end
        if self.entry.end_time and sched_end:
            check_out = self.entry.end_time
            # Early: check_out < sched_end
            early_sec = max(0.0, (sched_end - check_out).total_seconds())
            early_min = int(early_sec // 60)
            self.entry.early_minutes = early_min

        # 4. Determine Punishment
        if (late_min + early_min) > grace_period:
            self.entry.is_punished = True

    def _determine_adjusted_schedule_boundaries(self, morning_start, morning_end, afternoon_start, afternoon_end):
        """Determine effective schedule start/end based on leave proposals.

        Also respects `is_morning_required` and `is_afternoon_required` flags from schedule.
        """
        # Check for Leave Proposals
        proposals = Proposal.get_active_leave_proposals(self.entry.employee_id, self.entry.date)
        has_morning_leave = any(p.is_morning_leave for p in proposals)
        has_afternoon_leave = any(p.is_afternoon_leave for p in proposals)

        work_schedule = self.work_schedule
        is_morning_required = work_schedule.is_morning_required if work_schedule else True
        is_afternoon_required = work_schedule.is_afternoon_required if work_schedule else True

        # Baseline Schedule Boundaries - Filter by Requirement
        # If Morning is NOT required, start time effectively moves to Afternoon
        eff_morning_start = morning_start if is_morning_required else None
        eff_morning_end = morning_end if is_morning_required else None

        # If Afternoon is NOT required, end time effectively moves to Morning
        eff_afternoon_start = afternoon_start if is_afternoon_required else None
        eff_afternoon_end = afternoon_end if is_afternoon_required else None

        sched_start = eff_morning_start or eff_afternoon_start
        sched_end = eff_afternoon_end or eff_morning_end

        # Adjust Start Boundary (Expected Check-in) based on Leave
        if has_morning_leave and sched_start == eff_morning_start:
            # If Morning is excused, expected start shifts to Afternoon (if required)
            sched_start = eff_afternoon_start

        if has_afternoon_leave and sched_start == eff_afternoon_start:
            # If Afternoon is ALSO excused (and we were expecting to start then),
            # then we have NO expected start time.
            sched_start = None

        # Adjust End Boundary (Expected Check-out) based on Leave
        if has_afternoon_leave and sched_end == eff_afternoon_end:
            # If Afternoon is excused, expected end shifts to Morning (if required)
            sched_end = eff_morning_end

        if has_morning_leave and sched_end == eff_morning_end:
            # If Morning is ALSO excused (and we were expecting to end then),
            # then we have NO expected end time.
            sched_end = None

        return sched_start, sched_end

    # ---------------------------------------------------------------------------
    # Status & Working Days
    # ---------------------------------------------------------------------------

    def compute_status(self, is_finalizing: bool = False) -> None:
        """Compute status: ABSENT, SINGLE_PUNCH, ON_TIME, NOT_ON_TIME.

        PRIORITY ORDER (per PR1 plan Task 1.4):
        1. Single Punch takes precedence over leave
        2. Then check leave (no attendance)
        3. Then no logs
        4. Finally two punches

        NOTE: This method assumes snapshot_data has already been called by compute_all().
        It does NOT call snapshot_data to avoid resetting calculated values (late_minutes, etc.).
        """

        # 1. Single Punch takes precedence over leave (has 1 attendance log)
        if self._is_single_punch():
            # Clear absent_reason since attendance wins over leave
            self.entry.absent_reason = None
            self._handle_single_punch_status(is_finalizing)
            return

        # 2. Two Logs - attendance wins, clear leave and use penalty status
        if self.entry.start_time and self.entry.end_time:
            self.entry.absent_reason = None
            self.entry.status = TimesheetStatus.NOT_ON_TIME if self.entry.is_punished else TimesheetStatus.ON_TIME
            return

        # 3. No Logs - check leave status
        if self._handle_leave_status(is_finalizing):
            return

        # 4. No Logs, No Leave - handle as absent or pending
        self._handle_no_logs_status(is_finalizing)

    def _handle_leave_status(self, is_finalizing: bool) -> bool:
        """Return True if status was set due to leave.

        NOTE: This method is only called when there's NO attendance logs.
        The attendance priority rule is handled in compute_status() before this is called.
        """
        # Check if day has no work schedule (e.g., Sunday)
        # BUT skip this check for COMPENSATORY days - they're always working days
        if self._get_schedule_max_days() == 0 and self.entry.day_type != TimesheetDayType.COMPENSATORY:
            # No schedule = no working days regardless of leave
            self.entry.status = None
            return True

        leave_reasons = [
            TimesheetReason.PAID_LEAVE,
            TimesheetReason.UNPAID_LEAVE,
            TimesheetReason.MATERNITY_LEAVE,
        ]
        if self.entry.absent_reason in leave_reasons:
            # Full-day leave (absent_reason is set) → status = None
            self.entry.status = None
            return True

        # Check for half-day leave (absent_reason is NOT set, but there's a partial leave proposal)
        if is_finalizing:
            # TODO: cache active leave proposals to reuse, or store the snapshot to timesheet entry
            proposals = Proposal.get_active_leave_proposals(self.entry.employee_id, self.entry.date)
            has_morning_leave = any(p.is_morning_leave for p in proposals)
            has_afternoon_leave = any(p.is_afternoon_leave for p in proposals)

            # If both morning and afternoon are covered by partial leaves,
            # treat as fully covered (status = None, not ABSENT)
            if has_morning_leave and has_afternoon_leave:
                self.entry.status = None
                return True

            # Only has partial leave on one half with no attendance on other half → ABSENT
            if has_morning_leave or has_afternoon_leave:
                self.entry.status = TimesheetStatus.ABSENT
                return True

        return False

    def _handle_no_logs_status(self, is_finalizing: bool) -> None:
        """Handle status when no logs are present."""
        if (self.entry.official_hours or 0) > 0:
            self.entry.status = TimesheetStatus.NOT_ON_TIME if self.entry.is_punished else TimesheetStatus.ON_TIME
            return

        # Check if schedule has actual working times (not just if record exists)
        is_working_day = self._get_schedule_max_days() > 0
        if self.entry.day_type == TimesheetDayType.HOLIDAY:
            is_working_day = False
        elif self.entry.day_type == TimesheetDayType.COMPENSATORY:
            is_working_day = True

        if is_working_day and is_finalizing:
            self.entry.status = TimesheetStatus.ABSENT
        else:
            self.entry.status = None

    def _is_single_punch(self) -> bool:
        """Check if only one punch is present."""
        return bool(self.entry.start_time) != bool(self.entry.end_time)

    def _handle_single_punch_status(self, is_finalizing: bool) -> None:
        """Handle status for single punch.

        During the workday (is_finalizing=False):
        - If check-in was on time (not punished) → ON_TIME
        - If check-in was late (punished) → NOT_ON_TIME

        At end of day (is_finalizing=True):
        - Status becomes SINGLE_PUNCH
        """
        if is_finalizing:
            self.entry.status = TimesheetStatus.SINGLE_PUNCH
        else:
            # Use is_punished to determine if check-in was on time or late
            self.entry.status = TimesheetStatus.NOT_ON_TIME if self.entry.is_punished else TimesheetStatus.ON_TIME

    def compute_working_days(self, is_finalizing: bool = False) -> None:
        """Compute working_days according to business rules.

        Priority order:
        1. Real-time preview (not finalizing) → None
        2. Holiday → 1.0
        3. Full-day PAID_LEAVE → max based on schedule (0.5 or 1.0)
        4. ABSENT status:
           - With partial paid leave → partial credit (0.5)
           - Compensatory day → negative debt
           - Otherwise → 0
        5. Normal calculation: worked hours + partial leave + maternity bonus
        6. Single punch → 1/2 max days
        """
        # Real-time preview: leave working_days as None until day is finalized
        if not is_finalizing:
            self.entry.working_days = None
            return

        self.entry.working_days = Decimal("0.00")

        # 1. Holiday - always get full credit
        if self.entry.day_type == TimesheetDayType.HOLIDAY:
            self.entry.working_days = Decimal("1.00")
            return

        # 2. Full-day PAID_LEAVE (absent_reason set by snapshot) → max working days
        if self.entry.absent_reason == TimesheetReason.PAID_LEAVE:
            self.entry.working_days = self._get_schedule_max_days()
            return

        # 3. ABSENT status - check for partial leave credits first
        if self.entry.status == TimesheetStatus.ABSENT:
            partial_credit = self._get_partial_leave_credits()
            if partial_credit > 0:
                self.entry.working_days = partial_credit
                return

            if self.entry.day_type == TimesheetDayType.COMPENSATORY:
                # Absent on compensatory day = negative (debt)
                max_days = self._get_schedule_max_days()
                self.entry.working_days = -max_days
            # Otherwise working_days stays 0
            return

        # 4. Base worked hours calculation
        wd = Decimal(self.entry.official_hours or 0) / Decimal(STANDARD_WORKING_HOURS_PER_DAY)

        # 5. Partial Leave Credits (for half-day leave with attendance)
        wd += self._get_partial_leave_credits()

        # 6. Single Punch - fixed at 1/2 max days, OT reset to 0
        if self.entry.status == TimesheetStatus.SINGLE_PUNCH:
            max_cap = self._get_schedule_max_days()
            if not self.work_schedule:
                max_cap = Decimal("1.00")

            self.entry.working_days = max_cap / 2

            # Reset Overtime for single punch
            self.entry.overtime_hours = Decimal("0.00")
            self.entry.ot_tc1_hours = Decimal("0.00")
            self.entry.ot_tc2_hours = Decimal("0.00")
            self.entry.ot_tc3_hours = Decimal("0.00")
            return

        # 7. Maternity Bonus (+1 hour = 0.125 days)
        wd += self._get_maternity_bonus()

        self.entry.working_days = quantize_decimal(wd)

        # 8. Apply daily cap
        self._apply_working_days_cap()

        # 9. Compensatory days: working_days is the debt (worked - max)
        # If employee works less than max, they owe time (negative working_days)
        if self.entry.day_type == TimesheetDayType.COMPENSATORY:
            max_days = self._get_schedule_max_days()
            self.entry.working_days = self.entry.working_days - max_days
            self.entry.compensation_value = self.entry.working_days
        else:
            self.entry.compensation_value = Decimal("0.00")

    def _get_partial_leave_credits(self) -> Decimal:
        """Calculate credits for partial morning/afternoon leaves."""
        leave_credit = Decimal("0.00")
        proposals = Proposal.get_active_leave_proposals(self.entry.employee_id, self.entry.date)
        for p in proposals:
            if p.proposal_type == ProposalType.PAID_LEAVE:
                if p.is_morning_leave or p.is_afternoon_leave:
                    leave_credit += Decimal("0.50")
        return leave_credit

    def _get_maternity_bonus(self) -> Decimal:
        """Return maternity bonus credit if applicable.

        Only applies when there are at least 2 punches (start_time and end_time present).
        """
        if (
            self.entry.allowed_late_minutes_reason == AllowedLateMinutesReason.MATERNITY
            and self.entry.start_time
            and self.entry.end_time
        ):
            return Decimal("0.125")
        return Decimal("0.00")

    def _apply_working_days_cap(self) -> None:
        """Apply daily cap based on work schedule or absolute max of 1.0."""
        if not self.entry.working_days:
            return

        if self.work_schedule:
            max_days = self._get_schedule_max_days()
            if self.entry.working_days > max_days:
                self.entry.working_days = max_days
        elif self.entry.working_days > 1.0:
            self.entry.working_days = Decimal("1.00")

    def _estimate_single_punch_hours(self) -> Decimal:
        """Estimate hours if only one punch is available."""
        if not self.work_schedule:
            return Decimal("0.00")

        morning_start, morning_end, afternoon_start, afternoon_end = self._get_schedule_times()
        est_hours = Fraction(0)

        if self.entry.start_time:
            # Estimate from Start Time until EOD
            latest_end = afternoon_end or morning_end
            if latest_end:
                if morning_start and morning_end:
                    est_hours += compute_intersection_hours(
                        self.entry.start_time, latest_end, morning_start, morning_end
                    )
                if afternoon_start and afternoon_end:
                    est_hours += compute_intersection_hours(
                        self.entry.start_time, latest_end, afternoon_start, afternoon_end
                    )
        elif self.entry.end_time:
            # Estimate from BOD until End Time
            earliest_start = morning_start or afternoon_start
            if earliest_start:
                if morning_start and morning_end:
                    est_hours += compute_intersection_hours(
                        earliest_start, self.entry.end_time, morning_start, morning_end
                    )
                if afternoon_start and afternoon_end:
                    est_hours += compute_intersection_hours(
                        earliest_start, self.entry.end_time, afternoon_start, afternoon_end
                    )

        return (
            quantize_decimal(Decimal(est_hours.numerator) / Decimal(est_hours.denominator))
            if est_hours.denominator
            else Decimal("0.00")
        )

    def _get_schedule_max_days(self) -> Decimal:
        """Return max working days for the day.

        For compensatory days: uses CompensatoryWorkday.session (full_day=1.0, morning/afternoon=0.5)
        For normal days: uses WorkSchedule.get_max_working_days()
        """
        # For compensatory days, use the session from CompensatoryWorkday
        if self.entry.day_type == TimesheetDayType.COMPENSATORY:
            return self._get_compensatory_max_days()

        # For normal days, use work schedule helper method
        ws = self.work_schedule
        if not ws:
            return Decimal("0.00")

        return ws.get_max_working_days()

    def _get_compensatory_max_days(self) -> Decimal:
        """Return max working days for compensatory day based on session."""
        from apps.hrm.models.holiday import CompensatoryWorkday

        comp = CompensatoryWorkday.objects.filter(date=self.entry.date).first()
        if comp:
            if comp.session == CompensatoryWorkday.Session.FULL_DAY:
                return Decimal("1.00")
            else:  # MORNING or AFTERNOON
                return Decimal("0.50")
        # Fallback if no CompensatoryWorkday found (shouldn't happen)
        return Decimal("1.00")
