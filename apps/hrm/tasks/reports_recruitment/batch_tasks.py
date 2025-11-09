"""Batch Celery task for recruitment reports aggregation.

This module contains the scheduled batch task that runs at midnight to aggregate
recruitment reporting data for today and affected historical dates.
"""

import logging
from datetime import date
from typing import Any

from django.db import transaction

from apps.hrm.models import (
    Block,
    Branch,
    Department,
    RecruitmentCandidate,
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


def _recruitment_batch_aggregation(report_date: date, org_unit_ids: list[tuple]) -> None:
    """Business logic for recruitment batch aggregation.
    
    Aggregates recruitment reports for a specific date and org units.
    
    Args:
        report_date: The date to aggregate reports for
        org_unit_ids: List of (branch_id, block_id, department_id) tuples
    """
    if not org_unit_ids:
        return
    
    # Fetch all org units in bulk BEFORE loop (optimization)
    branch_ids = {unit[0] for unit in org_unit_ids if unit[0]}
    block_ids = {unit[1] for unit in org_unit_ids if unit[1]}
    department_ids = {unit[2] for unit in org_unit_ids if unit[2]}

    branches = {b.id: b for b in Branch.objects.filter(id__in=branch_ids)}
    blocks = {bl.id: bl for bl in Block.objects.filter(id__in=block_ids)}
    departments = {d.id: d for d in Department.objects.filter(id__in=department_ids)}

    # Process each org unit for this date
    with transaction.atomic():
        for branch_id, block_id, department_id in org_unit_ids:
            # Early return pattern - skip if conditions don't match
            if not (branch_id and block_id and department_id):
                continue
            
            branch = branches.get(branch_id)
            block = blocks.get(block_id)
            department = departments.get(department_id)

            if not (branch and block and department):
                continue
            
            # Aggregate all recruitment report types for this date/org unit
            _aggregate_recruitment_source_for_date(report_date, branch, block, department)
            _aggregate_recruitment_channel_for_date(report_date, branch, block, department)
            _aggregate_recruitment_cost_for_date(report_date, branch, block, department)
            _aggregate_hired_candidate_for_date(report_date, branch, block, department)
            _update_staff_growth_for_recruitment(report_date, branch, block, department)


# Create the actual Celery task using the framework
# Framework handles: date detection, org unit scoping, retry, transactions, error logging
aggregate_recruitment_reports_batch = create_batch_task(
    task_name='aggregate_recruitment_reports_batch',
    queryset=RecruitmentCandidate.objects.filter(
        status=RecruitmentCandidate.Status.HIRED,
        onboard_date__isnull=False,
    ),
    aggregation_function=_recruitment_batch_aggregation,
    queue='reports_batch',
    date_field='onboard_date',  # Use onboard_date instead of default 'date'
)
