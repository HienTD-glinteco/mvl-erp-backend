from datetime import date
from typing import Optional, Tuple

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.hrm.constants import ProposalStatus, ProposalType
from apps.hrm.models import (
    AttendanceExemption,
    CompensatoryWorkday,
    Contract,
    Holiday,
    Proposal,
    TimeSheetEntry,
)
from apps.hrm.services.timesheet_calculator import TimesheetCalculator
from apps.hrm.services.timesheet_snapshot_service import TimesheetSnapshotService


@receiver(post_save, sender=Contract)
def contract_changed_handler(sender, instance: Contract, created, **kwargs):
    """
    Handle Contract changes.
    Only update snapshot fields (contract, net_percentage, is_full_salary).
    Do NOT recalculate hours/working_days as contract doesn't affect them.
    """
    if not instance.effective_date or not instance.employee_id:
        return

    transaction.on_commit(lambda: _process_contract_change(instance))


def _process_contract_change(contract: Contract):
    """
    Update future timesheets to reflect new contract data.
    """
    effective_date = contract.effective_date
    query = TimeSheetEntry.objects.filter(employee_id=contract.employee_id, date__gte=effective_date)

    # Prepare data for bulk update
    updates = []
    service = TimesheetSnapshotService()

    # To use bulk_update efficiently, we need to gather objects.
    entries = list(query)
    for entry in entries:
        service.snapshot_contract_info(entry)
        updates.append(entry)

    if updates:
        TimeSheetEntry.objects.bulk_update(updates, fields=["contract", "net_percentage", "is_full_salary"])


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

    for entry in entries:
        # 1. Re-snapshot Day Type
        service.determine_day_type(entry)

        # 2. Recalculate
        calc = TimesheetCalculator(entry)
        calc.compute_all()

        updates.append(entry)

    if updates:
        # Update all relevant fields
        fields = [
            "day_type",
            "working_days",
            "status",
            "ot_tc1_hours",
            "ot_tc2_hours",
            "ot_tc3_hours",
            "overtime_hours",
            "is_punished",
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
    query = TimeSheetEntry.objects.filter(employee_id=exemption.employee_id, date__gte=exemption.effective_date)

    service = TimesheetSnapshotService()

    recalc_updates = []

    entries = list(query)
    for entry in entries:
        service.snapshot_data(entry)

        calc = TimesheetCalculator(entry)
        calc.compute_all()
        recalc_updates.append(entry)

    if recalc_updates:
        TimeSheetEntry.objects.bulk_update(
            recalc_updates,
            fields=[
                "is_exempt",
                "status",
                "working_days",
                "late_minutes",
                "early_minutes",
                "is_punished",
                "morning_hours",
                "afternoon_hours",
                "overtime_hours",
                "ot_tc1_hours",
                "ot_tc2_hours",
                "ot_tc3_hours",
                "absent_reason",
                "allowed_late_minutes",
                "allowed_late_minutes_reason",
            ],
        )


@receiver([post_save, post_delete], sender=Proposal)
def proposal_changed_handler(sender, instance: Proposal, **kwargs):
    """
    Handle Proposal changes (Leaves, OT, etc).
    """
    if not instance.created_by_id:
        return

    if instance.proposal_status != ProposalStatus.APPROVED:
        return

    if instance.proposal_type not in [
        ProposalType.PAID_LEAVE,
        ProposalType.UNPAID_LEAVE,
        ProposalType.MATERNITY_LEAVE,
        ProposalType.OVERTIME_WORK,
        ProposalType.LATE_EXEMPTION,
        ProposalType.POST_MATERNITY_BENEFITS,
        ProposalType.TIMESHEET_ENTRY_COMPLAINT,
    ]:
        return

    transaction.on_commit(lambda: _process_proposal_change(instance))


def _process_proposal_change(proposal: Proposal):
    # Determine date range
    start_date = None
    end_date = None

    # Extract dates based on type
    start_date, end_date = _get_start_end_dates(proposal)

    if not start_date:
        return

    if not end_date:
        end_date = start_date

    entries = TimeSheetEntry.objects.filter(employee_id=proposal.created_by_id, date__range=(start_date, end_date))

    snapshot_service = TimesheetSnapshotService()
    updates = []

    is_leave_proposal = proposal.proposal_type == ProposalType.PAID_LEAVE
    is_late_exemption_proposal = proposal.proposal_type == ProposalType.LATE_EXEMPTION
    is_post_maternity_benefits_proposal = proposal.proposal_type == ProposalType.POST_MATERNITY_BENEFITS

    for entry in entries:
        if is_leave_proposal:
            snapshot_service.snapshot_leave_reason(entry)
        if is_late_exemption_proposal:
            snapshot_service.snapshot_late_exemption(entry)
        if is_post_maternity_benefits_proposal:
            snapshot_service.snapshot_post_maternity_benefits(entry)

        # Recalculate
        calculator = TimesheetCalculator(entry)
        calculator.compute_all()
        updates.append(entry)

    if updates:
        TimeSheetEntry.objects.bulk_update(
            updates,
            fields=[
                "absent_reason",
                "count_for_payroll",
                "status",
                "working_days",
                "late_minutes",
                "early_minutes",
                "is_punished",
                "overtime_hours",
                "ot_tc1_hours",
                "ot_tc2_hours",
                "ot_tc3_hours",
            ],
        )


def _get_start_end_dates(proposal: Proposal) -> Tuple[Optional[date], Optional[date]]:
    start_date, end_date = None, None

    if proposal.proposal_type == ProposalType.PAID_LEAVE:
        start_date = proposal.paid_leave_start_date
        end_date = proposal.paid_leave_end_date

    if proposal.proposal_type == ProposalType.UNPAID_LEAVE:
        start_date = proposal.unpaid_leave_start_date
        end_date = proposal.unpaid_leave_end_date

    if proposal.proposal_type == ProposalType.MATERNITY_LEAVE:
        start_date = proposal.maternity_leave_start_date
        end_date = proposal.maternity_leave_end_date

    if proposal.proposal_type == ProposalType.OVERTIME_WORK:
        dates = list(proposal.overtime_entries.values_list("date", flat=True).order_by("date"))
        start_date = min(dates)
        end_date = max(dates)

    if proposal.proposal_type == ProposalType.LATE_EXEMPTION:
        start_date = proposal.late_exemption_start_date
        end_date = proposal.late_exemption_end_date

    if proposal.proposal_type == ProposalType.POST_MATERNITY_BENEFITS:
        start_date = proposal.post_maternity_benefits_start_date
        end_date = proposal.post_maternity_benefits_end_date

    if proposal.proposal_type == ProposalType.TIMESHEET_ENTRY_COMPLAINT:
        start_date = proposal.timesheet_entry_complaint_start_date
        end_date = proposal.timesheet_entry_complaint_end_date

    return start_date, end_date
