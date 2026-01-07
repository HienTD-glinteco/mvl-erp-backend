"""Signal handlers for recruitment reports aggregation."""

from decimal import Decimal

from django.db.models import Q, Sum
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.hrm.constants import RecruitmentSourceType
from apps.hrm.models import (
    EmployeeWorkHistory,
    HiredCandidateReport,
    RecruitmentCandidate,
    RecruitmentChannelReport,
    RecruitmentCostReport,
    RecruitmentExpense,
    RecruitmentSourceReport,
)
from apps.hrm.tasks import (
    aggregate_recruitment_reports_for_candidate,
    aggregate_recruitment_reports_for_work_history,
)


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


def _build_source_type_filter(source_type: str) -> Q:
    """Build a Q filter for expenses matching a specific source_type.

    Args:
        source_type: RecruitmentSourceType value

    Returns:
        Q: Django Q object to filter expenses by source type
    """
    if source_type == RecruitmentSourceType.REFERRAL_SOURCE:
        return Q(recruitment_source__allow_referral=True)
    elif source_type == RecruitmentSourceType.MARKETING_CHANNEL:
        return Q(recruitment_source__allow_referral=False, recruitment_channel__belong_to="marketing")
    elif source_type == RecruitmentSourceType.JOB_WEBSITE_CHANNEL:
        return Q(recruitment_source__allow_referral=False, recruitment_channel__belong_to="job_website")
    else:
        # RECRUITMENT_DEPARTMENT_SOURCE: not referral, not marketing, not job_website
        return Q(recruitment_source__allow_referral=False) & ~Q(
            recruitment_channel__belong_to__in=["marketing", "job_website"]
        )


@receiver(pre_save, sender=RecruitmentExpense)
def track_expense_changes(sender, instance, **kwargs):  # noqa: ARG001
    """Track RecruitmentExpense changes before save.

    Store the old state in a temporary attribute so we can update
    the old date's report in the post_save signal.
    """
    if instance.pk:
        try:
            old_instance = RecruitmentExpense.objects.select_related(
                "recruitment_source", "recruitment_channel", "recruitment_request"
            ).get(pk=instance.pk)
            instance._old_expense_snapshot = {
                "date": old_instance.date,
                "recruitment_source": old_instance.recruitment_source,
                "recruitment_channel": old_instance.recruitment_channel,
                "recruitment_request": old_instance.recruitment_request,
            }
        except RecruitmentExpense.DoesNotExist:
            instance._old_expense_snapshot = None
    else:
        instance._old_expense_snapshot = None


@receiver(post_save, sender=RecruitmentExpense)
def update_cost_report_on_expense_save(sender, instance, **kwargs):  # noqa: ARG001
    """Update RecruitmentCostReport when RecruitmentExpense is saved.

    Creates or updates the cost report to reflect the expense data,
    even when there are no hired candidates.

    When the expense date, source, or channel changes, also updates
    the old date's report to remove this expense from its aggregation.
    """
    # Get org fields from recruitment_request
    request = instance.recruitment_request
    if not request:
        return

    branch_id = request.branch_id
    block_id = request.block_id
    department_id = request.department_id

    # Check if we need to update old date's report
    old_snapshot = getattr(instance, "_old_expense_snapshot", None)
    if old_snapshot:
        old_date = old_snapshot["date"]
        old_request = old_snapshot["recruitment_request"]

        # Create a temporary object to determine old source_type
        class OldExpenseProxy:
            def __init__(self, snapshot):
                self.recruitment_source = snapshot["recruitment_source"]
                self.recruitment_channel = snapshot["recruitment_channel"]

        old_source_type = _determine_source_type_from_expense(OldExpenseProxy(old_snapshot))
        new_source_type = _determine_source_type_from_expense(instance)

        # Check if date or source_type changed
        if old_date != instance.date or old_source_type != new_source_type:
            # Update the old date's report
            if old_request:
                _recalculate_cost_report(
                    report_date=old_date,
                    branch_id=old_request.branch_id,
                    block_id=old_request.block_id,
                    department_id=old_request.department_id,
                    source_type=old_source_type,
                )

    # Update the current (new) date's report
    report_date = instance.date
    source_type = _determine_source_type_from_expense(instance)
    _recalculate_cost_report(
        report_date=report_date,
        branch_id=branch_id,
        block_id=block_id,
        department_id=department_id,
        source_type=source_type,
    )


def _recalculate_cost_report(report_date, branch_id, block_id, department_id, source_type):  # noqa: ANN001, ANN201
    """Recalculate and update/create a RecruitmentCostReport for given parameters.

    If no expenses exist for the given combination, deletes the report.
    """
    month_key = report_date.strftime("%Y-%m")

    # Aggregate all expenses for this date, org unit, and source type
    source_type_filter = _build_source_type_filter(source_type)
    expense_agg = RecruitmentExpense.objects.filter(
        source_type_filter,
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

    if total_cost == Decimal("0") and total_hires == 0:
        # No expenses, delete the report if it exists
        RecruitmentCostReport.objects.filter(
            report_date=report_date,
            branch_id=branch_id,
            block_id=block_id,
            department_id=department_id,
            source_type=source_type,
        ).delete()
    else:
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

    # Use helper to recalculate report (will delete if no expenses remain)
    _recalculate_cost_report(
        report_date=report_date,
        branch_id=request.branch_id,
        block_id=request.block_id,
        department_id=request.department_id,
        source_type=source_type,
    )


@receiver(post_save, sender=EmployeeWorkHistory)
def trigger_recruitment_reports_on_work_history_save(sender, instance, created, **kwargs):  # noqa: ARG001
    """Trigger recruitment reports when an employee returns to work."""
    if instance.name == EmployeeWorkHistory.EventType.RETURN_TO_WORK:
        # Create snapshot for the task
        snapshot = {
            "previous": None,  # For returning employee, we mostly care about the return event itself
            "current": {
                "date": instance.date,
                "branch_id": instance.branch_id,
                "block_id": instance.block_id,
                "department_id": instance.department_id,
                "employee_id": instance.employee_id,
            },
        }

        # Mark reports for refresh
        _mark_recruitment_reports_for_refresh(
            report_date=instance.date,
            branch_id=instance.branch_id,
            block_id=instance.block_id,
            department_id=instance.department_id,
        )

        if created:
            aggregate_recruitment_reports_for_work_history.delay("create", snapshot)
        else:
            # For simplicity, we just trigger a refresh if the event is updated
            # Though RETURN_TO_WORK usually isn't updated much
            aggregate_recruitment_reports_for_work_history.delay("update", snapshot)


@receiver(post_delete, sender=EmployeeWorkHistory)
def trigger_recruitment_reports_on_work_history_delete(sender, instance, **kwargs):  # noqa: ARG001
    """Decrement recruitment reports when a return to work event is deleted."""
    if instance.name == EmployeeWorkHistory.EventType.RETURN_TO_WORK:
        snapshot = {
            "previous": {
                "date": instance.date,
                "branch_id": instance.branch_id,
                "block_id": instance.block_id,
                "department_id": instance.department_id,
                "employee_id": instance.employee_id,
            },
            "current": None,
        }

        # Mark reports for refresh
        _mark_recruitment_reports_for_refresh(
            report_date=instance.date,
            branch_id=instance.branch_id,
            block_id=instance.block_id,
            department_id=instance.department_id,
        )

        aggregate_recruitment_reports_for_work_history.delay("delete", snapshot)
