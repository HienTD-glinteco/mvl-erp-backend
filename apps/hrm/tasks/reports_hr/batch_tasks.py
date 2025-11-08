"""Batch Celery task for HR reports aggregation.

This module contains the scheduled batch task that runs at midnight to aggregate
HR reporting data for today and affected historical dates.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from celery import shared_task
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from apps.hrm.models import (
    Block,
    Branch,
    Department,
    EmployeeWorkHistory,
)
from .helpers import (
    AGGREGATION_MAX_RETRIES,
    AGGREGATION_RETRY_DELAY,
    MAX_REPORT_LOOKBACK_DAYS,
    _aggregate_employee_status_for_date,
    _aggregate_staff_growth_for_date,
)

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=AGGREGATION_MAX_RETRIES)
def aggregate_hr_reports_batch(self, target_date: str | None = None) -> dict[str, Any]:
    """Batch aggregation of HR reports for today and affected historical dates.

    This scheduled task:
    1. Checks if any work history records were modified/created today
    2. If yes, finds the earliest affected date (within 1 year lookback)
    3. Re-aggregates ALL report records from earliest date to today for affected org units
    4. If no changes today, only processes today's date

    Note: When past records are modified, ALL reports from that date onwards become
    incorrect and must be recalculated. We can only scope by org unit (branch/block/dept).

    Args:
        self: Celery task instance
        target_date: Specific date to aggregate (ISO format YYYY-MM-DD).
                    If None, uses today and checks for historical changes.

    Returns:
        dict: Aggregation result with success status and metadata
    """
    try:
        today = timezone.now().date()

        if target_date:
            # Specific date provided - process only that date
            report_date = datetime.fromisoformat(target_date).date()
            dates_to_process = [report_date]
            affected_org_units = None  # Process all org units for this date
        else:
            # Check for work histories modified/created today
            cutoff_date = today - timedelta(days=MAX_REPORT_LOOKBACK_DAYS)

            # Find work histories that were created or updated today
            modified_today = EmployeeWorkHistory.objects.filter(
                Q(created_at__date=today) | Q(updated_at__date=today),
                date__gte=cutoff_date
            ).select_related('branch', 'block', 'department')

            if not modified_today.exists():
                # No changes today - just process today's date
                dates_to_process = [today]
                affected_org_units = None
            else:
                # Find the earliest affected date and all affected org units
                earliest_date = modified_today.aggregate(
                    min_date=models.Min('date')
                )['min_date']

                # Get all unique org units affected by these changes using efficient query
                affected_org_units = set(
                    modified_today.values_list("branch_id", "block_id", "department_id").distinct()
                )

                # Process ALL dates from earliest to today for affected org units
                # Even dates with no work history must be processed because reports are cumulative
                dates_to_process = []
                current_date = earliest_date
                while current_date <= today:
                    dates_to_process.append(current_date)
                    current_date += timedelta(days=1)

                logger.info(
                    f"Detected {modified_today.count()} work history changes today. "
                    f"Will re-aggregate ALL dates from {earliest_date} to {today} "
                    f"for {len(affected_org_units)} org units."
                )

        if not dates_to_process:
            logger.info("No dates to process for HR reports batch aggregation")
            return {"success": True, "dates_processed": 0, "org_units_processed": 0}

        logger.info(
            f"Starting batch HR reports aggregation for {len(dates_to_process)} dates"
        )

        total_org_units = 0

        for process_date in dates_to_process:
            # Get org units to process for this date
            if affected_org_units:
                # Process only affected org units
                org_unit_ids = list(affected_org_units)
            else:
                # Process all org units with work history on this date
                org_unit_ids = list(
                    EmployeeWorkHistory.objects.filter(date=process_date)
                    .values_list("branch_id", "block_id", "department_id")
                    .distinct()
                )

            if not org_unit_ids:
                continue

            # Fetch all org units in bulk
            branch_ids = {unit[0] for unit in org_unit_ids if unit[0]}
            block_ids = {unit[1] for unit in org_unit_ids if unit[1]}
            department_ids = {unit[2] for unit in org_unit_ids if unit[2]}

            branches = {b.id: b for b in Branch.objects.filter(id__in=branch_ids)}
            blocks = {bl.id: bl for bl in Block.objects.filter(id__in=block_ids)}
            departments = {d.id: d for d in Department.objects.filter(id__in=department_ids)}

            # Process each org unit for this date
            with transaction.atomic():
                for branch_id, block_id, department_id in org_unit_ids:
                    if branch_id and block_id and department_id:
                        branch = branches.get(branch_id)
                        block = blocks.get(block_id)
                        department = departments.get(department_id)

                        if branch and block and department:
                            _aggregate_staff_growth_for_date(process_date, branch, block, department)
                            _aggregate_employee_status_for_date(process_date, branch, block, department)
                            total_org_units += 1

        logger.info(
            f"Batch HR reports aggregation complete. "
            f"Processed {len(dates_to_process)} dates, {total_org_units} org units."
        )

        return {
            "success": True,
            "dates_processed": len(dates_to_process),
            "org_units_processed": total_org_units,
        }

    except Exception as e:
        logger.exception(f"Error in batch HR reports aggregation: {str(e)}")
        try:
            raise self.retry(exc=e, countdown=AGGREGATION_RETRY_DELAY * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            return {"success": False, "error": str(e)}
