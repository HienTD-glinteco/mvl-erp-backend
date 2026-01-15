from datetime import date
from typing import Optional, Tuple

from celery import shared_task
from django.db import transaction

from apps.hrm.constants import ProposalType
from apps.hrm.models import (
    AttendanceExemption,
    Contract,
    EmployeeMonthlyTimesheet,
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
    employee_id = contract.employee_id

    # For expired contracts, only update existing entries (no new creation)
    if contract.status == Contract.ContractStatus.EXPIRED:
        query = TimeSheetEntry.objects.filter(employee_id=employee_id, date__gte=effective_date)
        service = TimesheetSnapshotService()
        for entry in query:
            service.snapshot_contract_info(entry)
            entry.save(need_clean=False)
        return

    # For active/about_to_expire contracts
    if contract.status in [Contract.ContractStatus.ACTIVE, Contract.ContractStatus.ABOUT_TO_EXPIRE]:
        _process_backdated_contract_entries(employee_id, effective_date)

        # Always update existing entries with contract info (fast operation)
        # This covers the case where specific entries existed but we need to ensure they link to this new contract
        query = TimeSheetEntry.objects.filter(employee_id=employee_id, date__gte=effective_date)
        service = TimesheetSnapshotService()
        for entry in query:
            service.snapshot_contract_info(entry)
            entry.save(need_clean=False)


def _process_backdated_contract_entries(employee_id: int, effective_date: date):
    """
    Handle creation of missing timesheet entries and monthly timesheets for backdated contracts.
    """
    today = date.today()

    # Step 1: Check if timesheet entry exists at effective date
    if TimeSheetEntry.objects.filter(employee_id=employee_id, date=effective_date).exists():
        return

    # Step 2: Determine the gap
    # Find the first entry AFTER the effective date
    first_existing = (
        TimeSheetEntry.objects.filter(
            employee_id=employee_id,
            date__gt=effective_date,
        )
        .order_by("date")
        .first()
    )

    # If existing entry found, fill up to that point. Otherwise fill up to today.
    fill_end_date = first_existing.date if first_existing else today

    start_year, start_month = effective_date.year, effective_date.month
    end_year, end_month = fill_end_date.year, fill_end_date.month

    # Step 3 & 4: Create entries and monthly timesheets for the gap
    months_processed = []
    for year in range(start_year, end_year + 1):
        first_m = start_month if year == start_year else 1
        last_m = end_month if year == end_year else 12

        for month in range(first_m, last_m + 1):
            # Don't process future months if fill_end_date extends beyond today
            if date(year, month, 1) > today:
                continue

            create_entries_for_employee_month(employee_id, year, month)
            create_monthly_timesheet_for_employee(employee_id, year, month)
            months_processed.append((year, month))

    # Step 5: Mark subsequent monthly timesheets as need_refresh
    if first_existing and months_processed:
        last_processed_year, last_processed_month = months_processed[-1]
        last_processed_key = f"{last_processed_year:04d}{last_processed_month:02d}"

        # Update all future monthly timesheets
        EmployeeMonthlyTimesheet.objects.filter(employee_id=employee_id, month_key__gt=last_processed_key).update(
            need_refresh=True
        )


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
