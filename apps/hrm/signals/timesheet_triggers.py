from datetime import date
from typing import List

from django.db import transaction
from django.db.models import F, Q
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone

from apps.hrm.models import (
    AttendanceExemption,
    CompensatoryWorkday,
    Contract,
    Holiday,
    Proposal,
    TimeSheetEntry,
)
from apps.hrm.constants import ProposalType, ProposalStatus
from apps.hrm.services.timesheet_calculator import TimesheetCalculator
from apps.hrm.services.timesheet_snapshot_service import TimesheetSnapshotService


@receiver(post_save, sender=Contract)
def contract_changed_handler(sender, instance: Contract, created, **kwargs):
    """
    Handle Contract changes.
    Only update snapshot fields (contract, wage_rate, is_full_salary).
    Do NOT recalculate hours/working_days as contract doesn't affect them.
    """
    if not instance.effective_date or not instance.employee_id:
        return

    # Trigger async update
    # In a real app, use Celery task. Here we might do it inline or via on_commit if simple.
    # The requirement says "Dùng bulk update ở đây".
    transaction.on_commit(lambda: _process_contract_change(instance))


def _process_contract_change(contract: Contract):
    """
    Update future timesheets to reflect new contract data.
    """
    effective_date = contract.effective_date
    query = TimeSheetEntry.objects.filter(
        employee_id=contract.employee_id,
        date__gte=effective_date
    )

    # Prepare data for bulk update
    updates = []
    service = TimesheetSnapshotService()

    # We can't easily bulk_update with dynamic logic per row (snapshot logic might differ per date if multiple contracts overlap?)
    # But usually for a single contract change, it becomes the active one for a range.
    # SnapshotService logic: find active contract for date.
    # If we changed a contract, it might affect which contract is picked.

    # Optimization: If we know this contract IS the active one for the range, we can bulk update.
    # But if there's a newer contract later, we shouldn't overwrite that range.
    # Let's iterate for correctness as SnapshotService handles "find active contract".
    # Wait, the comment said: "Dùng bulk update ở đây. Và chỉ update đúng các field snapshot của contract."

    # To use bulk_update efficiently, we need to gather objects.
    entries = list(query)
    for entry in entries:
        # Re-run snapshot logic for contract ONLY?
        # Or full snapshot? SnapshotService does all.
        # Let's call snapshot_contract_info specifically if we can expose it, or just snapshot_data.
        service.snapshot_data(entry)
        updates.append(entry)

    if updates:
        TimeSheetEntry.objects.bulk_update(
            updates,
            fields=["contract", "wage_rate", "is_full_salary"]
        )


@receiver([post_save, post_delete], sender=Holiday)
@receiver([post_save, post_delete], sender=CompensatoryWorkday)
def calendar_event_changed_handler(sender, instance, **kwargs):
    """
    Handle Holiday or CompensatoryWorkday changes.
    Affects 'day_type' and potentially status/working_days.
    """
    # Determine date range
    start_date = getattr(instance, "start_date", None) or getattr(instance, "date", None)
    end_date = getattr(instance, "end_date", None) or getattr(instance, "date", None)

    if not start_date:
        return

    if not end_date:
        end_date = start_date

    transaction.on_commit(lambda: _process_calendar_change(start_date, end_date))


@transaction.atomic
def _process_calendar_change(start_date: date, end_date: date):
    """
    Recalculate timesheets for all employees in the date range.
    """
    entries = TimeSheetEntry.objects.filter(date__range=(start_date, end_date))

    service = TimesheetSnapshotService()
    updates = []

    # Need to fetch calculator for logic?
    # Changing day_type affects working_days (e.g. Holiday = full paid?)
    # So we need full recalculation.

    for entry in entries:
        # 1. Re-snapshot Day Type
        service.snapshot_data(entry)

        # 2. Recalculate
        calc = TimesheetCalculator(entry)
        calc.compute_all()

        updates.append(entry)

    if updates:
        # Update all relevant fields
        fields = [
            "day_type", "working_days", "status", "ot_tc1_hours", "ot_tc2_hours", "ot_tc3_hours",
            "overtime_hours", "is_punished"
        ]
        TimeSheetEntry.objects.bulk_update(updates, fields=fields)


@receiver([post_save, post_delete], sender=AttendanceExemption)
def exemption_changed_handler(sender, instance: AttendanceExemption, **kwargs):
    """
    Handle AttendanceExemption changes.
    """
    if not instance.employee_id or not instance.effective_date:
        return

    transaction.on_commit(lambda: _process_exemption_change(instance))


def _process_exemption_change(exemption: AttendanceExemption):
    query = TimeSheetEntry.objects.filter(
        employee_id=exemption.employee_id,
        date__gte=exemption.effective_date
    )
    # Note: AttendanceExemption model doesn't have end_date, removing filter

    # Check if we are ADDING an exemption (making them exempt) or REMOVING/MODIFYING?
    # We need to re-evaluate the exemption status for each day.
    # The comment said:
    # "check xem nếu giá trị is_exemption được set thành True, thì dùng bulk update, set và status
    # chỉ khi is_exemption được set thành False, thì mới dùng forloop và compute lại giá trị"

    # We can check per entry or check the operation?
    # The service determines if they are exempt.

    service = TimesheetSnapshotService()

    exempt_updates = []
    recalc_updates = []

    entries = list(query)
    for entry in entries:
        old_exempt = entry.is_exempt
        service.snapshot_data(entry) # Updates is_exempt
        new_exempt = entry.is_exempt

        if new_exempt:
            # Short circuit logic: Set to ON_TIME, Max Working Days
            entry.status = TimesheetStatus.ON_TIME
            entry.working_days = Decimal("1.00") # Assuming max
            entry.late_minutes = 0
            entry.early_minutes = 0
            entry.is_punished = False
            exempt_updates.append(entry)
        else:
            # If it WAS exempt and now is NOT, or just not exempt -> Recalculate full logic
            calc = TimesheetCalculator(entry)
            calc.compute_all()
            recalc_updates.append(entry)

    if exempt_updates:
        TimeSheetEntry.objects.bulk_update(
            exempt_updates,
            fields=["is_exempt", "status", "working_days", "late_minutes", "early_minutes", "is_punished"]
        )

    if recalc_updates:
        # Update all fields
        TimeSheetEntry.objects.bulk_update(
            recalc_updates,
            fields=[
                "is_exempt", "status", "working_days", "late_minutes", "early_minutes", "is_punished",
                "morning_hours", "afternoon_hours", "overtime_hours", "ot_tc1_hours", "ot_tc2_hours", "ot_tc3_hours"
            ]
        )


@receiver([post_save, post_delete], sender=Proposal)
def proposal_changed_handler(sender, instance: Proposal, **kwargs):
    """
    Handle Proposal changes (Leaves, OT, etc).
    """
    # Optimization: Filter types
    if instance.proposal_type not in [
        ProposalType.PAID_LEAVE,
        ProposalType.UNPAID_LEAVE,
        ProposalType.MATERNITY_LEAVE,
        ProposalType.OVERTIME_WORK,
        ProposalType.LATE_EXEMPTION,
        ProposalType.POST_MATERNITY_BENEFITS,
        ProposalType.TIMESHEET_ENTRY_COMPLAINT # Complaint usually triggers linking task, but might need recalc?
    ]:
        return

    # Only approved proposals affect calculation (usually)
    # But if a proposal moves from Approved -> Rejected/Cancelled, we need to revert.
    # So we trigger on any change if it WAS approved or IS approved?
    # Or just always trigger and let calculator find valid ones.

    if not instance.created_by_id:
        return

    transaction.on_commit(lambda: _process_proposal_change(instance))


def _process_proposal_change(proposal: Proposal):
    # Determine date range
    start_date = None
    end_date = None

    # Extract dates based on type
    if proposal.proposal_type == ProposalType.PAID_LEAVE:
        start_date = proposal.paid_leave_start_date
        end_date = proposal.paid_leave_end_date
    elif proposal.proposal_type == ProposalType.UNPAID_LEAVE:
        start_date = proposal.unpaid_leave_start_date
        end_date = proposal.unpaid_leave_end_date
    elif proposal.proposal_type == ProposalType.MATERNITY_LEAVE:
        start_date = proposal.maternity_leave_start_date
        end_date = proposal.maternity_leave_end_date
    elif proposal.proposal_type == ProposalType.OVERTIME_WORK:
        # Overtime entries might span multiple dates, but usually proposal has a range?
        # ProposalOvertimeEntry has dates. We might need to query them.
        # Fallback: check related entries
        entries = proposal.overtime_entries.all()
        dates = [e.date for e in entries]
        if dates:
            start_date = min(dates)
            end_date = max(dates)
    elif proposal.proposal_type == ProposalType.LATE_EXEMPTION:
        start_date = proposal.late_exemption_start_date
        end_date = proposal.late_exemption_end_date
    elif proposal.proposal_type == ProposalType.POST_MATERNITY_BENEFITS:
        start_date = proposal.post_maternity_benefits_start_date
        end_date = proposal.post_maternity_benefits_end_date

    if not start_date:
        return

    if not end_date:
        end_date = start_date

    entries = TimeSheetEntry.objects.filter(
        employee_id=proposal.created_by_id,
        date__range=(start_date, end_date)
    )

    service = TimesheetSnapshotService()
    updates = []

    for entry in entries:
        # Re-snapshot leaves/reasons
        service.snapshot_data(entry)

        # Recalculate
        calc = TimesheetCalculator(entry)
        calc.compute_all()
        updates.append(entry)

    if updates:
        TimeSheetEntry.objects.bulk_update(
            updates,
            fields=[
                "absent_reason", "count_for_payroll", "status", "working_days",
                "late_minutes", "early_minutes", "is_punished",
                "overtime_hours", "ot_tc1_hours", "ot_tc2_hours", "ot_tc3_hours"
            ]
        )
