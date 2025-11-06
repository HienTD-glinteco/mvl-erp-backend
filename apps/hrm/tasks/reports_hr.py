"""Celery tasks for HR reports aggregation.

This module contains event-driven and batch tasks for aggregating HR reporting data.
Tasks aggregate data into StaffGrowthReport and EmployeeStatusBreakdownReport models.
"""

import logging
from datetime import date, datetime, timedelta
from typing import Any

from celery import shared_task
from django.db import transaction
from django.db.models import Count, F, Q
from django.utils import timezone

from apps.hrm.models import (
    Block,
    Branch,
    Department,
    Employee,
    EmployeeStatusBreakdownReport,
    EmployeeWorkHistory,
    StaffGrowthReport,
)

logger = logging.getLogger(__name__)

# Constants
AGGREGATION_MAX_RETRIES = 3
AGGREGATION_RETRY_DELAY = 60  # 1 minute


@shared_task(bind=True, max_retries=AGGREGATION_MAX_RETRIES)
def aggregate_hr_reports_for_work_history(
    self, work_history_id: int, event_type: str = "create", old_values: dict | None = None
) -> dict[str, Any]:
    """Aggregate HR reports for a single work history event (smart incremental update).

    This event-driven task is triggered when an EmployeeWorkHistory record
    is created, updated, or deleted. It intelligently updates report records
    by incrementing/decrementing values based on the event type.

    Args:
        self: Celery task instance
        work_history_id: ID of the EmployeeWorkHistory record
        event_type: Type of event - "create", "update", or "delete"
        old_values: Dict with old values for update/delete events

    Returns:
        dict: Aggregation result with success status and metadata
    """
    try:
        # Get work history record (or use old_values for delete events)
        if event_type == "delete":
            if not old_values:
                logger.warning(f"Delete event for work history {work_history_id} without old_values")
                return {"success": True, "message": "Delete without old_values, skipped"}
            work_history_data = old_values
            report_date = work_history_data["date"]
            branch_id = work_history_data["branch_id"]
            block_id = work_history_data["block_id"]
            department_id = work_history_data["department_id"]
            event_name = work_history_data["name"]
            status = work_history_data.get("status")
            previous_data = work_history_data.get("previous_data", {})
        else:
            try:
                work_history = EmployeeWorkHistory.objects.select_related(
                    "employee", "branch", "block", "department"
                ).get(id=work_history_id)
            except EmployeeWorkHistory.DoesNotExist:
                logger.warning(f"Work history {work_history_id} does not exist")
                return {"success": True, "message": "Work history not found, skipped"}

            report_date = work_history.date
            branch_id = work_history.branch_id
            block_id = work_history.block_id
            department_id = work_history.department_id
            event_name = work_history.name
            status = work_history.status
            previous_data = work_history.previous_data or {}

        if not (branch_id and block_id and department_id):
            logger.warning(f"Work history {work_history_id} missing org fields")
            return {"success": True, "message": "Missing org fields, skipped"}

        logger.info(
            f"Incrementally updating HR reports for work history {work_history_id} "
            f"(event: {event_type}, date: {report_date})"
        )

        # Perform incremental update
        with transaction.atomic():
            _increment_staff_growth(
                report_date, branch_id, block_id, department_id,
                event_name, status, previous_data, event_type, old_values
            )

        return {
            "success": True,
            "work_history_id": work_history_id,
            "event_type": event_type,
            "report_date": str(report_date),
        }

    except Exception as e:
        logger.exception(f"Error in incremental HR reports update for work history {work_history_id}: {str(e)}")
        try:
            raise self.retry(exc=e, countdown=AGGREGATION_RETRY_DELAY * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            return {"success": False, "work_history_id": work_history_id, "error": str(e)}


@shared_task(bind=True, max_retries=AGGREGATION_MAX_RETRIES)
def aggregate_hr_reports_batch(self, target_date: str | None = None) -> dict[str, Any]:
    """Batch aggregation of HR reports for a specific date.

    This scheduled task runs at midnight to aggregate all HR reporting data
    for the previous day. It ensures data consistency and catches any missed
    or failed event-driven aggregations.

    Args:
        self: Celery task instance
        target_date: Date to aggregate (ISO format YYYY-MM-DD). Defaults to yesterday.

    Returns:
        dict: Aggregation result with success status and metadata
    """
    try:
        # Parse target date or default to yesterday
        if target_date:
            report_date = datetime.fromisoformat(target_date).date()
        else:
            report_date = (timezone.now() - timedelta(days=1)).date()

        logger.info(f"Starting batch HR reports aggregation for {report_date}")

        # Get unique org units with work history on this date
        org_unit_ids = (
            EmployeeWorkHistory.objects.filter(date=report_date)
            .values_list("branch_id", "block_id", "department_id")
            .distinct()
        )

        # Fetch all org units in one query
        branch_ids = {unit[0] for unit in org_unit_ids if unit[0]}
        block_ids = {unit[1] for unit in org_unit_ids if unit[1]}
        department_ids = {unit[2] for unit in org_unit_ids if unit[2]}

        branches = {b.id: b for b in Branch.objects.filter(id__in=branch_ids)}
        blocks = {bl.id: bl for bl in Block.objects.filter(id__in=block_ids)}
        departments = {d.id: d for d in Department.objects.filter(id__in=department_ids)}

        org_units_count = 0
        with transaction.atomic():
            for branch_id, block_id, department_id in org_unit_ids:
                if branch_id and block_id and department_id:
                    branch = branches.get(branch_id)
                    block = blocks.get(block_id)
                    department = departments.get(department_id)

                    if branch and block and department:
                        _aggregate_staff_growth_for_date(report_date, branch, block, department)
                        _aggregate_employee_status_for_date(report_date, branch, block, department)
                        org_units_count += 1

        logger.info(
            f"Batch HR reports aggregation complete for {report_date}. "
            f"Processed {org_units_count} organizational units."
        )

        return {
            "success": True,
            "target_date": str(report_date),
            "org_units_processed": org_units_count,
        }

    except Exception as e:
        logger.exception(f"Error in batch HR reports aggregation: {str(e)}")
        try:
            raise self.retry(exc=e, countdown=AGGREGATION_RETRY_DELAY * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            return {"success": False, "target_date": target_date or "yesterday", "error": str(e)}


#### Helper functions for HR report aggregation


def _increment_staff_growth(
    report_date: date,
    branch_id: int,
    block_id: int,
    department_id: int,
    event_name: str,
    status: str | None,
    previous_data: dict,
    event_type: str,
    old_values: dict | None = None,
) -> None:
    """Incrementally update staff growth report based on event.

    Args:
        report_date: Date of the report
        branch_id: Branch ID
        block_id: Block ID
        department_id: Department ID
        event_name: Type of work history event
        status: New status (for status change events)
        previous_data: Previous values before the event
        event_type: "create", "update", or "delete"
        old_values: Old values for update/delete events
    """
    # Calculate month and week keys
    month_key = report_date.strftime("%m/%Y")
    week_number = report_date.isocalendar()[1]
    week_key = f"Week {week_number} - {month_key}"

    # Get or create the report
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

    # Determine increment/decrement value
    delta = 1 if event_type == "create" else -1 if event_type == "delete" else 0

    # Update counters based on event type
    if event_name == EmployeeWorkHistory.EventType.TRANSFER:
        report.num_transfers = F("num_transfers") + delta
    elif event_name == EmployeeWorkHistory.EventType.CHANGE_STATUS:
        if status == Employee.Status.RESIGNED:
            report.num_resignations = F("num_resignations") + delta
        elif status == Employee.Status.ACTIVE:
            # Check if it's a return (from onboarding or unpaid leave)
            old_status = previous_data.get("status")
            if old_status in [Employee.Status.ONBOARDING, Employee.Status.UNPAID_LEAVE]:
                report.num_returns = F("num_returns") + delta

    report.save(update_fields=["num_transfers", "num_resignations", "num_returns"])

    logger.debug(
        f"Incremented staff growth for {report_date} - "
        f"Branch{branch_id}/Block{block_id}/Dept{department_id}: {event_name} ({event_type})"
    )


def _aggregate_staff_growth_for_date(report_date: date, branch, block, department) -> None:
    """Full re-aggregation of staff growth report for batch processing.

    Args:
        report_date: Date to aggregate
        branch: Branch instance
        block: Block instance
        department: Department instance
    """
    # Calculate month and week keys
    month_key = report_date.strftime("%m/%Y")
    week_number = report_date.isocalendar()[1]
    week_key = f"Week {week_number} - {month_key}"

    # Count work history events using aggregation
    work_histories = EmployeeWorkHistory.objects.filter(
        date=report_date,
        branch=branch,
        block=block,
        department=department,
    )

    # Count different event types
    num_transfers = work_histories.filter(name=EmployeeWorkHistory.EventType.TRANSFER).count()

    num_resignations = work_histories.filter(
        name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
        status=Employee.Status.RESIGNED,
    ).count()

    num_returns = work_histories.filter(
        name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
        status=Employee.Status.ACTIVE,
    ).filter(
        Q(previous_data__status=Employee.Status.ONBOARDING)
        | Q(previous_data__status=Employee.Status.UNPAID_LEAVE)
    ).count()

    # Update or create the report record
    StaffGrowthReport.objects.update_or_create(
        report_date=report_date,
        branch=branch,
        block=block,
        department=department,
        defaults={
            "month_key": month_key,
            "week_key": week_key,
            "num_transfers": num_transfers,
            "num_resignations": num_resignations,
            "num_returns": num_returns,
            "num_introductions": 0,
            "num_recruitment_source": 0,
        },
    )

    logger.debug(
        f"Aggregated staff growth for {report_date} - "
        f"{branch.name}/{block.name}/{department.name}: "
        f"transfers={num_transfers}, resignations={num_resignations}, returns={num_returns}"
    )


def _aggregate_employee_status_for_date(report_date: date, branch, block, department) -> None:
    """Aggregate employee status breakdown using efficient queries.

    Args:
        report_date: Date to aggregate
        branch: Branch instance
        block: Block instance
        department: Department instance
    """
    # Use single aggregation query with conditional counting
    status_counts = (
        Employee.objects.filter(
            branch=branch,
            block=block,
            department=department,
        )
        .values("status")
        .annotate(count=Count("id"))
    )

    status_dict = {item["status"]: item["count"] for item in status_counts}

    count_active = status_dict.get(Employee.Status.ACTIVE, 0)
    count_onboarding = status_dict.get(Employee.Status.ONBOARDING, 0)
    count_maternity_leave = status_dict.get(Employee.Status.MATERNITY_LEAVE, 0)
    count_unpaid_leave = status_dict.get(Employee.Status.UNPAID_LEAVE, 0)
    count_resigned = status_dict.get(Employee.Status.RESIGNED, 0)

    # Count resignation reasons in single query
    resignation_reasons = (
        Employee.objects.filter(
            branch=branch,
            block=block,
            department=department,
            status=Employee.Status.RESIGNED,
            resignation_reason__isnull=False,
        )
        .values("resignation_reason")
        .annotate(count=Count("id"))
    )

    resignation_reasons_dict = {item["resignation_reason"]: item["count"] for item in resignation_reasons}

    total_not_resigned = count_active + count_onboarding + count_maternity_leave + count_unpaid_leave

    # Update or create the report record
    EmployeeStatusBreakdownReport.objects.update_or_create(
        report_date=report_date,
        branch=branch,
        block=block,
        department=department,
        defaults={
            "count_active": count_active,
            "count_onboarding": count_onboarding,
            "count_maternity_leave": count_maternity_leave,
            "count_unpaid_leave": count_unpaid_leave,
            "count_resigned": count_resigned,
            "total_not_resigned": total_not_resigned,
            "count_resigned_reasons": resignation_reasons_dict,
        },
    )

    logger.debug(
        f"Aggregated employee status for {report_date} - "
        f"{branch.name}/{block.name}/{department.name}: "
        f"active={count_active}, resigned={count_resigned}"
    )
