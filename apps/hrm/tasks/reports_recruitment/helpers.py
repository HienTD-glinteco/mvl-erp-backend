"""Helper functions for recruitment reports aggregation.

This module contains all helper functions used by both event-driven and batch tasks.
"""

import logging
from datetime import date
from decimal import Decimal
from typing import Any, cast

from django.db.models import Count, F, Sum

from apps.hrm.constants import RecruitmentSourceType
from apps.hrm.models import (
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
        if isinstance(current, dict) and current.get("status") == RecruitmentCandidate.Status.HIRED:
            _process_recruitment_change(cast(dict[str, Any], current), delta=1)

    elif event_type == "update":
        # Check if hired status changed
        prev_hired = isinstance(previous, dict) and previous.get("status") == RecruitmentCandidate.Status.HIRED
        curr_hired = isinstance(current, dict) and current.get("status") == RecruitmentCandidate.Status.HIRED

        if prev_hired and not curr_hired:
            # Was hired, now not - decrement
            _process_recruitment_change(cast(dict[str, Any], previous), delta=-1)
        elif not prev_hired and curr_hired:
            # Was not hired, now is - increment
            _process_recruitment_change(cast(dict[str, Any], current), delta=1)
        elif prev_hired and curr_hired:
            # Status still hired but other fields changed - revert and apply
            _process_recruitment_change(cast(dict[str, Any], previous), delta=-1)
            _process_recruitment_change(cast(dict[str, Any], current), delta=1)

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
    _increment_source_report(onboard_date, branch_id, block_id, department_id, recruitment_source_id, delta)

    # Update recruitment channel report
    _increment_channel_report(onboard_date, branch_id, block_id, department_id, recruitment_channel_id, delta)

    # Update hired candidate report and determine source type
    source_type = _determine_source_type_from_snapshot(data)
    # years_of_experience is an integer field

    years_of_experience = data.get("years_of_experience", 0)
    # Ensure integer type (in case it comes as string from snapshot)
    if isinstance(years_of_experience, str):
        years_of_experience = int(years_of_experience) if years_of_experience.isdigit() else 0
    is_experienced = years_of_experience > 0  # 0 means no experience
    referrer_id = data.get("referrer_id")

    _increment_hired_candidate_report(
        onboard_date, branch_id, block_id, department_id, source_type, is_experienced, referrer_id, delta
    )

    # Update staff growth report (num_recruitment_source)
    _increment_staff_growth_recruitment(onboard_date, branch_id, block_id, department_id, delta)


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
    source_has_allow_referral: bool = False,
) -> None:
    """
    Increment/decrement staff growth counters for recruitment.

    Business logic (as clarified):
    - num_introductions: Hired candidates from referral sources (allow_referrer=True)
    - num_recruitment_source: Hired candidates from non-referral sources (allow_referrer=False)

    The allow_referrer field on RecruitmentSource distinguishes:
    - allow_referrer=True: Referral sources
    - allow_referrer=False: Recruitment department sources

    Args:
        report_date: Report date
        branch_id, block_id, department_id: Org unit IDs
        delta: +1 for create, -1 for delete
        source_has_allow_referral: True if candidate's source has allow_referral=True
    """
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
            # These fields should NOT be initialized to 0 - set by other tasks
        },
    )

    # Update counters based on source type
    if source_has_allow_referral:
        # Referral source
        report.num_introductions = F("num_introductions") + delta
    else:
        # Recruitment department source
        report.num_recruitment_source = F("num_recruitment_source") + delta

    report.save(update_fields=["num_introductions", "num_recruitment_source"])


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


def _fetch_expenses_by_request(request_ids: set[int], report_date: date) -> dict[int, Decimal]:
    """Fetch total expenses per recruitment_request in bulk and return mapping.

    Returns a dict mapping recruitment_request_id -> Decimal(total_amount).
    """
    expenses_by_request: dict[int, Decimal] = {}
    if not request_ids:
        return expenses_by_request

    expenses = (
        RecruitmentExpense.objects.filter(
            recruitment_request_id__in=request_ids,
            date__lte=report_date,
        )
        .values("recruitment_request_id")
        .annotate(total=Sum("amount"))
    )

    for expense in expenses:
        total = expense.get("total")
        if total is None:
            continue
        expenses_by_request[int(expense["recruitment_request_id"])] = Decimal(str(total))

    return expenses_by_request


def _count_hired_per_request(hired_candidates) -> dict[int, int]:
    """Count how many hired candidates belong to each recruitment_request."""
    hired_per_request: dict[int, int] = {}
    for candidate in hired_candidates:
        rid = candidate.recruitment_request_id
        if rid:
            hired_per_request[rid] = hired_per_request.get(rid, 0) + 1
    return hired_per_request


def _accumulate_source_type_stats(
    hired_candidates, expenses_by_request: dict[int, Decimal], hired_per_request: dict[int, int]
) -> dict[str, dict[str, Any]]:
    """Accumulate stats per source type: num_hires and total_cost."""
    source_type_stats: dict[str, dict[str, Any]] = {}
    for candidate in hired_candidates:
        source_type = _determine_source_type(candidate)
        if source_type not in source_type_stats:
            source_type_stats[source_type] = {"num_hires": 0, "total_cost": Decimal("0")}

        stats = source_type_stats[source_type]
        stats["num_hires"] = int(stats.get("num_hires", 0)) + 1

        # Only certain source types have associated expenses
        if source_type in (
            RecruitmentSourceType.MARKETING_CHANNEL,
            RecruitmentSourceType.JOB_WEBSITE_CHANNEL,
            RecruitmentSourceType.REFERRAL_SOURCE,
        ):
            request_id = candidate.recruitment_request_id
            if request_id and request_id in expenses_by_request:
                total_expense = expenses_by_request[request_id]
                num_hired = hired_per_request.get(request_id, 1)
                if total_expense and num_hired > 0:
                    cost_per_hire = total_expense / Decimal(num_hired)
                    stats["total_cost"] += cost_per_hire

    return source_type_stats


def _aggregate_recruitment_cost_for_date(report_date: date, branch, block, department) -> None:
    """Full re-aggregation of recruitment cost report for batch processing.

    This function was refactored to delegate responsibilities to small helpers
    so its cyclomatic complexity stays low for linters.
    """
    month_key = report_date.strftime("%Y-%m")

    # Fetch hired candidates and helper structures
    hired_candidates = RecruitmentCandidate.objects.filter(
        status=RecruitmentCandidate.Status.HIRED,
        onboard_date=report_date,
        branch=branch,
        block=block,
        department=department,
    ).select_related("recruitment_source", "recruitment_channel", "recruitment_request")

    request_ids = {c.recruitment_request_id for c in hired_candidates if c.recruitment_request_id}

    expenses_by_request = _fetch_expenses_by_request(request_ids, report_date)
    hired_per_request = _count_hired_per_request(hired_candidates)
    source_type_stats = _accumulate_source_type_stats(hired_candidates, expenses_by_request, hired_per_request)

    # Persist reports
    for source_type, stats in source_type_stats.items():
        avg_cost = stats["total_cost"] / Decimal(stats["num_hires"]) if stats["num_hires"] > 0 else Decimal("0")

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
    source_type_stats: dict[str, dict[str, Any]] = {}

    for candidate in hired_candidates:
        source_type = _determine_source_type(candidate)

        if source_type not in source_type_stats:
            source_type_stats[source_type] = {
                "num_candidates_hired": 0,
                "num_experienced": 0,
                "employee": None,
            }

        stats = source_type_stats[source_type]
        # Ensure numeric fields are initialized and typed before arithmetic
        stats["num_candidates_hired"] = int(stats.get("num_candidates_hired", 0)) + 1

        # Check if experienced (not NO_EXPERIENCE)
        if candidate.years_of_experience != RecruitmentCandidate.YearsOfExperience.NO_EXPERIENCE:
            stats["num_experienced"] = int(stats.get("num_experienced", 0)) + 1

        # For referral sources, track the referrer (Employee instance)
        if source_type == RecruitmentSourceType.REFERRAL_SOURCE and candidate.referrer:
            stats["employee"] = candidate.referrer

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
    - num_introductions: COUNT of HIRED candidates with source.allow_referrer=True (Referral source)
    - num_recruitment_source: COUNT of HIRED candidates with source.allow_referrer=False (Department source)

    Business Rules:
    - allow_referrer=True: Identifies referral sources
    - allow_referrer=False: Identifies department sources
    - num_introductions: ALL hired candidates from referral sources
    - num_recruitment_source: ALL hired candidates from department sources

    Example:
    - 10 candidates hired via referral source (allow_referrer=True) → num_introductions
    - 7 candidates hired via department source (allow_referrer=False) → num_recruitment_source
    - Both counts are independent and don't overlap

    Args:
        report_date: Date to aggregate
        branch, block, department: Org unit objects
    """
    # Identify referral sources using allow_referrer field

    # Fetch referral source IDs directly
    referral_source_ids = list(RecruitmentSource.objects.filter(allow_referral=True).values_list("id", flat=True))

    if not referral_source_ids:
        logger.warning("No recruitment sources with allow_referrer=True found")
        return

    # num_introductions: All hired candidates from referral sources (allow_referrer=True)
    num_introductions = RecruitmentCandidate.objects.filter(
        status=RecruitmentCandidate.Status.HIRED,
        onboard_date=report_date,
        branch=branch,
        block=block,
        department=department,
        recruitment_source__allow_referral=True,  # Referral sources
    ).count()

    # num_recruitment_source: Hired candidates with department sources (allow_referrer=False)
    # According to comment: allow_referrer=False means department sources
    num_recruitment_source = RecruitmentCandidate.objects.filter(
        status=RecruitmentCandidate.Status.HIRED,
        onboard_date=report_date,
        branch=branch,
        block=block,
        department=department,
        recruitment_source__allow_referral=False,  # Department sources
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
