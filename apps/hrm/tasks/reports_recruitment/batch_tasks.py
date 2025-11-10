"""Batch Celery task for recruitment reports aggregation.

This module contains the scheduled batch task that runs at midnight to aggregate
recruitment reporting data based on reports marked with need_refresh=True.
"""

import logging
from datetime import date, timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.hrm.models import (
    Block,
    Branch,
    Department,
    HiredCandidateReport,
    RecruitmentChannelReport,
    RecruitmentCostReport,
    RecruitmentSourceReport,
)
from ..report_framework import create_batch_task
from .helpers import (
    _aggregate_hired_candidate_for_date,
    _aggregate_recruitment_channel_for_date,
    _aggregate_recruitment_cost_for_date,
    _aggregate_recruitment_source_for_date,
    _update_staff_growth_for_recruitment,
)

logger = logging.getLogger(__name__)


def _get_recruitment_reports_needing_refresh() -> tuple[date | None, list[tuple[int, int, int]]]:
    """Get earliest report date and org units needing refresh for recruitment reports.
    
    Queries all 4 recruitment report models for records marked with need_refresh=True.
    Returns the earliest date that needs processing and all affected org units.
    
    Returns:
        Tuple of (earliest_date, list of org_unit tuples)
        earliest_date is None if no reports need refresh
    """
    from django.db.models import Min

    # Find earliest date needing refresh across all recruitment report models
    source_date = RecruitmentSourceReport.objects.filter(
        need_refresh=True
    ).aggregate(Min('report_date'))['report_date__min']
    
    channel_date = RecruitmentChannelReport.objects.filter(
        need_refresh=True
    ).aggregate(Min('report_date'))['report_date__min']
    
    cost_date = RecruitmentCostReport.objects.filter(
        need_refresh=True
    ).aggregate(Min('report_date'))['report_date__min']
    
    hired_date = HiredCandidateReport.objects.filter(
        need_refresh=True
    ).aggregate(Min('report_date'))['report_date__min']
    
    # Get the earliest of all dates
    dates = [d for d in [source_date, channel_date, cost_date, hired_date] if d is not None]
    if not dates:
        return None, []
    
    earliest_date = min(dates)
    
    # Get all org units that need refresh from earliest date onwards
    today = timezone.now().date()
    org_units_set = set()
    
    # Collect org units from all recruitment report models
    for report in RecruitmentSourceReport.objects.filter(
        need_refresh=True,
        report_date__gte=earliest_date,
        report_date__lte=today
    ).values('branch_id', 'block_id', 'department_id').distinct():
        org_units_set.add((
            report['branch_id'],
            report['block_id'],
            report['department_id']
        ))
    
    for report in RecruitmentChannelReport.objects.filter(
        need_refresh=True,
        report_date__gte=earliest_date,
        report_date__lte=today
    ).values('branch_id', 'block_id', 'department_id').distinct():
        org_units_set.add((
            report['branch_id'],
            report['block_id'],
            report['department_id']
        ))
    
    for report in RecruitmentCostReport.objects.filter(
        need_refresh=True,
        report_date__gte=earliest_date,
        report_date__lte=today
    ).values('branch_id', 'block_id', 'department_id').distinct():
        org_units_set.add((
            report['branch_id'],
            report['block_id'],
            report['department_id']
        ))
    
    for report in HiredCandidateReport.objects.filter(
        need_refresh=True,
        report_date__gte=earliest_date,
        report_date__lte=today
    ).values('branch_id', 'block_id', 'department_id').distinct():
        org_units_set.add((
            report['branch_id'],
            report['block_id'],
            report['department_id']
        ))
    
    return earliest_date, list(org_units_set)


def _recruitment_batch_aggregation_with_refresh() -> int:
    """Business logic for recruitment batch aggregation using need_refresh flag.
    
    This function:
    1. Finds all reports marked with need_refresh=True
    2. Identifies earliest date and affected org units
    3. Processes all dates from earliest to today for those org units
    4. Clears need_refresh flag after successful processing
    
    Returns:
        Number of dates successfully processed
    """
    earliest_date, org_units = _get_recruitment_reports_needing_refresh()
    
    if earliest_date is None or not org_units:
        logger.info("No recruitment reports need refresh")
        return 0
    
    today = timezone.now().date()
    logger.info(
        f"Batch aggregating recruitment reports from {earliest_date} to {today} "
        f"for {len(org_units)} org units"
    )
    
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
                
                # Aggregate all recruitment report types
                _aggregate_recruitment_source_for_date(current_date, branch, block, department)
                _aggregate_recruitment_channel_for_date(current_date, branch, block, department)
                _aggregate_recruitment_cost_for_date(current_date, branch, block, department)
                _aggregate_hired_candidate_for_date(current_date, branch, block, department)
                _update_staff_growth_for_recruitment(current_date, branch, block, department)
            
            # Clear need_refresh flag for this date after successful processing
            RecruitmentSourceReport.objects.filter(
                report_date=current_date
            ).update(need_refresh=False)
            
            RecruitmentChannelReport.objects.filter(
                report_date=current_date
            ).update(need_refresh=False)
            
            RecruitmentCostReport.objects.filter(
                report_date=current_date
            ).update(need_refresh=False)
            
            HiredCandidateReport.objects.filter(
                report_date=current_date
            ).update(need_refresh=False)
        
        dates_processed += 1
        current_date += timedelta(days=1)
    
    logger.info(f"Processed {dates_processed} dates for recruitment reports")
    return dates_processed


# Create the actual Celery task using the framework
aggregate_recruitment_reports_batch = create_batch_task(
    name='aggregate_recruitment_reports_batch',
    batch_aggregate_func=_recruitment_batch_aggregation_with_refresh,
    queue='reports_batch'
)
