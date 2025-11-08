"""Celery tasks for recruitment reports aggregation.

This module contains event-driven and batch tasks for aggregating recruitment reporting data.
Tasks aggregate data into RecruitmentSourceReport, RecruitmentChannelReport,
RecruitmentCostReport, HiredCandidateReport, and StaffGrowthReport (for hired candidates).
"""

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


@shared_task(bind=True, max_retries=AGGREGATION_MAX_RETRIES)
def aggregate_recruitment_reports_for_candidate(
    self, event_type: str, snapshot: dict[str, Any]
) -> dict[str, Any]:
    """Aggregate recruitment reports for a single candidate event (smart incremental update).

    This event-driven task uses snapshot data to avoid race conditions where the
    candidate record might be modified before the task processes.

    Args:
        self: Celery task instance
        event_type: Type of event - "create", "update", or "delete"
        snapshot: Dict containing previous and current state:
            - previous: Previous state (None for create, dict for update/delete)
            - current: Current state (dict for create/update, None for delete)

    Returns:
        dict: Aggregation result with success status and metadata
    """
    try:
        previous = snapshot.get("previous")
        current = snapshot.get("current")

        if not previous and not current:
            logger.warning(f"Invalid snapshot for event {event_type}")
            return {"success": False, "error": "Invalid snapshot"}

        # Extract data from current or previous state
        data = current if current else previous
        
        logger.info(
            f"Incrementally updating recruitment reports for candidate "
            f"(event: {event_type}, status: {data.get('status')})"
        )

        # Perform incremental update
        with transaction.atomic():
            _increment_recruitment_reports(event_type, snapshot)

        return {
            "success": True,
            "event_type": event_type,
        }

    except Exception as e:
        logger.exception(f"Error in incremental recruitment reports update: {str(e)}")
        try:
            raise self.retry(exc=e, countdown=AGGREGATION_RETRY_DELAY * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            return {"success": False, "error": str(e)}


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
                
                # Get all unique org units affected by these changes
                affected_org_units = set()
                for candidate in modified_today:
                    if candidate.branch_id and candidate.block_id and candidate.department_id:
                        affected_org_units.add((candidate.branch_id, candidate.block_id, candidate.department_id))
                
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


def _increment_recruitment_reports(event_type: str, snapshot: dict[str, Any]) -> None:
    """Incrementally update recruitment reports based on event snapshot.

    Only processes hired candidates. Updates StaffGrowthReport as well.

    Args:
        event_type: "create", "update", or "delete"
        snapshot: Dict with previous and current state
    """
    previous = snapshot.get("previous")
    current = snapshot.get("current")

    # Process based on event type
    if event_type == "create":
        if current and current.get("status") == RecruitmentCandidate.Status.HIRED:
            _process_recruitment_change(current, delta=1)
        
    elif event_type == "update":
        # Check if hired status changed
        prev_hired = previous and previous.get("status") == RecruitmentCandidate.Status.HIRED
        curr_hired = current and current.get("status") == RecruitmentCandidate.Status.HIRED
        
        if prev_hired and not curr_hired:
            # Was hired, now not - decrement
            _process_recruitment_change(previous, delta=-1)
        elif not prev_hired and curr_hired:
            # Was not hired, now is - increment
            _process_recruitment_change(current, delta=1)
        elif prev_hired and curr_hired:
            # Status still hired but other fields changed - revert and apply
            _process_recruitment_change(previous, delta=-1)
            _process_recruitment_change(current, delta=1)
            
    elif event_type == "delete":
        if previous and previous.get("status") == RecruitmentCandidate.Status.HIRED:
            _process_recruitment_change(previous, delta=-1)


def _process_recruitment_change(data: dict[str, Any], delta: int) -> None:
    """Process a single recruitment change (increment or decrement).

    Args:
        data: Candidate data snapshot
        delta: +1 for increment, -1 for decrement
    """
    onboard_date = data.get("onboard_date")
    if not onboard_date:
        return
    
    branch_id = data["branch_id"]
    block_id = data["block_id"]
    department_id = data["department_id"]
    recruitment_source_id = data["recruitment_source_id"]
    recruitment_channel_id = data["recruitment_channel_id"]
    
    # Update recruitment source report
    _increment_source_report(
        onboard_date, branch_id, block_id, department_id, recruitment_source_id, delta
    )
    
    # Update recruitment channel report
    _increment_channel_report(
        onboard_date, branch_id, block_id, department_id, recruitment_channel_id, delta
    )
    
    # Update hired candidate report and determine source type
    source_type = _determine_source_type_from_snapshot(data)
    is_experienced = data.get("years_of_experience") != "NO_EXPERIENCE"
    referrer_id = data.get("referrer_id")
    
    _increment_hired_candidate_report(
        onboard_date, branch_id, block_id, department_id,
        source_type, is_experienced, referrer_id, delta
    )
    
    # Update staff growth report (num_recruitment_source)
    _increment_staff_growth_recruitment(
        onboard_date, branch_id, block_id, department_id, delta
    )


def _determine_source_type_from_snapshot(data: dict[str, Any]) -> str:
    """Determine recruitment source type from candidate snapshot data.

    Args:
        data: Candidate snapshot with source/channel info

    Returns:
        str: Source type from RecruitmentSourceType choices
    """
    # Check if referral source
    if data.get("source_allow_referral"):
        return RecruitmentSourceType.REFERRAL_SOURCE

    # Check channel type
    channel_belong_to = data.get("channel_belong_to")
    if channel_belong_to == "marketing":
        return RecruitmentSourceType.MARKETING_CHANNEL
    elif channel_belong_to == "job_website":
        return RecruitmentSourceType.JOB_WEBSITE_CHANNEL

    # Default to recruitment department source
    return RecruitmentSourceType.RECRUITMENT_DEPARTMENT_SOURCE


def _increment_source_report(
    report_date: date,
    branch_id: int,
    block_id: int,
    department_id: int,
    recruitment_source_id: int,
    delta: int,
) -> None:
    """Increment/decrement recruitment source report counter."""
    report, created = RecruitmentSourceReport.objects.get_or_create(
        report_date=report_date,
        branch_id=branch_id,
        block_id=block_id,
        department_id=department_id,
        recruitment_source_id=recruitment_source_id,
        defaults={"num_hires": 0},
    )
    
    report.num_hires = F("num_hires") + delta
    report.save(update_fields=["num_hires"])


def _increment_channel_report(
    report_date: date,
    branch_id: int,
    block_id: int,
    department_id: int,
    recruitment_channel_id: int,
    delta: int,
) -> None:
    """Increment/decrement recruitment channel report counter."""
    report, created = RecruitmentChannelReport.objects.get_or_create(
        report_date=report_date,
        branch_id=branch_id,
        block_id=block_id,
        department_id=department_id,
        recruitment_channel_id=recruitment_channel_id,
        defaults={"num_hires": 0},
    )
    
    report.num_hires = F("num_hires") + delta
    report.save(update_fields=["num_hires"])


def _increment_hired_candidate_report(
    report_date: date,
    branch_id: int,
    block_id: int,
    department_id: int,
    source_type: str,
    is_experienced: bool,
    referrer_id: int | None,
    delta: int,
) -> None:
    """Increment/decrement hired candidate report counters."""
    month_key = report_date.strftime("%m/%Y")
    week_number = report_date.isocalendar()[1]
    week_key = f"Week {week_number} - {month_key}"
    
    report, created = HiredCandidateReport.objects.get_or_create(
        report_date=report_date,
        branch_id=branch_id,
        block_id=block_id,
        department_id=department_id,
        source_type=source_type,
        employee_id=referrer_id if source_type == RecruitmentSourceType.REFERRAL_SOURCE else None,
        defaults={
            "month_key": month_key,
            "week_key": week_key,
            "num_candidates_hired": 0,
            "num_experienced": 0,
        },
    )
    
    report.num_candidates_hired = F("num_candidates_hired") + delta
    if is_experienced:
        report.num_experienced = F("num_experienced") + delta
    report.save(update_fields=["num_candidates_hired", "num_experienced"])


def _increment_staff_growth_recruitment(
    report_date: date,
    branch_id: int,
    block_id: int,
    department_id: int,
    delta: int,
) -> None:
    """Increment/decrement staff growth num_recruitment_source counter."""
    month_key = report_date.strftime("%m/%Y")
    week_number = report_date.isocalendar()[1]
    week_key = f"Week {week_number} - {month_key}"
    
    report, created = StaffGrowthReport.objects.get_or_create(
        report_date=report_date,
        branch_id=branch_id,
        block_id=block_id,
        department_id=department_id,
        defaults={
            "month_key": month_key,
            "week_key": week_key,
            "num_transfers": 0,
            "num_resignations": 0,
            "num_returns": 0,
            "num_introductions": 0,
            "num_recruitment_source": 0,
        },
    )
    
    report.num_recruitment_source = F("num_recruitment_source") + delta
    report.save(update_fields=["num_recruitment_source"])


#### Batch aggregation helper functions


def _aggregate_recruitment_source_for_date(report_date: date, branch, block, department) -> None:
    """Full re-aggregation of recruitment source report for batch processing."""
    # Get all hired candidates for this date and org unit, grouped by source
    hired_by_source = (
        RecruitmentCandidate.objects.filter(
            status=RecruitmentCandidate.Status.HIRED,
            onboard_date=report_date,
            branch=branch,
            block=block,
            department=department,
        )
        .values("recruitment_source")
        .annotate(num_hires=Count("id"))
    )

    # Update or create report for each source
    for item in hired_by_source:
        source = RecruitmentSource.objects.get(id=item["recruitment_source"])
        RecruitmentSourceReport.objects.update_or_create(
            report_date=report_date,
            branch=branch,
            block=block,
            department=department,
            recruitment_source=source,
            defaults={"num_hires": item["num_hires"]},
        )

    logger.debug(
        f"Aggregated recruitment source for {report_date} - "
        f"{branch.name}/{block.name}/{department.name}: {len(hired_by_source)} sources"
    )


def _aggregate_recruitment_channel_for_date(report_date: date, branch, block, department) -> None:
    """Full re-aggregation of recruitment channel report for batch processing."""
    # Get all hired candidates for this date and org unit, grouped by channel
    hired_by_channel = (
        RecruitmentCandidate.objects.filter(
            status=RecruitmentCandidate.Status.HIRED,
            onboard_date=report_date,
            branch=branch,
            block=block,
            department=department,
        )
        .values("recruitment_channel")
        .annotate(num_hires=Count("id"))
    )

    # Update or create report for each channel
    for item in hired_by_channel:
        channel = RecruitmentChannel.objects.get(id=item["recruitment_channel"])
        RecruitmentChannelReport.objects.update_or_create(
            report_date=report_date,
            branch=branch,
            block=block,
            department=department,
            recruitment_channel=channel,
            defaults={"num_hires": item["num_hires"]},
        )

    logger.debug(
        f"Aggregated recruitment channel for {report_date} - "
        f"{branch.name}/{block.name}/{department.name}: {len(hired_by_channel)} channels"
    )


def _aggregate_recruitment_cost_for_date(report_date: date, branch, block, department) -> None:
    """Full re-aggregation of recruitment cost report for batch processing."""
    month_key = report_date.strftime("%Y-%m")

    # Categorize candidates by source type
    hired_candidates = RecruitmentCandidate.objects.filter(
        status=RecruitmentCandidate.Status.HIRED,
        onboard_date=report_date,
        branch=branch,
        block=block,
        department=department,
    ).select_related("recruitment_source", "recruitment_channel")

    # Group by source type
    source_type_stats = {}

    for candidate in hired_candidates:
        source_type = _determine_source_type(candidate)

        if source_type not in source_type_stats:
            source_type_stats[source_type] = {"num_hires": 0, "total_cost": Decimal("0")}

        source_type_stats[source_type]["num_hires"] += 1

        # Calculate cost for this candidate if applicable
        if source_type in [
            RecruitmentSourceType.MARKETING_CHANNEL,
            RecruitmentSourceType.JOB_WEBSITE_CHANNEL,
            RecruitmentSourceType.REFERRAL_SOURCE,
        ]:
            # Get expenses related to this candidate
            expenses = RecruitmentExpense.objects.filter(
                recruitment_request=candidate.recruitment_request,
                expense_date__lte=report_date,
            ).aggregate(total=Sum("amount"))

            if expenses["total"]:
                # Distribute cost among all hired candidates from this request
                num_hired_from_request = RecruitmentCandidate.objects.filter(
                    recruitment_request=candidate.recruitment_request,
                    status=RecruitmentCandidate.Status.HIRED,
                ).count()

                if num_hired_from_request > 0:
                    cost_per_hire = Decimal(str(expenses["total"])) / num_hired_from_request
                    source_type_stats[source_type]["total_cost"] += cost_per_hire

    # Update or create report for each source type
    for source_type, stats in source_type_stats.items():
        avg_cost = (
            stats["total_cost"] / stats["num_hires"]
            if stats["num_hires"] > 0
            else Decimal("0")
        )

        RecruitmentCostReport.objects.update_or_create(
            report_date=report_date,
            branch=branch,
            block=block,
            department=department,
            source_type=source_type,
            defaults={
                "month_key": month_key,
                "total_cost": stats["total_cost"],
                "num_hires": stats["num_hires"],
                "avg_cost_per_hire": avg_cost,
            },
        )

    logger.debug(
        f"Aggregated recruitment cost for {report_date} - "
        f"{branch.name}/{block.name}/{department.name}: {len(source_type_stats)} source types"
    )


def _aggregate_hired_candidate_for_date(report_date: date, branch, block, department) -> None:
    """Full re-aggregation of hired candidate report for batch processing."""
    month_key = report_date.strftime("%m/%Y")
    week_number = report_date.isocalendar()[1]
    week_key = f"Week {week_number} - {month_key}"

    # Get all hired candidates for this date and org unit
    hired_candidates = RecruitmentCandidate.objects.filter(
        status=RecruitmentCandidate.Status.HIRED,
        onboard_date=report_date,
        branch=branch,
        block=block,
        department=department,
    ).select_related("recruitment_source", "recruitment_channel", "referrer")

    # Group by source type
    source_type_stats = {}

    for candidate in hired_candidates:
        source_type = _determine_source_type(candidate)

        if source_type not in source_type_stats:
            source_type_stats[source_type] = {
                "num_candidates_hired": 0,
                "num_experienced": 0,
                "employee": None,
            }

        source_type_stats[source_type]["num_candidates_hired"] += 1

        # Check if experienced (not NO_EXPERIENCE)
        if candidate.years_of_experience != RecruitmentCandidate.YearsOfExperience.NO_EXPERIENCE:
            source_type_stats[source_type]["num_experienced"] += 1

        # For referral sources, track the referrer
        if source_type == RecruitmentSourceType.REFERRAL_SOURCE and candidate.referrer:
            source_type_stats[source_type]["employee"] = candidate.referrer

    # Update or create report for each source type
    for source_type, stats in source_type_stats.items():
        HiredCandidateReport.objects.update_or_create(
            report_date=report_date,
            branch=branch,
            block=block,
            department=department,
            source_type=source_type,
            employee=stats["employee"],
            defaults={
                "month_key": month_key,
                "week_key": week_key,
                "num_candidates_hired": stats["num_candidates_hired"],
                "num_experienced": stats["num_experienced"],
            },
        )

    logger.debug(
        f"Aggregated hired candidates for {report_date} - "
        f"{branch.name}/{block.name}/{department.name}: {len(source_type_stats)} source types"
    )


def _update_staff_growth_for_recruitment(report_date: date, branch, block, department) -> None:
    """Update StaffGrowthReport num_recruitment_source counter for hired candidates."""
    # Count hired candidates on this date for this org unit
    num_hired = RecruitmentCandidate.objects.filter(
        status=RecruitmentCandidate.Status.HIRED,
        onboard_date=report_date,
        branch=branch,
        block=block,
        department=department,
    ).count()

    month_key = report_date.strftime("%m/%Y")
    week_number = report_date.isocalendar()[1]
    week_key = f"Week {week_number} - {month_key}"

    # Update or create staff growth report
    StaffGrowthReport.objects.update_or_create(
        report_date=report_date,
        branch=branch,
        block=block,
        department=department,
        defaults={
            "month_key": month_key,
            "week_key": week_key,
            "num_recruitment_source": num_hired,
        },
    )


def _determine_source_type(candidate: RecruitmentCandidate) -> str:
    """Determine the recruitment source type for a candidate.

    Args:
        candidate: RecruitmentCandidate instance

    Returns:
        str: Source type from RecruitmentSourceType choices
    """
    # Check if referral source
    if candidate.recruitment_source.allow_referral:
        return RecruitmentSourceType.REFERRAL_SOURCE

    # Check channel type
    if candidate.recruitment_channel.belong_to == "marketing":
        return RecruitmentSourceType.MARKETING_CHANNEL
    elif candidate.recruitment_channel.belong_to == "job_website":
        return RecruitmentSourceType.JOB_WEBSITE_CHANNEL

    # Default to recruitment department source
    return RecruitmentSourceType.RECRUITMENT_DEPARTMENT_SOURCE
