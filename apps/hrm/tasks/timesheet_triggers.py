from datetime import date
from typing import Optional, Tuple

from celery import shared_task
from django.db import transaction

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

    service = TimesheetSnapshotService()

    for entry in query:
        service.snapshot_contract_info(entry)
        entry.save(need_clean=False)


@shared_task
@transaction.atomic
def process_calendar_change(start_date: date, end_date: date):
    """
    Recalculate timesheets for all employees in the date range.
    """
    entries = TimeSheetEntry.objects.filter(date__range=(start_date, end_date))

    for entry in entries:
        calc = TimesheetCalculator(entry)
        calc.compute_all(is_finalizing=entry.is_work_day_finalizing())

        entry.save(need_clean=False)


@shared_task
def process_exemption_change(exemption: AttendanceExemption):
    query = TimeSheetEntry.objects.filter(employee_id=exemption.employee_id, date__gte=exemption.effective_date)

    entries = list(query)
    for entry in entries:
        calc = TimesheetCalculator(entry)
        calc.compute_all(is_finalizing=entry.is_work_day_finalizing())
        entry.save(need_clean=False)


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

    for entry in entries:
        # Recalculate
        calculator = TimesheetCalculator(entry)
        calculator.compute_all(is_finalizing=entry.is_work_day_finalizing())
        entry.save(need_clean=False)


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
