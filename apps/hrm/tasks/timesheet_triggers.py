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
from apps.hrm.services.timesheets import (
    create_entries_for_employee_month,
    create_monthly_timesheet_for_employee,
)


@shared_task
def process_contract_change(contract: Contract):
    """
    Update timesheets to reflect new contract data.
    - For backdated contracts: create timesheet entries for past months
    - Update monthly timesheets to calculate leave balances
    """
    effective_date = contract.effective_date
    today = date.today()
    employee_id = contract.employee_id

    # For expired contracts, only update existing entries (no new creation)
    if contract.status == Contract.ContractStatus.EXPIRED:
        query = TimeSheetEntry.objects.filter(employee_id=employee_id, date__gte=effective_date)
        service = TimesheetSnapshotService()
        for entry in query:
            service.snapshot_contract_info(entry)
            entry.save(need_clean=False)
        return

    # For active/about_to_expire contracts with backdated effective_date
    if contract.status in [Contract.ContractStatus.ACTIVE, Contract.ContractStatus.ABOUT_TO_EXPIRE]:
        start_year, start_month = effective_date.year, effective_date.month
        end_year, end_month = today.year, today.month

        # 1. Create timesheet entries for past months (from effective_date to current month)
        for year in range(start_year, end_year + 1):
            first_month = start_month if year == start_year else 1
            last_month = end_month if year == end_year else 12

            for month in range(first_month, last_month + 1):
                create_entries_for_employee_month(employee_id, year, month)

        # 2. Update existing entries with contract info
        query = TimeSheetEntry.objects.filter(employee_id=employee_id, date__gte=effective_date)
        service = TimesheetSnapshotService()
        for entry in query:
            service.snapshot_contract_info(entry)
            entry.save(need_clean=False)

        # 3. Update monthly timesheets (for leave balance calculations)
        # Process in chronological order to ensure correct carry-over
        for year in range(start_year, end_year + 1):
            first_month = start_month if year == start_year else 1
            last_month = end_month if year == end_year else 12

            for month in range(first_month, last_month + 1):
                create_monthly_timesheet_for_employee(employee_id, year, month)


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
