from datetime import datetime, time, timedelta

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.core.models import UserDevice
from apps.core.utils.jwt import bump_user_mobile_token_version, revoke_user_outstanding_tokens
from apps.hrm.constants import ProposalType, ProposalWorkShift, TimesheetReason
from apps.hrm.models import Employee, Proposal, ProposalOvertimeEntry, ProposalTimeSheetEntry, TimeSheetEntry
from apps.hrm.services.timesheet_snapshot_service import TimesheetSnapshotService


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
            ProposalType.MATERNITY_LEAVE: ProposalService._execute_maternity_leave_proposal,
            ProposalType.TIMESHEET_ENTRY_COMPLAINT: ProposalService._execute_complaint_proposal,
            ProposalType.OVERTIME_WORK: ProposalService._execute_overtime_proposal,
            ProposalType.DEVICE_CHANGE: ProposalService._execute_device_change_proposal,
            ProposalType.POST_MATERNITY_BENEFITS: ProposalService._execute_post_maternity_benefits_proposal,
        }

        handler = handler_map.get(proposal.proposal_type)  # type: ignore
        if handler:
            handler(proposal)

    @staticmethod
    def _execute_leave_proposal(proposal: Proposal) -> None:
        """
        Execute a leave proposal by marking timesheet entries as absent.
        This is mutual for all LEAVE proposals (PAID_LEAVE, UNPAID_LEAVE, MATERNITY_LEAVE).

        For leave proposals (PAID_LEAVE, UNPAID_LEAVE, MATERNITY_LEAVE), this method:
        1. Iterates through the date range from start_date to end_date
        2. Finds or creates a TimesheetEntry for each date
        3. For FULL_DAY leaves: Sets absent_reason based on proposal type
        4. For partial (MORNING/AFTERNOON) leaves: Does NOT set absent_reason
           to allow TimesheetCalculator to correctly compute partial credits

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

        # Determine if this is a partial leave (morning or afternoon only)
        is_partial_leave = shift in [ProposalWorkShift.MORNING, ProposalWorkShift.AFTERNOON]

        # Iterate through date range
        current_date = start_date
        while current_date <= end_date:
            # Find or create timesheet entry for this date
            entry, created = TimeSheetEntry.objects.get_or_create(employee=proposal.created_by, date=current_date)

            entry.status = None

            # Only set absent_reason for FULL_DAY leaves.
            # Partial leaves should NOT set absent_reason so that
            # TimesheetCalculator can correctly compute partial credits.
            if not is_partial_leave:
                entry.absent_reason = absent_reason
                # For full_day or maternity leave, clear all hours
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
    def _execute_maternity_leave_proposal(proposal: Proposal) -> None:
        """
        Execute other side effects when a maternity leave proposal is approved.
        """
        ProposalService._execute_leave_proposal(proposal)
        today = timezone.now().date()
        if proposal.maternity_leave_start_date <= today <= proposal.maternity_leave_end_date:  # type: ignore[operator]
            proposal.created_by.status = Employee.Status.MATERNITY_LEAVE
            proposal.created_by.resignation_start_date = proposal.maternity_leave_start_date
            proposal.created_by.resignation_end_date = proposal.maternity_leave_end_date
            proposal.created_by.save(update_fields=["status", "resignation_start_date", "resignation_end_date"])

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
            raise ProposalExecutionError(f"Complaint proposal {proposal.id} has no linked timesheet entry")

        entry = junction.timesheet_entry

        # Check if we have approved times
        approved_check_in = proposal.timesheet_entry_complaint_approved_check_in_time
        approved_check_out = proposal.timesheet_entry_complaint_approved_check_out_time

        if approved_check_in and approved_check_out:
            # Case: Correction - Update timesheet entry with approved times
            ProposalService._apply_complaint_correction(entry, approved_check_in, approved_check_out)
        else:
            raise ProposalExecutionError(
                _("Complaint proposal %(id)s missing approved check-in/out times") % {"id": proposal.id}
            )

    @staticmethod
    def _apply_complaint_correction(entry: TimeSheetEntry, approved_check_in: time, approved_check_out: time) -> None:
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
        overtime_entries = list(ProposalOvertimeEntry.objects.filter(proposal=proposal))

        if len(overtime_entries) == 0:
            raise ProposalExecutionError(f"Overtime proposal {proposal.id} has no overtime entries")

        for ot_entry in overtime_entries:
            # Find or create timesheet entry for this date
            entry, created = TimeSheetEntry.objects.get_or_create(employee=proposal.created_by, date=ot_entry.date)

            # The calculate_hours_from_schedule method will check for approved overtime
            # proposals and calculate overtime hours accordingly
            entry.calculate_hours_from_schedule()

            entry.save()

    @staticmethod
    def _execute_device_change_proposal(proposal: Proposal) -> None:
        """Execute a device change proposal by reassigning device to requester.

        For device change proposals, this method:
        1. Removes existing UserDevice mapping if device_id is mapped to another user
        2. Removes requester's old UserDevice (if single device policy)
        3. Creates/updates UserDevice for requester with new device_id
        4. Revokes outstanding tokens for requester (force re-login)

        Args:
            proposal: The approved device change Proposal instance

        Raises:
            ProposalExecutionError: If proposal execution fails
        """
        new_device_id = proposal.device_change_new_device_id
        new_platform = proposal.device_change_new_platform or ""

        if not new_device_id:
            raise ProposalExecutionError(f"Device change proposal {proposal.id} missing new_device_id")

        # Get requester user (proposal.created_by is Employee, need User)
        if not proposal.created_by:
            raise ProposalExecutionError(f"Device change proposal {proposal.id} has no created_by")

        requester_user = proposal.created_by.user

        # Step 1: Check if new_device_id is already active for another user
        existing_device = UserDevice.objects.filter(
            client=UserDevice.Client.MOBILE,
            state=UserDevice.State.ACTIVE,
            device_id=new_device_id,
        ).first()
        if existing_device and existing_device.user != requester_user:
            existing_device.state = UserDevice.State.REVOKED
            existing_device.save(update_fields=["state"])

        # Step 2: Revoke requester's currently active device(s)
        UserDevice.objects.filter(
            user=requester_user,
            client=UserDevice.Client.MOBILE,
            state=UserDevice.State.ACTIVE,
        ).exclude(device_id=new_device_id).update(state=UserDevice.State.REVOKED)

        # Step 3: Create or update active device mapping for requester
        UserDevice.objects.update_or_create(
            user=requester_user,
            client=UserDevice.Client.MOBILE,
            device_id=new_device_id,
            defaults={
                "platform": new_platform,
                "state": UserDevice.State.ACTIVE,
                "last_seen_at": timezone.now(),
            },
        )

        # Step 4: Bump token version and blacklist refresh tokens (force re-login)
        bump_user_mobile_token_version(requester_user)
        revoke_user_outstanding_tokens(requester_user)

    @staticmethod
    def _execute_post_maternity_benefits_proposal(proposal: Proposal) -> None:
        """Execute a post maternity benefits proposal.

        This primarily updates the timesheet calculation logic (allowed late minutes,
        maternity bonus). We trigger a recalculation of affected timesheet entries.
        """
        start_date = proposal.post_maternity_benefits_start_date
        end_date = proposal.post_maternity_benefits_end_date

        if not start_date or not end_date:
            raise ProposalExecutionError(f"Post Maternity proposal {proposal.id} missing start/end date")

        # Iterate through date range and force save to trigger recalculation
        current_date = start_date
        while current_date <= end_date:
            # We only care about existing entries that might need recalculation
            # or creating placeholders?
            # Usually benefits apply when there is attendance.
            # But the requirement implies we should ensure entries exist or just update existing.
            # Let's update existing ones first.
            entries = TimeSheetEntry.objects.filter(employee=proposal.created_by, date=current_date)
            for entry in entries:
                # Explicitly snapshot data first to capture proposal info (e.g. allowed late minutes)
                # before calculation runs.
                TimesheetSnapshotService().snapshot_data(entry)
                entry.calculate_hours_from_schedule()
                entry.save()

            current_date += timedelta(days=1)
