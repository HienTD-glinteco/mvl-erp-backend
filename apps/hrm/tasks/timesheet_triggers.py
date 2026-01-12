from datetime import date
from typing import Optional, Tuple

from celery import shared_task
from django.db import transaction
from django.db.models.signals import post_save

from apps.hrm.constants import ProposalType
from apps.hrm.models import (
    AttendanceExemption,
    Contract,
    Proposal,
    TimeSheetEntry,
)
from apps.hrm.services.timesheet_calculator import TimesheetCalculator
from apps.hrm.services.timesheet_snapshot_service import TimesheetSnapshotService


@shared_task
def process_contract_change(contract: Contract):
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
        for entry in updates:
            post_save.send(sender=TimeSheetEntry, instance=entry, created=False)


@shared_task
@transaction.atomic
def process_calendar_change(start_date: date, end_date: date):
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
        for entry in updates:
            post_save.send(sender=TimeSheetEntry, instance=entry, created=False)


@shared_task
def process_exemption_change(exemption: AttendanceExemption):
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
        for entry in recalc_updates:
            post_save.send(sender=TimeSheetEntry, instance=entry, created=False)


@shared_task
def process_proposal_change(proposal: Proposal):
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

    is_leave_proposal = proposal.proposal_type in [
        ProposalType.PAID_LEAVE,
        ProposalType.UNPAID_LEAVE,
        ProposalType.MATERNITY_LEAVE,
    ]
    is_late_exemption_proposal = proposal.proposal_type in [
        ProposalType.LATE_EXEMPTION,
        ProposalType.POST_MATERNITY_BENEFITS,
    ]
    is_overtime_proposal = proposal.proposal_type == ProposalType.OVERTIME_WORK

    for entry in entries:
        # Snapshot overtime data for OT proposals
        if is_overtime_proposal:
            snapshot_service.snapshot_overtime_data(entry)

        # Snapshot leave reason and count_for_payroll for leave proposals
        if is_leave_proposal:
            # Clear existing absent_reason to allow re-snapshotting
            entry.absent_reason = None
            snapshot_service.snapshot_leave_reason(entry)
            snapshot_service.set_count_for_payroll(entry)

        # Snapshot allowed late minutes for late exemption/post maternity
        if is_late_exemption_proposal:
            snapshot_service.snapshot_allowed_late_minutes(entry)

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
                "allowed_late_minutes",
                "allowed_late_minutes_reason",
                "approved_ot_start_time",
                "approved_ot_end_time",
                "approved_ot_minutes",
            ],
        )
        for entry in updates:
            post_save.send(sender=TimeSheetEntry, instance=entry, created=False)


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
        start_date = proposal.timesheet_entry_complaint_complaint_date
        end_date = proposal.timesheet_entry_complaint_complaint_date

    return start_date, end_date
