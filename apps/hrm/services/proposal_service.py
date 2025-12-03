from datetime import datetime, time, timedelta
from typing import Optional

from django.db import transaction
from django.utils import timezone

from apps.hrm.constants import ProposalType, TimesheetReason, TimesheetStatus
from apps.hrm.models import AttendanceRecord, Proposal, ProposalOvertimeEntry, ProposalTimeSheetEntry, TimeSheetEntry


class ProposalExecutionError(Exception):
    """Exception raised when proposal execution fails."""

    pass


class ProposalService:
    """Service for executing approved proposals and updating timesheet entries.

    This service implements the business logic for applying approved proposals to
    timesheet entries. It handles different proposal types:
    - Leave proposals (PAID_LEAVE, UNPAID_LEAVE, MATERNITY_LEAVE)
    - Timesheet complaint proposals (TIMESHEET_ENTRY_COMPLAINT)
    - Overtime proposals (OVERTIME_WORK)
    """

    @staticmethod
    @transaction.atomic
    def execute_approved_proposal(proposal: Proposal) -> None:
        """Execute an approved proposal by updating related timesheet entries.

        This is the main entry point for executing approved proposals. It delegates
        to specific handlers based on proposal type.

        Args:
            proposal: The approved Proposal instance to execute

        Raises:
            ProposalExecutionError: If proposal execution fails
        """
        # Dispatch to appropriate handler based on proposal type
        handler_map = {
            ProposalType.PAID_LEAVE: ProposalService._execute_leave_proposal,
            ProposalType.UNPAID_LEAVE: ProposalService._execute_leave_proposal,
            ProposalType.MATERNITY_LEAVE: ProposalService._execute_leave_proposal,
            ProposalType.TIMESHEET_ENTRY_COMPLAINT: ProposalService._execute_complaint_proposal,
            ProposalType.OVERTIME_WORK: ProposalService._execute_overtime_proposal,
        }

        handler = handler_map.get(proposal.proposal_type)  # type: ignore
        if handler:
            handler(proposal)

    @staticmethod
    def _execute_leave_proposal(proposal: Proposal) -> None:
        """Execute a leave proposal by marking timesheet entries as absent.

        For leave proposals (PAID_LEAVE, UNPAID_LEAVE, MATERNITY_LEAVE), this method:
        1. Iterates through the date range from start_date to end_date
        2. Finds or creates a TimesheetEntry for each date
        3. Sets status=ABSENT and absent_reason based on proposal type
        4. Handles full_day vs morning/afternoon shifts

        Args:
            proposal: The approved leave Proposal instance
        """
        # Determine the date range and shift based on proposal type
        start_date = None
        end_date = None
        shift = None
        absent_reason = None

        if proposal.proposal_type == ProposalType.PAID_LEAVE:
            start_date = proposal.paid_leave_start_date
            end_date = proposal.paid_leave_end_date
            shift = proposal.paid_leave_shift
            absent_reason = TimesheetReason.PAID_LEAVE
        elif proposal.proposal_type == ProposalType.UNPAID_LEAVE:
            start_date = proposal.unpaid_leave_start_date
            end_date = proposal.unpaid_leave_end_date
            shift = proposal.unpaid_leave_shift
            absent_reason = TimesheetReason.UNPAID_LEAVE
        elif proposal.proposal_type == ProposalType.MATERNITY_LEAVE:
            start_date = proposal.maternity_leave_start_date
            end_date = proposal.maternity_leave_end_date
            shift = None  # Maternity leave is always full day
            absent_reason = TimesheetReason.MATERNITY_LEAVE

        if not start_date or not end_date:
            raise ProposalExecutionError(f"Leave proposal {proposal.id} missing start_date or end_date")

        # Iterate through date range
        current_date = start_date
        while current_date <= end_date:
            # Find or create timesheet entry for this date
            entry, created = TimeSheetEntry.objects.get_or_create(
                employee=proposal.created_by, date=current_date
            )

            # Set status and reason
            entry.status = TimesheetStatus.ABSENT
            entry.absent_reason = absent_reason

            # For full_day or maternity leave, clear all hours
            # For morning/afternoon shift, could implement partial day logic here
            # Currently treating all as full day absent
            entry.morning_hours = 0
            entry.afternoon_hours = 0
            entry.official_hours = 0
            entry.overtime_hours = 0
            entry.total_worked_hours = 0

            # Clear times if no existing attendance
            if not entry.start_time and not entry.end_time:
                entry.start_time = None
                entry.end_time = None

            entry.save()

            # Move to next date
            current_date += timedelta(days=1)

    @staticmethod
    def _execute_complaint_proposal(proposal: Proposal) -> None:
        """Execute a timesheet entry complaint proposal.

        For complaint proposals, this method handles two cases:
        1. Correction: Update existing timesheet entry with approved times
        2. Cannot Attend: Create attendance record to trigger normal processing

        Args:
            proposal: The approved complaint Proposal instance
        """
        # Get the linked timesheet entry
        junction = ProposalTimeSheetEntry.objects.filter(proposal=proposal).first()
        if not junction:
            raise ProposalExecutionError(
                f"Complaint proposal {proposal.id} has no linked timesheet entry"
            )

        entry = junction.timesheet_entry

        # Check if we have approved times
        approved_check_in = proposal.timesheet_entry_complaint_approved_check_in_time
        approved_check_out = proposal.timesheet_entry_complaint_approved_check_out_time

        if approved_check_in and approved_check_out:
            # Case: Correction - Update timesheet entry with approved times
            ProposalService._apply_complaint_correction(entry, approved_check_in, approved_check_out)
        else:
            # Case: Cannot Attend - Create attendance record
            ProposalService._create_attendance_for_complaint(proposal, entry)

    @staticmethod
    def _apply_complaint_correction(
        entry: TimeSheetEntry, approved_check_in: time, approved_check_out: time
    ) -> None:
        """Apply approved times to a timesheet entry (correction case).

        Args:
            entry: The TimesheetEntry to update
            approved_check_in: Approved check-in time
            approved_check_out: Approved check-out time
        """
        # Combine date with approved times to create datetime
        start_datetime = timezone.make_aware(datetime.combine(entry.date, approved_check_in))
        end_datetime = timezone.make_aware(datetime.combine(entry.date, approved_check_out))

        # Update entry times
        entry.start_time = start_datetime
        entry.end_time = end_datetime

        # Set manually corrected flag to prevent signal overwrite
        entry.is_manually_corrected = True

        # Recalculate hours based on new times
        entry.calculate_hours_from_schedule()

        entry.save()

    @staticmethod
    def _create_attendance_for_complaint(proposal: Proposal, entry: TimeSheetEntry) -> None:
        """Create attendance records for cannot-attend complaint case.

        Args:
            proposal: The complaint Proposal instance
            entry: The TimesheetEntry to update
        """
        # Get proposed times
        proposed_check_in = proposal.timesheet_entry_complaint_proposed_check_in_time
        proposed_check_out = proposal.timesheet_entry_complaint_proposed_check_out_time

        if not proposed_check_in or not proposed_check_out:
            raise ProposalExecutionError(
                f"Complaint proposal {proposal.id} missing proposed check-in/out times"
            )

        # Create attendance records with type OTHER
        # The attendance signal will automatically update the timesheet entry
        employee = proposal.created_by

        # Create check-in record
        check_in_datetime = timezone.make_aware(datetime.combine(entry.date, proposed_check_in))
        AttendanceRecord.objects.create(
            attendance_type="other",
            employee=employee,
            attendance_code=employee.attendance_code or "",
            timestamp=check_in_datetime,
        )

        # Create check-out record
        check_out_datetime = timezone.make_aware(datetime.combine(entry.date, proposed_check_out))
        AttendanceRecord.objects.create(
            attendance_type="other",
            employee=employee,
            attendance_code=employee.attendance_code or "",
            timestamp=check_out_datetime,
        )

    @staticmethod
    def _execute_overtime_proposal(proposal: Proposal) -> None:
        """Execute an overtime proposal by updating timesheet entries.

        For overtime proposals, this method:
        1. Iterates through all ProposalOvertimeEntry records for the proposal
        2. Finds or creates a TimesheetEntry for each date
        3. Triggers calculate_hours_from_schedule() which will read the approved OT duration

        Note: The actual overtime calculation logic is in TimesheetEntry.calculate_hours_from_schedule()
        which checks for approved ProposalOvertimeEntry records and calculates:
        overtime_hours = min(actual_ot, approved_ot_duration)

        Args:
            proposal: The approved overtime Proposal instance
        """
        # Get all overtime entries for this proposal
        overtime_entries = ProposalOvertimeEntry.objects.filter(proposal=proposal)

        if not overtime_entries.exists():
            raise ProposalExecutionError(f"Overtime proposal {proposal.id} has no overtime entries")

        for ot_entry in overtime_entries:
            # Find or create timesheet entry for this date
            entry, created = TimeSheetEntry.objects.get_or_create(
                employee=proposal.created_by, date=ot_entry.date
            )

            # The calculate_hours_from_schedule method will check for approved overtime
            # proposals and calculate overtime hours accordingly
            entry.calculate_hours_from_schedule()

            entry.save()
