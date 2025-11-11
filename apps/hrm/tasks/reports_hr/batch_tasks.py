"""Batch Celery task for HR reports aggregation.

This module contains the scheduled batch task that runs at midnight to aggregate
HR reporting data based on reports marked with need_refresh=True.
"""

import logging
from datetime import date, timedelta

from celery import shared_task
from django.db import transaction
from django.db.models import Min
from django.utils import timezone

from apps.hrm.models import (
    Block,
    Branch,
    Department,
    EmployeeStatusBreakdownReport,
    StaffGrowthReport,
)

from .helpers import (
    _aggregate_employee_status_for_date,
    _aggregate_staff_growth_for_date,
)

logger = logging.getLogger(__name__)


def _get_reports_needing_refresh() -> tuple[date | None, list[tuple[int, int, int]]]:
    """Get earliest report date and org units needing refresh.

    Queries report models for records marked with need_refresh=True.
    Returns the earliest date that needs processing and all affected org units.

    Returns:
        Tuple of (earliest_date, list of org_unit tuples)
        earliest_date is None if no reports need refresh
    """
    # Find earliest date needing refresh across all report models
    staff_growth_date = StaffGrowthReport.objects.filter(need_refresh=True).aggregate(Min("report_date"))[
        "report_date__min"
    ]

    status_breakdown_date = EmployeeStatusBreakdownReport.objects.filter(need_refresh=True).aggregate(
        Min("report_date")
    )["report_date__min"]

    # Get the earliest of the two
    dates = [d for d in [staff_growth_date, status_breakdown_date] if d is not None]
    if not dates:
        return None, []

    earliest_date = min(dates)

    # Get all org units that need refresh from earliest date onwards
    today = timezone.now().date()
    org_units_set = set()

    # Collect org units from StaffGrowthReport
    for report in (
        StaffGrowthReport.objects.filter(need_refresh=True, report_date__gte=earliest_date, report_date__lte=today)
        .values("branch_id", "block_id", "department_id")
        .distinct()
    ):
        org_units_set.add((report["branch_id"], report["block_id"], report["department_id"]))

    # Collect org units from EmployeeStatusBreakdownReport
    for report in (
        EmployeeStatusBreakdownReport.objects.filter(
            need_refresh=True, report_date__gte=earliest_date, report_date__lte=today
        )
        .values("branch_id", "block_id", "department_id")
        .distinct()
    ):
        org_units_set.add((report["branch_id"], report["block_id"], report["department_id"]))

    return earliest_date, list(org_units_set)


@shared_task(queue="reports_batch")
def aggregate_hr_reports_batch() -> int:
    """Business logic for HR batch aggregation using need_refresh flag.

    This function:
    1. Finds all reports marked with need_refresh=True
    2. Identifies earliest date and affected org units
    3. Processes all dates from earliest to today for those org units
    4. Clears need_refresh flag after successful processing

    Returns:
        Number of dates successfully processed
    """
    earliest_date, org_units = _get_reports_needing_refresh()

    if earliest_date is None or not org_units:
        logger.info("No HR reports need refresh")
        return 0

    today = timezone.now().date()
    logger.info(f"Batch aggregating HR reports from {earliest_date} to {today} for {len(org_units)} org units")

    # Fetch all org units in bulk BEFORE loop (optimization per code review)
    branch_ids = {unit[0] for unit in org_units if unit[0]}
    block_ids = {unit[1] for unit in org_units if unit[1]}
    department_ids = {unit[2] for unit in org_units if unit[2]}

    branches = {b.id: b for b in Branch.objects.filter(id__in=branch_ids)}
    blocks = {bl.id: bl for bl in Block.objects.filter(id__in=block_ids)}
    departments = {d.id: d for d in Department.objects.filter(id__in=department_ids)}

    dates_processed = 0
    current_date = earliest_date

    # Process each date from earliest to today
    while current_date <= today:
        with transaction.atomic():
            for branch_id, block_id, department_id in org_units:
                # Early return pattern - skip if conditions don't match
                if not (branch_id and block_id and department_id):
                    continue

                branch = branches.get(branch_id)
                block = blocks.get(block_id)
                department = departments.get(department_id)

                if not (branch and block and department):
                    continue

                # Aggregate both types of HR reports
                _aggregate_staff_growth_for_date(current_date, branch, block, department)
                _aggregate_employee_status_for_date(current_date, branch, block, department)

            # Clear need_refresh flag for this date after successful processing
            StaffGrowthReport.objects.filter(report_date=current_date).update(need_refresh=False)

            EmployeeStatusBreakdownReport.objects.filter(report_date=current_date).update(need_refresh=False)

        dates_processed += 1
        current_date += timedelta(days=1)

    logger.info(f"Processed {dates_processed} dates for HR reports")
    return dates_processed
