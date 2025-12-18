from datetime import datetime, time, timedelta

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.core.models import UserDevice
from apps.core.utils.jwt import revoke_user_outstanding_tokens
from apps.hrm.constants import ProposalStatus, ProposalType, TimesheetReason, TimesheetStatus
from apps.hrm.models import Proposal, ProposalOvertimeEntry, ProposalTimeSheetEntry, TimeSheetEntry
from apps.notifications.utils import create_notification


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
            ProposalType.DEVICE_CHANGE: ProposalService._execute_device_change_proposal,
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
            entry, created = TimeSheetEntry.objects.get_or_create(employee=proposal.created_by, date=current_date)

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
        5. Sends notifications to affected users

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

        # Step 1: Check if new_device_id is already mapped to another user
        existing_device = UserDevice.objects.filter(device_id=new_device_id).first()
        previous_owner_user = None
        if existing_device:
            if existing_device.user != requester_user:
                # Device belongs to another user, need to reassign
                previous_owner_user = existing_device.user
                # Delete the existing mapping
                existing_device.delete()
            # If it already belongs to requester, we'll update it below

        # Step 2: Delete requester's old device (single device policy)
        # This ensures user has only one device registered
        if requester_user and hasattr(requester_user, "device") and requester_user.device is not None:
            old_device = requester_user.device
            if old_device.device_id != new_device_id:
                # Delete old device mapping
                old_device.delete()

        # Step 3: Create or update UserDevice for requester with new device
        UserDevice.objects.update_or_create(
            user=requester_user,
            defaults={"device_id": new_device_id, "platform": new_platform, "active": True},
        )

        # Step 4: Revoke outstanding tokens for requester (force re-login)
        revoked_count = revoke_user_outstanding_tokens(requester_user)

        # Step 5: Send notifications
        # Notify requester about approval and device assignment
        if requester_user:
            create_notification(
                actor=proposal.approved_by.user if proposal.approved_by else requester_user,  # type: ignore
                recipient=requester_user,
                verb="Device change approved",
                message=f"Your device change request has been approved. New device {new_device_id} has been assigned to your account. Please log in again.",
                extra_data={
                    "proposal_id": str(proposal.id),
                    "new_device_id": new_device_id,
                    "tokens_revoked": revoked_count,
                },
            )

        # Notify previous owner (if device was reassigned from another user)
        if previous_owner_user:
            create_notification(
                actor=proposal.approved_by.user if proposal.approved_by else requester_user,  # type: ignore
                recipient=previous_owner_user,
                verb="Device reassigned",
                message=f"Your device {new_device_id} has been reassigned to another user per admin approval.",
                extra_data={"proposal_id": str(proposal.id), "device_id": new_device_id},
            )

    @staticmethod
    def notify_proposal_approval(proposal: Proposal) -> None:
        """Notify the user about proposal approval.

        Args:
            proposal: The approved Proposal instance
        """
        handler_map = {
            ProposalType.TIMESHEET_ENTRY_COMPLAINT: ProposalService._notify_complaint_proposal,
            ProposalType.DEVICE_CHANGE: ProposalService._notify_device_change_proposal,
        }

        handler = handler_map.get(proposal.proposal_type)  # type: ignore
        if handler:
            handler(proposal)

    @staticmethod
    def _notify_complaint_proposal(proposal: Proposal) -> None:
        """Notify user about timesheet entry complaint proposal approval.

        Args:
            proposal: The approved complaint Proposal instance
        """
        if not proposal.approved_by:
            # NOTE: only send notification if approved_by is set
            return

        status_display = proposal.get_proposal_status_display()
        message = (
            f"Your timesheet complaint has been {status_display} with approved "
            f"check-in time: {proposal.timesheet_entry_complaint_approved_check_in_time} "
            f"and check-out time: {proposal.timesheet_entry_complaint_approved_check_out_time}."
        )  # noqa: E501

        create_notification(
            actor=proposal.approved_by.user,  # type: ignore
            recipient=proposal.created_by.user,  # type: ignore
            verb=f"Your timesheet complaint has been {status_display}.",
            message=message,
            extra_data={"proposal_id": str(proposal.id)},
        )

    @staticmethod
    def _notify_device_change_proposal(proposal: Proposal) -> None:
        """Notify user about device change proposal status.

        This is called for both approval and rejection notifications.

        Args:
            proposal: The device change Proposal instance
        """
        if not proposal.created_by:
            return

        status_display = proposal.get_proposal_status_display()
        requester_user = proposal.created_by.user

        if proposal.proposal_status == ProposalStatus.APPROVED:
            message = (
                f"Your device change request has been {status_display}. "
                f"Device {proposal.device_change_new_device_id} has been assigned to your account. "
                f"Please log in again to use the new device."
            )
        elif proposal.proposal_status == ProposalStatus.REJECTED:
            message = f"Your device change request has been {status_display}."
            if proposal.approval_note:
                message += f" Reason: {proposal.approval_note}"
        else:
            message = f"Your device change request status: {status_display}."

        if requester_user:
            create_notification(
                actor=proposal.approved_by.user if proposal.approved_by else requester_user,  # type: ignore
                recipient=requester_user,
                verb=f"Device change request {status_display}",
                message=message,
                extra_data={
                    "proposal_id": str(proposal.id),
                    "new_device_id": proposal.device_change_new_device_id,
                },
            )
