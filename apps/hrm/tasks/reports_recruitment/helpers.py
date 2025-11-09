"""Helper functions for recruitment reports aggregation.

This module contains all helper functions used by both event-driven and batch tasks.
"""

import logging
from datetime import date
from decimal import Decimal
from typing import Any

from django.db.models import Count, F, Q, Sum
from django.db import models

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

    # Collect all source IDs and fetch in bulk
    source_ids = [item["recruitment_source"] for item in hired_by_source if item["recruitment_source"]]
    sources = {s.id: s for s in RecruitmentSource.objects.filter(id__in=source_ids)}

    # Update or create report for each source
    for item in hired_by_source:
        source = sources.get(item["recruitment_source"])
        if source:
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

    # Collect all channel IDs and fetch in bulk
    channel_ids = [item["recruitment_channel"] for item in hired_by_channel if item["recruitment_channel"]]
    channels = {c.id: c for c in RecruitmentChannel.objects.filter(id__in=channel_ids)}

    # Update or create report for each channel
    for item in hired_by_channel:
        channel = channels.get(item["recruitment_channel"])
        if channel:
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
    ).select_related("recruitment_source", "recruitment_channel", "recruitment_request")

    # Collect all recruitment request IDs for bulk expense fetching
    request_ids = set()
    for candidate in hired_candidates:
        if candidate.recruitment_request_id:
            request_ids.add(candidate.recruitment_request_id)

    # Fetch all expenses in bulk
    expenses_by_request = {}
    if request_ids:
        expenses = RecruitmentExpense.objects.filter(
            recruitment_request_id__in=request_ids,
            expense_date__lte=report_date,
        ).values("recruitment_request_id").annotate(total=Sum("amount"))

        for expense in expenses:
            expenses_by_request[expense["recruitment_request_id"]] = expense["total"]

    # Count hired candidates per request for cost distribution
    hired_per_request = {}
    for candidate in hired_candidates:
        if candidate.recruitment_request_id:
            hired_per_request[candidate.recruitment_request_id] = (
                hired_per_request.get(candidate.recruitment_request_id, 0) + 1
            )

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
            # Get pre-fetched expense total
            request_id = candidate.recruitment_request_id
            if request_id and request_id in expenses_by_request:
                total_expense = expenses_by_request[request_id]
                num_hired = hired_per_request.get(request_id, 1)

                if total_expense and num_hired > 0:
                    cost_per_hire = Decimal(str(total_expense)) / num_hired
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
    """Update StaffGrowthReport num_introductions and num_recruitment_source for hired candidates.
    
    Calculation Formula (per business requirements):
    - num_introductions: COUNT of HIRED candidates with source = "Giới thiệu" (Referral)
    - num_recruitment_source: COUNT of HIRED candidates from recruitment dept with source = "Giới thiệu"
    
    Both metrics track referral-based hires:
    - num_introductions: All referral hires regardless of department
    - num_recruitment_source: Referral hires specifically from recruitment department
    
    Example:
    - If 5 candidates hired via referral, num_introductions = 5
    - If 3 of those came from recruitment dept, num_recruitment_source = 3
    
    Args:
        report_date: Date to aggregate
        branch, block, department: Org unit objects
    """
    # Count all hired candidates with "Giới thiệu" source
    from apps.hrm.models import RecruitmentSource
    
    try:
        referral_source = RecruitmentSource.objects.get(name="Giới thiệu")
    except RecruitmentSource.DoesNotExist:
        logger.warning("Recruitment source 'Giới thiệu' not found")
        return
    
    # Total referral hires
    num_introductions = RecruitmentCandidate.objects.filter(
        status=RecruitmentCandidate.Status.HIRED,
        onboard_date=report_date,
        branch=branch,
        block=block,
        department=department,
        source=referral_source,
    ).count()
    
    # Referral hires from recruitment department specifically
    # TODO: Need to determine how to identify "recruitment department" candidates
    # For now, using same count as num_introductions
    num_recruitment_source = num_introductions

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
            "num_introductions": num_introductions,
            "num_recruitment_source": num_recruitment_source,
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
