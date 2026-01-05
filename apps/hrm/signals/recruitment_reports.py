"""Signal handlers for recruitment reports aggregation."""

from decimal import Decimal

from django.db.models import Sum
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.hrm.constants import RecruitmentSourceType
from apps.hrm.models import (
    HiredCandidateReport,
    RecruitmentCandidate,
    RecruitmentChannelReport,
    RecruitmentCostReport,
    RecruitmentExpense,
    RecruitmentSourceReport,
)
from apps.hrm.tasks import aggregate_recruitment_reports_for_candidate


@receiver(pre_save, sender=RecruitmentCandidate)
def track_candidate_changes(sender, instance, **kwargs):  # noqa: ARG001
    """Track recruitment candidate changes before save.

    Store the old state in a temporary attribute so we can create a snapshot
    in the post_save signal.
    """
    if instance.pk:
        try:
            old_instance = RecruitmentCandidate.objects.select_related(
                "recruitment_source", "recruitment_channel", "referrer"
            ).get(pk=instance.pk)
            instance._old_snapshot = {
                "status": old_instance.status,
                "onboard_date": old_instance.onboard_date,
                "branch_id": old_instance.branch_id,
                "block_id": old_instance.block_id,
                "department_id": old_instance.department_id,
                "recruitment_source_id": old_instance.recruitment_source_id,
                "recruitment_channel_id": old_instance.recruitment_channel_id,
                "source_allow_referral": old_instance.recruitment_source.allow_referral,
                "channel_belong_to": old_instance.recruitment_channel.belong_to,
                "years_of_experience": old_instance.years_of_experience,
                "referrer_id": old_instance.referrer_id,
            }
        except RecruitmentCandidate.DoesNotExist:
            instance._old_snapshot = None
    else:
        instance._old_snapshot = None


@receiver(post_save, sender=RecruitmentCandidate)
def trigger_recruitment_reports_aggregation_on_save(sender, instance, created, **kwargs):  # noqa: ARG001
    """Trigger recruitment reports aggregation when candidate is created or updated.

    This signal:
    1. Fires a Celery task to incrementally update recruitment reports using snapshot data
    2. Marks affected report records with need_refresh=True for batch reconciliation
    """
    # Only trigger if the candidate has required organizational fields
    if instance.branch_id and instance.block_id and instance.department_id:
        # Get related data for snapshot
        recruitment_source = instance.recruitment_source
        recruitment_channel = instance.recruitment_channel

        # Create current snapshot
        current_snapshot = {
            "status": instance.status,
            "onboard_date": instance.onboard_date,
            "branch_id": instance.branch_id,
            "block_id": instance.block_id,
            "department_id": instance.department_id,
            "recruitment_source_id": instance.recruitment_source_id,
            "recruitment_channel_id": instance.recruitment_channel_id,
            "source_allow_referral": recruitment_source.allow_referral if recruitment_source else False,
            "channel_belong_to": recruitment_channel.belong_to if recruitment_channel else None,
            "years_of_experience": instance.years_of_experience,
            "referrer_id": instance.referrer_id,
        }

        # Mark affected reports for batch refresh (uses onboard_date if available)
        report_date = instance.onboard_date if instance.onboard_date else None
        if report_date:
            _mark_recruitment_reports_for_refresh(
                report_date=report_date,
                branch_id=instance.branch_id,
                block_id=instance.block_id,
                department_id=instance.department_id,
            )

        if created:
            # Create event: previous is None, current is new state
            snapshot = {"previous": None, "current": current_snapshot}
            aggregate_recruitment_reports_for_candidate.delay("create", snapshot)
        else:
            # Update event: previous is old state, current is new state
            previous_snapshot = getattr(instance, "_old_snapshot", None)
            snapshot = {"previous": previous_snapshot, "current": current_snapshot}
            aggregate_recruitment_reports_for_candidate.delay("update", snapshot)


@receiver(post_delete, sender=RecruitmentCandidate)
def trigger_recruitment_reports_aggregation_on_delete(sender, instance, **kwargs):  # noqa: ARG001
    """Trigger recruitment reports aggregation when candidate is deleted.

    This signal:
    1. Fires a Celery task to decrementally update recruitment reports using snapshot data
    2. Marks affected report records with need_refresh=True for batch reconciliation
    """
    # Trigger incremental update for deletion
    if instance.branch_id and instance.block_id and instance.department_id:
        # Get related data for snapshot
        recruitment_source = instance.recruitment_source
        recruitment_channel = instance.recruitment_channel

        # Mark affected reports for batch refresh (uses onboard_date if available)
        report_date = instance.onboard_date if instance.onboard_date else None
        if report_date:
            _mark_recruitment_reports_for_refresh(
                report_date=report_date,
                branch_id=instance.branch_id,
                block_id=instance.block_id,
                department_id=instance.department_id,
            )

        # Delete event: previous is deleted state, current is None
        previous_snapshot = {
            "status": instance.status,
            "onboard_date": instance.onboard_date,
            "branch_id": instance.branch_id,
            "block_id": instance.block_id,
            "department_id": instance.department_id,
            "recruitment_source_id": instance.recruitment_source_id,
            "recruitment_channel_id": instance.recruitment_channel_id,
            "source_allow_referral": recruitment_source.allow_referral if recruitment_source else False,
            "channel_belong_to": recruitment_channel.belong_to if recruitment_channel else None,
            "years_of_experience": instance.years_of_experience,
            "referrer_id": instance.referrer_id,
        }
        snapshot = {"previous": previous_snapshot, "current": None}
        aggregate_recruitment_reports_for_candidate.delay("delete", snapshot)


def _mark_recruitment_reports_for_refresh(report_date, branch_id, block_id, department_id):  # noqa: ANN001, ANN201
    """Mark affected recruitment report records with need_refresh=True.

    Only marks the specific report record matching the exact date and org unit,
    avoiding bulk updates of large date ranges.

    Args:
        report_date: The report date to mark
        branch_id: Branch ID
        block_id: Block ID (can be None)
        department_id: Department ID (can be None)
    """
    # Build filter criteria for exact org unit match
    filter_criteria = {
        "report_date": report_date,
        "branch_id": branch_id,
    }
    if block_id:
        filter_criteria["block_id"] = block_id
    if department_id:
        filter_criteria["department_id"] = department_id

    # Mark RecruitmentSourceReport records
    RecruitmentSourceReport.objects.filter(**filter_criteria).update(need_refresh=True)

    # Mark RecruitmentChannelReport records
    RecruitmentChannelReport.objects.filter(**filter_criteria).update(need_refresh=True)

    # Mark RecruitmentCostReport records
    RecruitmentCostReport.objects.filter(**filter_criteria).update(need_refresh=True)

    # Mark HiredCandidateReport records
    HiredCandidateReport.objects.filter(**filter_criteria).update(need_refresh=True)


def _determine_source_type_from_expense(expense: RecruitmentExpense) -> str:
    """Determine recruitment source type from expense data.

    Args:
        expense: RecruitmentExpense instance

    Returns:
        str: Source type from RecruitmentSourceType choices
    """
    # Check if referral source
    if expense.recruitment_source and expense.recruitment_source.allow_referral:
        return RecruitmentSourceType.REFERRAL_SOURCE

    # Check channel type
    if expense.recruitment_channel:
        if expense.recruitment_channel.belong_to == "marketing":
            return RecruitmentSourceType.MARKETING_CHANNEL
        elif expense.recruitment_channel.belong_to == "job_website":
            return RecruitmentSourceType.JOB_WEBSITE_CHANNEL

    # Default to recruitment department source
    return RecruitmentSourceType.RECRUITMENT_DEPARTMENT_SOURCE


@receiver(post_save, sender=RecruitmentExpense)
def update_cost_report_on_expense_save(sender, instance, **kwargs):  # noqa: ARG001
    """Update RecruitmentCostReport when RecruitmentExpense is saved.

    Creates or updates the cost report to reflect the expense data,
    even when there are no hired candidates.
    """
    report_date = instance.date
    source_type = _determine_source_type_from_expense(instance)

    # Get org fields from recruitment_request
    request = instance.recruitment_request
    if not request:
        return

    branch_id = request.branch_id
    block_id = request.block_id
    department_id = request.department_id

    month_key = report_date.strftime("%Y-%m")

    # Aggregate all expenses for this date, org unit, and source type
    expense_agg = RecruitmentExpense.objects.filter(
        date=report_date,
        recruitment_request__branch_id=branch_id,
        recruitment_request__block_id=block_id,
        recruitment_request__department_id=department_id,
    ).aggregate(
        total_cost=Sum("total_cost"),
        total_hires=Sum("num_candidates_hired"),
    )

    total_cost = expense_agg.get("total_cost") or Decimal("0")
    total_hires = expense_agg.get("total_hires") or 0

    # Calculate average cost per hire
    avg_cost = total_cost / total_hires if total_hires > 0 else Decimal("0")

    # Update or create the report record
    RecruitmentCostReport.objects.update_or_create(
        report_date=report_date,
        branch_id=branch_id,
        block_id=block_id,
        department_id=department_id,
        source_type=source_type,
        defaults={
            "month_key": month_key,
            "total_cost": total_cost,
            "num_hires": total_hires,
            "avg_cost_per_hire": avg_cost,
        },
    )


@receiver(post_delete, sender=RecruitmentExpense)
def update_cost_report_on_expense_delete(sender, instance, **kwargs):  # noqa: ARG001
    """Update RecruitmentCostReport when RecruitmentExpense is deleted.

    Re-aggregates the cost report after expense deletion.
    If no expenses remain, deletes the report record.
    """
    report_date = instance.date
    source_type = _determine_source_type_from_expense(instance)

    # Get org fields from recruitment_request
    request = instance.recruitment_request
    if not request:
        return

    branch_id = request.branch_id
    block_id = request.block_id
    department_id = request.department_id

    # Check if any expenses remain for this combination
    remaining_expenses = RecruitmentExpense.objects.filter(
        date=report_date,
        recruitment_request__branch_id=branch_id,
        recruitment_request__block_id=block_id,
        recruitment_request__department_id=department_id,
    ).exclude(pk=instance.pk)

    if not remaining_expenses.exists():
        # No expenses remain, delete the report record
        RecruitmentCostReport.objects.filter(
            report_date=report_date,
            branch_id=branch_id,
            block_id=block_id,
            department_id=department_id,
            source_type=source_type,
        ).delete()
    else:
        # Re-aggregate remaining expenses
        expense_agg = remaining_expenses.aggregate(
            total_cost=Sum("total_cost"),
            total_hires=Sum("num_candidates_hired"),
        )

        total_cost = expense_agg.get("total_cost") or Decimal("0")
        total_hires = expense_agg.get("total_hires") or 0
        avg_cost = total_cost / total_hires if total_hires > 0 else Decimal("0")

        month_key = report_date.strftime("%Y-%m")

        RecruitmentCostReport.objects.update_or_create(
            report_date=report_date,
            branch_id=branch_id,
            block_id=block_id,
            department_id=department_id,
            source_type=source_type,
            defaults={
                "month_key": month_key,
                "total_cost": total_cost,
                "num_hires": total_hires,
                "avg_cost_per_hire": avg_cost,
            },
        )
