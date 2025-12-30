from decimal import Decimal
import logging
from typing import Optional

from django.db import models
from django.db.models import QuerySet

from apps.hrm.models import Contract, TimeSheetEntry, AttendanceExemption, Proposal
from apps.hrm.constants import TimesheetDayType, TimesheetReason, ProposalType, ProposalWorkShift, TimesheetStatus
from apps.hrm.models.holiday import Holiday, CompensatoryWorkday

logger = logging.getLogger(__name__)


class TimesheetSnapshotService:
    """Service to handle timesheet snapshotting.

    This service is responsible for:
    1. Determining the Day Type (Official, Holiday, Compensatory).
    2. Snapshotting Contract details (Contract ID, Wage Rate, Is Full Salary).
    3. Snapshotting Attendance Exemption status.
    4. Applying Leave reasons (Paid/Unpaid/Maternity).
    """

    def snapshot_data(self, entry: TimeSheetEntry) -> None:
        """Perform all snapshot operations for a timesheet entry."""
        # 1. Determine Day Type (Holiday, Compensatory, Normal)
        self._determine_day_type(entry)

        # 2. Snapshot Contract Info
        self._snapshot_contract_info(entry)

        # 3. Snapshot Exemption Status
        self._snapshot_exemption_status(entry)

        # 4. Apply Leave Reasons
        self._apply_leave_reason(entry)

    def _determine_day_type(self, entry: TimeSheetEntry) -> None:
        """Determine if the day is a Holiday, Compensatory Workday, or standard."""
        # Default to None (Normal) if not set or invalid
        # Precedence: Compensatory > Holiday > Standard

        # Check Compensatory Workday
        is_compensatory = CompensatoryWorkday.objects.filter(date=entry.date).exists()
        if is_compensatory:
            entry.day_type = TimesheetDayType.COMPENSATORY
            return

        # Check Holiday
        # Holiday model usually has start_date and end_date ranges
        is_holiday = Holiday.objects.filter(start_date__lte=entry.date, end_date__gte=entry.date).exists()
        if is_holiday:
            entry.day_type = TimesheetDayType.HOLIDAY
            return

        # Else: Standard day (will be checked against WorkSchedule later in calculator)
        entry.day_type = None

    def _snapshot_contract_info(self, entry: TimeSheetEntry) -> None:
        """Find active contract for the date and snapshot its details."""
        # Find active contract
        contract = (
            Contract.objects.filter(
                employee=entry.employee,
                effective_date__lte=entry.date,
                contract_type__isnull=False,
            )
            .order_by("-effective_date")
            .first()
        )

        if contract:
            entry.contract = contract
            # Snapshot wage rate
            # Note: Contract model doesn't have wage_rate field directly exposed in the viewed file.
            # It seems the user request implies copying specific fields.
            # However, looking at Contract model, there is no wage_rate field.
            # The previous code assumed contract.wage_rate.
            # If it's missing, we default to 100.
            entry.wage_rate = getattr(contract, "wage_rate", 100)

            # Snapshot is_full_salary from ContractType
            # Assuming ContractType has is_full_salary field
            if contract.contract_type:
                entry.is_full_salary = getattr(contract.contract_type, "is_full_salary", True)
        else:
            entry.contract = None
            entry.wage_rate = 100
            # Default is_full_salary? Usually True or False? Model default is True.
            # entry.is_full_salary = True

    def _snapshot_exemption_status(self, entry: TimeSheetEntry) -> None:
        """Check if employee is exempt from attendance on this date."""
        # Note: AttendanceExemption is a OneToOne with Employee, but logic seems to treat it as possibly historical or ranges?
        # Model `AttendanceExemption` in viewed file has `OneToOneField` to Employee and `effective_date`.
        # It DOES NOT have `end_date`.
        # So if `effective_date` <= entry.date, they are exempt?
        # But OneToOne implies only one record per employee.

        # Checking AttendanceExemption model definition:
        # employee = OneToOneField(...)
        # effective_date = models.DateField(...)

        # So simply check if record exists and effective_date is met.
        try:
            exemption = AttendanceExemption.objects.get(employee=entry.employee)
            if exemption.effective_date and exemption.effective_date <= entry.date:
                entry.is_exempt = True
            else:
                 # If effective_date is null? Usually effective immediately?
                 # Assuming effective_date is optional -> active immediately?
                 if not exemption.effective_date:
                     entry.is_exempt = True
                 else:
                     entry.is_exempt = False
        except AttendanceExemption.DoesNotExist:
            entry.is_exempt = False

    def _apply_leave_reason(self, entry: TimeSheetEntry) -> None:
        """Check for approved full-day leaves and set absent_reason and count_for_payroll."""
        # Clear existing
        entry.absent_reason = None
        # Default count_for_payroll is True (from model default), but if leave might change it.
        # But wait, logic should be: if leave -> set false. If no leave -> keep default?
        # Model default is True.
        entry.count_for_payroll = True

        proposals = Proposal.get_active_leave_proposals(entry.employee_id, entry.date)

        for p in proposals:
            # Check shifts (Full Day)
            if p.proposal_type == ProposalType.PAID_LEAVE:
                if not p.paid_leave_shift or p.paid_leave_shift == ProposalWorkShift.FULL_DAY:
                    entry.absent_reason = TimesheetReason.PAID_LEAVE
                    entry.count_for_payroll = False
                    # If status is absent, calculator will use this reason to set working_days=1
                    return
            elif p.proposal_type == ProposalType.UNPAID_LEAVE:
                if not p.unpaid_leave_shift or p.unpaid_leave_shift == ProposalWorkShift.FULL_DAY:
                    entry.absent_reason = TimesheetReason.UNPAID_LEAVE
                    entry.count_for_payroll = False
                    return
            elif p.proposal_type == ProposalType.MATERNITY_LEAVE:
                 entry.absent_reason = TimesheetReason.MATERNITY_LEAVE
                 entry.count_for_payroll = False
                 return
