"""Celery tasks for recruitment reports aggregation.

This module contains event-driven and batch tasks for aggregating recruitment reporting data.
Tasks aggregate data into RecruitmentSourceReport, RecruitmentChannelReport,
RecruitmentCostReport, and HiredCandidateReport models.
"""

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from celery import shared_task
from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone

from apps.hrm.constants import RecruitmentSourceType
from apps.hrm.models import (
    HiredCandidateReport,
    RecruitmentCandidate,
    RecruitmentChannelReport,
    RecruitmentCostReport,
    RecruitmentExpense,
    RecruitmentSourceReport,
)

logger = logging.getLogger(__name__)

# Constants
AGGREGATION_MAX_RETRIES = 3
AGGREGATION_RETRY_DELAY = 60  # 1 minute


@shared_task(bind=True, max_retries=AGGREGATION_MAX_RETRIES)
def aggregate_recruitment_reports_for_candidate(self, candidate_id: int) -> dict[str, Any]:
    """Aggregate recruitment reports for a single candidate event.

    This event-driven task is triggered when a RecruitmentCandidate record
    is created, updated (especially status change to HIRED), or deleted.
    It updates the relevant report records for the date of the candidate event.

    Args:
        self: Celery task instance
        candidate_id: ID of the RecruitmentCandidate record

    Returns:
        dict: Aggregation result with keys:
            - success: bool indicating if aggregation succeeded
            - candidate_id: int candidate ID
            - report_date: date of the report
            - error: str error message (if failed)
    """
    try:
        # Get candidate record
        try:
            candidate = RecruitmentCandidate.objects.select_related(
                "branch", "block", "department", "recruitment_source", "recruitment_channel", "referrer"
            ).get(id=candidate_id)
        except RecruitmentCandidate.DoesNotExist:
            logger.warning(f"Candidate {candidate_id} does not exist, skipping aggregation")
            return {
                "success": True,
                "candidate_id": candidate_id,
                "report_date": None,
                "message": "Candidate deleted, skipped",
            }

        # Use onboard_date if hired, otherwise submitted_date
        report_date = candidate.onboard_date if candidate.status == RecruitmentCandidate.Status.HIRED else candidate.submitted_date

        logger.info(
            f"Aggregating recruitment reports for candidate {candidate_id} "
            f"(code: {candidate.code}, status: {candidate.status}, date: {report_date})"
        )

        # Aggregate reports for this date and organizational units
        with transaction.atomic():
            if candidate.status == RecruitmentCandidate.Status.HIRED and candidate.onboard_date:
                # Only aggregate for hired candidates
                _aggregate_recruitment_source_for_date(
                    report_date, candidate.branch, candidate.block, candidate.department
                )
                _aggregate_recruitment_channel_for_date(
                    report_date, candidate.branch, candidate.block, candidate.department
                )
                _aggregate_recruitment_cost_for_date(
                    report_date, candidate.branch, candidate.block, candidate.department
                )
                _aggregate_hired_candidate_for_date(
                    report_date, candidate.branch, candidate.block, candidate.department
                )

        logger.info(f"Successfully aggregated recruitment reports for candidate {candidate_id}")
        return {
            "success": True,
            "candidate_id": candidate_id,
            "report_date": str(report_date),
            "error": None,
        }

    except Exception as e:
        logger.exception(f"Error aggregating recruitment reports for candidate {candidate_id}: {str(e)}")
        # Retry on failure
        try:
            raise self.retry(exc=e, countdown=AGGREGATION_RETRY_DELAY * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            return {
                "success": False,
                "candidate_id": candidate_id,
                "report_date": None,
                "error": str(e),
            }


@shared_task(bind=True, max_retries=AGGREGATION_MAX_RETRIES)
def aggregate_recruitment_reports_batch(self, target_date: str | None = None) -> dict[str, Any]:
    """Batch aggregation of recruitment reports for a specific date.

    This scheduled task runs at midnight to aggregate all recruitment reporting data
    for the previous day. It ensures data consistency and catches any missed
    or failed event-driven aggregations.

    Args:
        self: Celery task instance
        target_date: Date to aggregate (ISO format YYYY-MM-DD). Defaults to yesterday.

    Returns:
        dict: Aggregation result with keys:
            - success: bool indicating if aggregation succeeded
            - target_date: date that was aggregated
            - org_units_processed: int number of organizational units processed
            - error: str error message (if failed)
    """
    try:
        # Parse target date or default to yesterday
        if target_date:
            report_date = datetime.fromisoformat(target_date).date()
        else:
            report_date = (timezone.now() - timedelta(days=1)).date()

        logger.info(f"Starting batch recruitment reports aggregation for {report_date}")

        # Get all unique organizational unit combinations that have hired candidates on this date
        org_units = (
            RecruitmentCandidate.objects.filter(
                status=RecruitmentCandidate.Status.HIRED,
                onboard_date=report_date,
            )
            .values("branch", "block", "department")
            .distinct()
        )

        org_units_count = 0
        with transaction.atomic():
            for org_unit in org_units:
                branch_id = org_unit["branch"]
                block_id = org_unit["block"]
                department_id = org_unit["department"]

                if branch_id and block_id and department_id:
                    from apps.hrm.models import Branch, Block, Department

                    branch = Branch.objects.get(id=branch_id)
                    block = Block.objects.get(id=block_id)
                    department = Department.objects.get(id=department_id)

                    _aggregate_recruitment_source_for_date(report_date, branch, block, department)
                    _aggregate_recruitment_channel_for_date(report_date, branch, block, department)
                    _aggregate_recruitment_cost_for_date(report_date, branch, block, department)
                    _aggregate_hired_candidate_for_date(report_date, branch, block, department)
                    org_units_count += 1

        logger.info(
            f"Successfully completed batch recruitment reports aggregation for {report_date}. "
            f"Processed {org_units_count} organizational units."
        )

        return {
            "success": True,
            "target_date": str(report_date),
            "org_units_processed": org_units_count,
            "error": None,
        }

    except Exception as e:
        logger.exception(f"Error in batch recruitment reports aggregation: {str(e)}")
        # Retry on failure
        try:
            raise self.retry(exc=e, countdown=AGGREGATION_RETRY_DELAY * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            return {
                "success": False,
                "target_date": target_date or "yesterday",
                "org_units_processed": 0,
                "error": str(e),
            }


#### Helper functions for recruitment report aggregation


def _aggregate_recruitment_source_for_date(report_date: date, branch, block, department) -> None:
    """Aggregate recruitment source report for a specific date and organizational unit.

    Args:
        report_date: Date to aggregate
        branch: Branch instance
        block: Block instance
        department: Department instance
    """
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
        from apps.hrm.models import RecruitmentSource

        source = RecruitmentSource.objects.get(id=item["recruitment_source"])
        RecruitmentSourceReport.objects.update_or_create(
            report_date=report_date,
            branch=branch,
            block=block,
            department=department,
            recruitment_source=source,
            defaults={
                "num_hires": item["num_hires"],
            },
        )

    logger.debug(
        f"Aggregated recruitment source for {report_date} - "
        f"{branch.name}/{block.name}/{department.name}: {len(hired_by_source)} sources"
    )


def _aggregate_recruitment_channel_for_date(report_date: date, branch, block, department) -> None:
    """Aggregate recruitment channel report for a specific date and organizational unit.

    Args:
        report_date: Date to aggregate
        branch: Branch instance
        block: Block instance
        department: Department instance
    """
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
        from apps.hrm.models import RecruitmentChannel

        channel = RecruitmentChannel.objects.get(id=item["recruitment_channel"])
        RecruitmentChannelReport.objects.update_or_create(
            report_date=report_date,
            branch=branch,
            block=block,
            department=department,
            recruitment_channel=channel,
            defaults={
                "num_hires": item["num_hires"],
            },
        )

    logger.debug(
        f"Aggregated recruitment channel for {report_date} - "
        f"{branch.name}/{block.name}/{department.name}: {len(hired_by_channel)} channels"
    )


def _aggregate_recruitment_cost_for_date(report_date: date, branch, block, department) -> None:
    """Aggregate recruitment cost report for a specific date and organizational unit.

    Args:
        report_date: Date to aggregate
        branch: Branch instance
        block: Block instance
        department: Department instance
    """
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
    """Aggregate hired candidate report for a specific date and organizational unit.

    Args:
        report_date: Date to aggregate
        branch: Branch instance
        block: Block instance
        department: Department instance
    """
    month_key = report_date.strftime("%m/%Y")
    # Week key format: "Week W - MM/YYYY"
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
            employee=stats["employee"],  # Only set for referral_source
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

    # Check if returning employee (would need additional logic/field)
    # For now, default to recruitment department source
    return RecruitmentSourceType.RECRUITMENT_DEPARTMENT_SOURCE
