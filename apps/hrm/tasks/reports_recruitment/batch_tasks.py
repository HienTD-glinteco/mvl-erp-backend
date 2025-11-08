"""Scheduled batch recruitment reports aggregation tasks."""

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from celery import shared_task
from django.db import models, transaction
from django.db.models import Count, F, Min, Q, Sum
from django.utils import timezone

from apps.hrm.constants import RecruitmentSourceType
from apps.hrm.models import (
    Block,
    Branch,
    Department,
    HiredCandidateReport,
    RecruitmentCandidate,
    RecruitmentChannel,
    RecruitmentChannelReport,
    RecruitmentCostReport,
    RecruitmentExpense,
    RecruitmentSource,
    RecruitmentSourceReport,
    StaffGrowthReport,
)

logger = logging.getLogger(__name__)

# Constants
AGGREGATION_MAX_RETRIES = 3
AGGREGATION_RETRY_DELAY = 60  # 1 minute
MAX_REPORT_LOOKBACK_DAYS = 365  # Maximum 1 year lookback for batch reports


from .helpers import (
    _aggregate_hired_candidate_for_date,
    _aggregate_recruitment_channel_for_date,
    _aggregate_recruitment_cost_for_date,
    _aggregate_recruitment_source_for_date,
    _update_staff_growth_for_recruitment,
)

@shared_task(bind=True, max_retries=AGGREGATION_MAX_RETRIES)
def aggregate_recruitment_reports_batch(self, target_date: str | None = None) -> dict[str, Any]:
    """Batch aggregation of recruitment reports for today and affected historical dates.

    This scheduled task:
    1. Checks if any recruitment candidates were modified/created today
    2. If yes, finds the earliest affected onboard date (within 1 year lookback)
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
            # Check for hired candidates modified/created today
            cutoff_date = today - timedelta(days=MAX_REPORT_LOOKBACK_DAYS)
            
            # Find hired candidates that were created or updated today
            modified_today = RecruitmentCandidate.objects.filter(
                Q(created_at__date=today) | Q(updated_at__date=today),
                status=RecruitmentCandidate.Status.HIRED,
                onboard_date__gte=cutoff_date,
                onboard_date__isnull=False,
            ).select_related('branch', 'block', 'department')
            
            if not modified_today.exists():
                # No changes today - just process today's hired candidates
                dates_to_process = [today]
                affected_org_units = None
            else:
                # Find the earliest affected onboard date and all affected org units
                earliest_date = modified_today.aggregate(
                    min_date=models.Min('onboard_date')
                )['min_date']
                
                # Get all unique org units affected by these changes using efficient query
                affected_org_units = set(
                    modified_today.values_list("branch_id", "block_id", "department_id").distinct()
                )
                
                # Process ALL dates from earliest to today for affected org units
                # Even dates with no candidates must be processed because reports are cumulative
                dates_to_process = []
                current_date = earliest_date
                while current_date <= today:
                    dates_to_process.append(current_date)
                    current_date += timedelta(days=1)
                
                logger.info(
                    f"Detected {modified_today.count()} candidate changes today. "
                    f"Will re-aggregate ALL dates from {earliest_date} to {today} "
                    f"for {len(affected_org_units)} org units."
                )

        if not dates_to_process:
            logger.info("No dates to process for recruitment reports batch aggregation")
            return {"success": True, "dates_processed": 0, "org_units_processed": 0}

        logger.info(
            f"Starting batch recruitment reports aggregation for {len(dates_to_process)} dates"
        )

        total_org_units = 0
        
        for process_date in dates_to_process:
            # Get org units to process for this date
            if affected_org_units:
                # Process only affected org units
                org_unit_ids = list(affected_org_units)
            else:
                # Process all org units with hired candidates on this date
                org_unit_ids = list(
                    RecruitmentCandidate.objects.filter(
                        status=RecruitmentCandidate.Status.HIRED,
                        onboard_date=process_date,
                    )
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
                            _aggregate_recruitment_source_for_date(process_date, branch, block, department)
                            _aggregate_recruitment_channel_for_date(process_date, branch, block, department)
                            _aggregate_recruitment_cost_for_date(process_date, branch, block, department)
                            _aggregate_hired_candidate_for_date(process_date, branch, block, department)
                            _update_staff_growth_for_recruitment(process_date, branch, block, department)
                            total_org_units += 1

        logger.info(
            f"Batch recruitment reports aggregation complete. "
            f"Processed {len(dates_to_process)} dates, {total_org_units} org units."
        )

        return {
            "success": True,
            "dates_processed": len(dates_to_process),
            "org_units_processed": total_org_units,
        }

    except Exception as e:
        logger.exception(f"Error in batch recruitment reports aggregation: {str(e)}")
        try:
            raise self.retry(exc=e, countdown=AGGREGATION_RETRY_DELAY * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            return {"success": False, "error": str(e)}


#### Helper functions for recruitment report aggregation