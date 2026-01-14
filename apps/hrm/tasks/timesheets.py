"""Celery tasks for creating/updating timesheet entries and monthly aggregates.

This file contains two main tasks:
- prepare_monthly_timesheets: creates timesheet entries and monthly rows for all or a specific employee/month
- update_monthly_timesheet_async: refreshes monthly aggregates and clears need_refresh flags
"""

import logging
from datetime import date

from celery import shared_task
from django.db.models import Q
from django.utils import timezone

from apps.hrm.constants import ProposalType
from apps.hrm.models import (
    Employee,
    EmployeeMonthlyTimesheet,
    Proposal,
    ProposalTimeSheetEntry,
)
from apps.hrm.models.timesheet import TimeSheetEntry
from apps.hrm.services.timesheet_calculator import TimesheetCalculator
from apps.hrm.services.timesheets import (
    create_entries_for_employee_month,
    create_entries_for_month_all,
    create_monthly_timesheet_for_employee,
    create_monthly_timesheets_for_month_all,
)

logger = logging.getLogger(__name__)


@shared_task
def prepare_monthly_timesheets(
    employee_id: int | None = None,
    year: int | None = None,
    month: int | None = None,
    increment_leave: bool = True,
):
    """Prepare timesheet entries and monthly rows either for a single employee or all active employees.

    Also handles incrementing available_leave_days for eligible employees when processing all employees.

    - If employee_id is None: create entries for all active employees for given year/month (defaults to current)
    - If employee_id provided: create entries for that employee and month
    - If increment_leave is True (default): increment available_leave_days by 1 for eligible employees
    """
    today = date.today()
    if not year or not month:
        year = today.year
        month = today.month

    if employee_id:
        create_entries_for_employee_month(employee_id, year, month)
        create_monthly_timesheet_for_employee(employee_id, year, month)
        return {"success": True, "employee_id": employee_id, "year": year, "month": month}

    # otherwise do for all employees
    create_entries_for_month_all(year, month)
    timesheets = create_monthly_timesheets_for_month_all(year, month)

    # Update available leave days for eligible employees based on the calculated monthly timesheet
    updated_leave = 0
    if increment_leave:
        for ts in timesheets:
            Employee.objects.filter(pk=ts.employee_id).update(available_leave_days=ts.remaining_leave_days)
        updated_leave = len(timesheets)
        logger.info("prepare_monthly_timesheets: updated leave days for %s employees", updated_leave)

    return {"success": True, "employee_id": None, "year": year, "month": month, "leave_updated": updated_leave}


@shared_task
def update_monthly_timesheet_async(
    employee_id: int | None = None, year: int | None = None, month: int | None = None, fields: list[str] | None = None
):
    """Refresh monthly timesheet rows. If employee/month not provided, process all rows with need_refresh=True.

    This task can be called by signals or scheduled periodically.
    """
    if employee_id and year and month:
        EmployeeMonthlyTimesheet.refresh_for_employee_month(employee_id, year, month, fields)
        return {"success": True, "employee_id": employee_id, "year": year, "month": month}

    # process all flagged rows
    qs = EmployeeMonthlyTimesheet.objects.filter(need_refresh=True)
    count = 0
    for row in qs.iterator():
        try:
            yr = row.report_date.year
            mo = row.report_date.month
            EmployeeMonthlyTimesheet.refresh_for_employee_month(row.employee_id, yr, mo, fields)
            count += 1
        except Exception as e:
            logger.exception("Failed to refresh monthly timesheet for %s: %s", row, e)
    return {"success": True, "processed": count}


@shared_task
def recalculate_timesheets(employee_id: int, start_date_str: str) -> dict:
    """Recalculate timesheet entries for an employee from a start date until today.

    This ensures that changes in employee status/type are reflected in
    dependent fields like `count_for_payroll`.

    Args:
        employee_id: The ID of the employee.
        start_date_str: ISO format string of the start date (inclusive).

    Returns:
        Dict with success status and count of updated entries.
    """
    try:
        start_date = date.fromisoformat(start_date_str)
        today = date.today()

        entries = TimeSheetEntry.objects.filter(employee_id=employee_id, date__gte=start_date, date__lte=today)
        count = 0

        for entry in entries:
            # We must use the calculator to update logic
            calc = TimesheetCalculator(entry)
            calc.compute_all()
            entry.save()
            count += 1

        logger.info("Recalculated %d timesheet entries for employee %s from %s", count, employee_id, start_date_str)
        return {"success": True, "updated_count": count}
    except Exception as e:
        logger.exception(
            "Failed to recalculate timesheets for employee %s from %s: %s", employee_id, start_date_str, e
        )
        return {"success": False, "error": str(e)}


@shared_task
def finalize_daily_timesheets() -> dict:
    """End-of-day task to finalize statuses for the day.

    Runs daily (e.g., at 17:30).
    Logic:
    - Queries all TimeSheetEntry for today.
    - If status is None or implicitly ABSENT (no logs), sets status = ABSENT.
    - If status is SINGLE_PUNCH (1 log), ensures working_days logic is applied (Calculator handles this).
    - Saving the entry triggers recalculation via clean/save logic usually, but here we invoke Calculator explicitly to be sure.
    """
    today = timezone.localdate()
    # Or just today = date.today() depending on TZ settings.
    # Use localdate for safety if server has UTC.

    entries = TimeSheetEntry.objects.filter(date=today)
    count = 0

    for entry in entries:
        # Re-run calculator to finalize status based on logs (or lack thereof)
        # The calculator logic handles "No logs -> ABSENT" and "1 log -> SINGLE_PUNCH"

        calc = TimesheetCalculator(entry)
        calc.compute_all(is_finalizing=True)
        entry.save()
        count += 1

    return {"success": True, "finalized_count": count, "date": today}


def _get_proposal_date_ranges(proposal):
    """Helper to extract date ranges for proposal types with start/end dates."""
    mapping = {
        ProposalType.LATE_EXEMPTION: ("late_exemption_start_date", "late_exemption_end_date"),
        ProposalType.POST_MATERNITY_BENEFITS: (
            "post_maternity_benefits_start_date",
            "post_maternity_benefits_end_date",
        ),
        ProposalType.MATERNITY_LEAVE: ("maternity_leave_start_date", "maternity_leave_end_date"),
        ProposalType.PAID_LEAVE: ("paid_leave_start_date", "paid_leave_end_date"),
        ProposalType.UNPAID_LEAVE: ("unpaid_leave_start_date", "unpaid_leave_end_date"),
    }

    fields = mapping.get(proposal.proposal_type)
    if fields:
        start = getattr(proposal, fields[0])
        end = getattr(proposal, fields[1])
        return start, end
    return None, None


@shared_task
def link_proposals_to_timesheet_entry_task(timesheet_entry_id: int) -> dict:
    """Link existing proposals to a newly created timesheet entry.

    This task searches for proposals that affect the timesheet entry's date
    (e.g., Leave, Overtime, Complaint) and syncs ProposalTimeSheetEntry records.
    """
    try:
        entry = TimeSheetEntry.objects.get(pk=timesheet_entry_id)
    except TimeSheetEntry.DoesNotExist:
        logger.warning("TimeSheetEntry %s not found.", timesheet_entry_id)
        return {"success": False, "error": "TimeSheetEntry not found"}

    date_obj = entry.date
    employee = entry.employee

    # 1. Date range based proposals
    # Explicitly constructing Q for each type to avoid 'or' confusion and check specific fields safely
    range_q = Q(pk__in=[])

    # Late Exemption
    range_q |= Q(
        proposal_type=ProposalType.LATE_EXEMPTION,
        late_exemption_start_date__lte=date_obj,
        late_exemption_end_date__gte=date_obj,
    )
    # Post Maternity
    range_q |= Q(
        proposal_type=ProposalType.POST_MATERNITY_BENEFITS,
        post_maternity_benefits_start_date__lte=date_obj,
        post_maternity_benefits_end_date__gte=date_obj,
    )
    # Maternity Leave
    range_q |= Q(
        proposal_type=ProposalType.MATERNITY_LEAVE,
        maternity_leave_start_date__lte=date_obj,
        maternity_leave_end_date__gte=date_obj,
    )
    # Paid Leave
    range_q |= Q(
        proposal_type=ProposalType.PAID_LEAVE,
        paid_leave_start_date__lte=date_obj,
        paid_leave_end_date__gte=date_obj,
    )
    # Unpaid Leave
    range_q |= Q(
        proposal_type=ProposalType.UNPAID_LEAVE,
        unpaid_leave_start_date__lte=date_obj,
        unpaid_leave_end_date__gte=date_obj,
    )

    # 2. Specific date proposals (Complaint)
    complaint_q = Q(
        proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
        timesheet_entry_complaint_complaint_date=date_obj,
    )

    # 3. Overtime (via relation)
    # Query proposals that have an overtime entry on this date
    overtime_q = Q(proposal_type=ProposalType.OVERTIME_WORK, overtime_entries__date=date_obj)

    # Combine logic: Created by employee AND (ranges OR complaint OR overtime)
    final_q = Q(created_by=employee) & (range_q | complaint_q | overtime_q)

    # Get relevant proposal IDs
    relevant_proposal_ids = set(Proposal.objects.filter(final_q).values_list("id", flat=True))

    # Get existing linked proposal IDs
    existing_linked_ids = set(
        ProposalTimeSheetEntry.objects.filter(timesheet_entry=entry).values_list("proposal_id", flat=True)
    )

    # Determine changes
    to_add_ids = relevant_proposal_ids - existing_linked_ids
    to_remove_ids = existing_linked_ids - relevant_proposal_ids

    # Bulk Delete
    if to_remove_ids:
        deleted_count, _ = ProposalTimeSheetEntry.objects.filter(
            timesheet_entry=entry, proposal_id__in=to_remove_ids
        ).delete()
        logger.info("Unlinked %s proposals from entry %s", deleted_count, entry.id)

    # Bulk Create
    if to_add_ids:
        new_links = [ProposalTimeSheetEntry(proposal_id=pid, timesheet_entry=entry) for pid in to_add_ids]
        # NOTE: ignore_conflicts=True to handle potential race conditions safely
        objs = ProposalTimeSheetEntry.objects.bulk_create(new_links, ignore_conflicts=True)
        logger.info("Linked %s proposals to entry %s", len(objs), entry.id)

    return {"success": True, "added": len(to_add_ids), "removed": len(to_remove_ids)}


@shared_task
def link_timesheet_entries_to_proposal_task(proposal_id: int) -> dict:
    """Link existing timesheet entries to a newly created/updated proposal.

    This task searches for timesheet entries for the proposal's creator within
    the proposal's effective date range and syncs ProposalTimeSheetEntry records.
    """
    try:
        proposal = Proposal.objects.get(pk=proposal_id)
    except Proposal.DoesNotExist:
        logger.warning("Proposal %s not found.", proposal_id)
        return {"success": False, "error": "Proposal not found"}

    creator = proposal.created_by
    entries_q = Q(pk__in=[])

    # Identify relevant dates based on proposal type
    if proposal.proposal_type in [
        ProposalType.LATE_EXEMPTION,
        ProposalType.POST_MATERNITY_BENEFITS,
        ProposalType.MATERNITY_LEAVE,
        ProposalType.PAID_LEAVE,
        ProposalType.UNPAID_LEAVE,
    ]:
        # Use helper to get start/end dates based on type, avoiding long chain of ORs
        start, end = _get_proposal_date_ranges(proposal)

        if start and end:
            entries_q = Q(date__gte=start, date__lte=end)

    elif proposal.proposal_type == ProposalType.TIMESHEET_ENTRY_COMPLAINT:
        if proposal.timesheet_entry_complaint_complaint_date:
            entries_q = Q(date=proposal.timesheet_entry_complaint_complaint_date)

    elif proposal.proposal_type == ProposalType.OVERTIME_WORK:
        # Overtime entries might be multiple non-contiguous dates
        ot_dates = proposal.overtime_entries.values_list("date", flat=True)
        if ot_dates:
            entries_q = Q(date__in=ot_dates)

    # Find relevant timesheet entries
    relevant_timesheet_ids = set(
        TimeSheetEntry.objects.filter(entries_q, employee=creator).values_list("id", flat=True)
    )

    # Get existing linked timesheet IDs
    existing_linked_ids = set(
        ProposalTimeSheetEntry.objects.filter(proposal=proposal).values_list("timesheet_entry_id", flat=True)
    )

    # Determine changes
    to_add_ids = relevant_timesheet_ids - existing_linked_ids
    to_remove_ids = existing_linked_ids - relevant_timesheet_ids

    # Bulk Delete
    if to_remove_ids:
        deleted_count, _ = ProposalTimeSheetEntry.objects.filter(
            proposal=proposal, timesheet_entry_id__in=to_remove_ids
        ).delete()
        logger.info("Unlinked %s timesheet entries from proposal %s", deleted_count, proposal.id)

    # Bulk Create
    if to_add_ids:
        new_links = [ProposalTimeSheetEntry(proposal=proposal, timesheet_entry_id=tid) for tid in to_add_ids]
        # NOTE: ignore_conflicts=True to handle potential race conditions safely
        objs = ProposalTimeSheetEntry.objects.bulk_create(new_links, ignore_conflicts=True)
        logger.info("Linked %s timesheet entries to proposal %s", len(objs), proposal.id)

    return {"success": True, "added": len(to_add_ids), "removed": len(to_remove_ids)}
