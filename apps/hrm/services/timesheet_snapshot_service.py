import logging

from apps.hrm.constants import AllowedLateMinutesReason, ProposalType, TimesheetDayType, TimesheetReason
from apps.hrm.models import AttendanceExemption, Proposal, TimeSheetEntry
from apps.hrm.models.holiday import CompensatoryWorkday, Holiday
from apps.hrm.utils.work_schedule_cache import get_work_schedule_by_weekday

logger = logging.getLogger(__name__)


class TimesheetSnapshotService:
    """Service to handle timesheet snapshotting.

    This service is responsible for:
    1. Determining the Day Type (Official, Holiday, Compensatory).
    2. Snapshotting Contract details (Contract ID, Wage Rate, Is Full Salary).
    3. Snapshotting Attendance Exemption status.
    4. Applying Leave reasons (Paid/Unpaid/Maternity).
    """

    def set_default_values(self, entry: TimeSheetEntry) -> None:
        """Set default values for timesheet entry fields.

        Unconditionally resets snapshot-related fields to their initial values.
        This ensures a clean slate before snapshot operations, which is essential
        when re-snapshotting an entry.

        Note: Some fields are NOT reset here because they are set by external
        processes or have specific preservation logic:
        - absent_reason: Set by ProposalService when executing leave proposals
        - is_full_salary: Handled by snapshot_contract_info with preservation logic
        """
        # Contract info - reset contract reference, but NOT is_full_salary
        # (is_full_salary is handled by snapshot_contract_info which checks for existing values)
        entry.contract = None
        entry.net_percentage = 100

        # Exemption status
        entry.is_exempt = False

        # Time logs
        entry.morning_hours = 0
        entry.afternoon_hours = 0
        entry.official_hours = 0
        entry.total_worked_hours = 0
        entry.overtime_hours = 0
        entry.ot_tc1_hours = 0
        entry.ot_tc2_hours = 0
        entry.ot_tc3_hours = 0
        entry.ot_start_time = None
        entry.ot_end_time = None

        # Allowed late minutes
        entry.allowed_late_minutes = 0
        entry.allowed_late_minutes_reason = AllowedLateMinutesReason.STANDARD

        # Overtime data
        entry.approved_ot_start_time = None
        entry.approved_ot_end_time = None
        entry.approved_ot_minutes = 0

        # Compensation & Penalties
        entry.compensation_value = 0
        entry.paid_leave_hours = 0
        entry.late_minutes = 0
        entry.early_minutes = 0
        entry.is_punished = False

        # Day type - default to OFFICIAL
        entry.day_type = TimesheetDayType.OFFICIAL
        entry.working_days = 0
        entry.status = None
        entry.absent_reason = None

        # Payroll flag
        entry.is_full_salary = True
        entry.count_for_payroll = True

    def snapshot_data(self, entry: TimeSheetEntry) -> None:
        """Perform all snapshot operations for a timesheet entry."""
        # 0. Set default values
        self.set_default_values(entry)

        # 1. Determine Day Type (Holiday, Compensatory, Normal)
        self.determine_day_type(entry)

        # 2. Snapshot Contract Info
        self.snapshot_contract_info(entry)

        # 3. Snapshot Exemption Status
        self.snapshot_exemption_status(entry)

        # 4. Snapshot Proposals data
        self.snapshot_leave_reason(entry)

        # 5. Snapshot allowed late minutes (includes Late Exemption & Post Maternity)
        self.snapshot_allowed_late_minutes(entry)

        # 6. Snapshot allowed Overtime
        self.snapshot_overtime_data(entry)

        # 7. Set count_for_payroll
        self.set_count_for_payroll(entry)

    def determine_day_type(self, entry: "TimeSheetEntry") -> None:
        """Determine if it is a WORKDAY, HOLIDAY, or COMPENSATORY."""
        date = entry.date
        if not date:
            return

        # Check for Holiday
        holiday = Holiday.objects.filter(start_date__lte=date, end_date__gte=date).first()
        if holiday:
            entry.day_type = TimesheetDayType.HOLIDAY
            return

        # Check for Compensatory (Work on Sunday)
        comp = CompensatoryWorkday.objects.filter(date=date).exists()
        if comp:
            entry.day_type = TimesheetDayType.COMPENSATORY
            return

        entry.day_type = TimesheetDayType.OFFICIAL

    def snapshot_contract_info(self, entry: "TimeSheetEntry") -> None:
        """Snapshot current contract status (Probation vs Official)."""
        from apps.hrm.models.contract import Contract
        from apps.hrm.models.contract_type import ContractType

        if not entry.employee_id:
            return

        # Fetch directly if not prefetched
        contract = (
            Contract.objects.filter(
                employee_id=entry.employee_id,
                effective_date__lte=entry.date,
                status__in=[Contract.ContractStatus.ACTIVE, Contract.ContractStatus.ABOUT_TO_EXPIRE],
            )
            .order_by("-effective_date")
            .first()
        )

        if contract:
            entry.contract = contract
            # Only overwrite if currently default/None
            if entry.net_percentage == 100 or entry.net_percentage == 0:
                entry.net_percentage = contract.net_percentage

            # For is_full_salary, if it's already False, keep it False (more restrictive)
            if entry.is_full_salary:
                entry.is_full_salary = contract.net_percentage == ContractType.NetPercentage.FULL
        else:
            entry.contract = None
            # Don't overwrite if it was manually set to something else
            if entry.net_percentage == 0:
                entry.net_percentage = 100
            if entry.is_full_salary is None:
                entry.is_full_salary = True

    def snapshot_exemption_status(self, entry: "TimeSheetEntry") -> None:
        """Snapshot if employee is exempt from time tracking on this day."""
        if not entry.employee_id:
            return

        if entry.is_exempt:
            return

        # Fetch directly if not prefetched
        entry.is_exempt = AttendanceExemption.objects.filter(
            employee_id=entry.employee_id, effective_date__lte=entry.date, status=AttendanceExemption.Status.ENABLED
        ).exists()

    def snapshot_leave_reason(self, entry: "TimeSheetEntry") -> None:
        """Populate absent_reason if an approved PAID_LEAVE or UNPAID_LEAVE proposal exists."""
        from apps.hrm.models.proposal import Proposal, ProposalType

        if entry.absent_reason:
            return

        # Use Proposal model directly to avoid circular dependency
        leave = Proposal.get_active_leave_proposals(entry.employee_id, entry.date).first()

        if leave:
            # Only set absent_reason if it's a full day leave (no partial shift specified)
            if not leave.paid_leave_shift and not leave.unpaid_leave_shift:
                if leave.proposal_type == ProposalType.MATERNITY_LEAVE:
                    entry.absent_reason = TimesheetReason.MATERNITY_LEAVE
                elif leave.proposal_type == ProposalType.PAID_LEAVE:
                    entry.absent_reason = TimesheetReason.PAID_LEAVE
                elif leave.proposal_type == ProposalType.UNPAID_LEAVE:
                    entry.absent_reason = TimesheetReason.UNPAID_LEAVE
        # We don't clear it here; unexcused absence is handled by the calculator if status is ABSENT
        # and no reason was found.

    def snapshot_allowed_late_minutes(self, entry: TimeSheetEntry) -> None:
        """Calculate and store allowed_late_minutes (grace period)."""
        # 1. Default from Work Schedule
        allowed_minutes = 0
        reason = AllowedLateMinutesReason.STANDARD

        weekday = entry.date.isoweekday() + 1
        work_schedule = get_work_schedule_by_weekday(weekday)
        if work_schedule:
            allowed_minutes = work_schedule.allowed_late_minutes or 0

        # 2. Check Proposals (Complaints/Benefits)
        proposals = Proposal.get_active_complaint_proposals(
            employee_id=entry.employee_id,
            date=entry.date,
        )

        for p in proposals:
            if p.proposal_type == ProposalType.POST_MATERNITY_BENEFITS:
                # Extension for post maternity - min 65 mins
                reason = AllowedLateMinutesReason.MATERNITY
                if allowed_minutes < 65:
                    allowed_minutes = 65

            if p.proposal_type == ProposalType.LATE_EXEMPTION:
                # Custom grace period for late exemption
                if p.late_exemption_minutes:
                    allowed_minutes = p.late_exemption_minutes
                    reason = AllowedLateMinutesReason.LATE_EXEMPTION

        entry.allowed_late_minutes = allowed_minutes
        entry.allowed_late_minutes_reason = reason

    def snapshot_overtime_data(self, entry: TimeSheetEntry) -> None:
        """Snapshot approved overtime data from proposals.

        Calculates:
        - approved_ot_start_time: Min start time
        - approved_ot_end_time: Max end time
        - approved_ot_minutes: Total duration in minutes
        """
        from apps.hrm.models.proposal import ProposalOvertimeEntry, ProposalStatus

        # Find all approved overtime entries for this employee and date
        # Note: Filtering by proposal__created_by and proposal__proposal_status=APPROVED
        # which is the logic used in TimesheetCalculator previously.
        ot_entries = ProposalOvertimeEntry.objects.filter(
            proposal__created_by=entry.employee_id,
            proposal__proposal_status=ProposalStatus.APPROVED,
            date=entry.date,
        )

        if not ot_entries.exists():
            entry.approved_ot_start_time = None
            entry.approved_ot_end_time = None
            entry.approved_ot_minutes = 0
            return

        min_start = None
        max_end = None
        total_minutes = 0

        for ot_entry in ot_entries:
            # Update min start
            if min_start is None or ot_entry.start_time < min_start:
                min_start = ot_entry.start_time

            # Update max end
            if max_end is None or ot_entry.end_time > max_end:
                max_end = ot_entry.end_time

            # Accumulate duration
            # Duration logic: (end - start).seconds / 60
            # Need to handle datetime conversion to subtract properly or just use dummy date
            from datetime import datetime

            # Use a dummy date for calculation
            dummy_date = datetime(2000, 1, 1).date()
            start_dt = datetime.combine(dummy_date, ot_entry.start_time)
            end_dt = datetime.combine(dummy_date, ot_entry.end_time)

            # Handle cross-midnight if applicable (though separate date field implies day-bound)
            # Assuming strictly within the date for now as per previous logic.
            if end_dt > start_dt:
                duration = (end_dt - start_dt).total_seconds() / 60
                total_minutes += int(duration)

        entry.approved_ot_start_time = min_start
        entry.approved_ot_end_time = max_end
        entry.approved_ot_minutes = total_minutes

    def set_count_for_payroll(self, entry: TimeSheetEntry) -> None:
        if not entry.employee_id:
            return

        # Use .employee only if we really need properties from it.
        # But maybe just fetch if not loaded.
        try:
            employee = entry.employee
        except Exception:
            # Fallback if relation not loaded
            from apps.hrm.models import Employee

            employee_obj = Employee.objects.filter(id=entry.employee_id).first()
            if not employee_obj:
                return
            employee = employee_obj

        entry.count_for_payroll = not employee.is_unpaid_employee

        if entry.absent_reason in [
            TimesheetReason.PAID_LEAVE,
            TimesheetReason.UNPAID_LEAVE,
            TimesheetReason.MATERNITY_LEAVE,
        ]:
            entry.count_for_payroll = False
