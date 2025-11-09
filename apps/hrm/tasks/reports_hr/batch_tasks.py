"""Batch Celery task for HR reports aggregation.

This module contains the scheduled batch task that runs at midnight to aggregate
HR reporting data for today and affected historical dates.
"""

import logging
from datetime import date, datetime, timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.hrm.models import (
    Block,
    Branch,
    Department,
    EmployeeWorkHistory,
)
from ..report_framework import create_batch_task
from .helpers import (
    MAX_REPORT_LOOKBACK_DAYS,
    _aggregate_employee_status_for_date,
    _aggregate_staff_growth_for_date,
)

logger = logging.getLogger(__name__)


def _get_modified_work_history_query(start_date: date, end_date: date) -> Any:
    """Query function to get work histories modified between dates.
    
    This function is used by the framework to detect which records were modified.
    
    Args:
        start_date: Start date for filtering
        end_date: End date for filtering
        
    Returns:
        QuerySet of EmployeeWorkHistory records
    """
    from django.db.models import Q
    
    today = timezone.now().date()
    cutoff_date = today - timedelta(days=MAX_REPORT_LOOKBACK_DAYS)
    
    return EmployeeWorkHistory.objects.filter(
        Q(created_at__date__gte=start_date, created_at__date__lte=end_date) |
        Q(updated_at__date__gte=start_date, updated_at__date__lte=end_date),
        date__gte=cutoff_date
    ).select_related('branch', 'block', 'department')


def _hr_batch_aggregation(
    process_date: date,
    org_units: list[tuple[int, int, int]]
) -> int:
    """Business logic for HR batch aggregation.
    
    Aggregates HR reports for a specific date and list of org units.
    The framework handles detection of which dates and org units to process.
    
    Args:
        process_date: Date to aggregate reports for
        org_units: List of (branch_id, block_id, department_id) tuples
        
    Returns:
        Number of org units successfully processed
    """
    if not org_units:
        return 0
    
    logger.info(
        f"Batch aggregating HR reports for {process_date} "
        f"with {len(org_units)} org units"
    )
    
    # Fetch all org units in bulk BEFORE loop (optimization per code review)
    branch_ids = {unit[0] for unit in org_units if unit[0]}
    block_ids = {unit[1] for unit in org_units if unit[1]}
    department_ids = {unit[2] for unit in org_units if unit[2]}
    
    branches = {b.id: b for b in Branch.objects.filter(id__in=branch_ids)}
    blocks = {bl.id: bl for bl in Block.objects.filter(id__in=block_ids)}
    departments = {d.id: d for d in Department.objects.filter(id__in=department_ids)}
    
    processed_count = 0
    
    # Process each org unit for this date
    with transaction.atomic():
        for branch_id, block_id, department_id in org_units:
            # Early return pattern - skip if conditions don't match (per code review)
            if not (branch_id and block_id and department_id):
                continue
            
            branch = branches.get(branch_id)
            block = blocks.get(block_id)
            department = departments.get(department_id)
            
            if not (branch and block and department):
                continue
            
            # Aggregate both types of HR reports
            _aggregate_staff_growth_for_date(process_date, branch, block, department)
            _aggregate_employee_status_for_date(process_date, branch, block, department)
            processed_count += 1
    
    return processed_count


# Create the actual Celery task using the framework
aggregate_hr_reports_batch = create_batch_task(
    name='aggregate_hr_reports_batch',
    batch_aggregate_func=_hr_batch_aggregation,
    get_modified_model_query=_get_modified_work_history_query,
    queue='reports_batch'
)

