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
MAX_REPORT_LOOKBACK_DAYS = 365  # Maximum 1 year lookback for batch reports


@shared_task(bind=True, max_retries=AGGREGATION_MAX_RETRIES)
def aggregate_hr_reports_for_work_history(
    self, event_type: str, snapshot: dict[str, Any]
) -> dict[str, Any]:
    """Aggregate HR reports for a single work history event (smart incremental update).

    This event-driven task uses snapshot data to avoid race conditions where the
    work history record might be modified before the task processes.

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
        report_date = data["date"]
        
        logger.info(
            f"Incrementally updating HR reports for work history "
            f"(event: {event_type}, date: {report_date})"
        )

        # Perform incremental update
        with transaction.atomic():
            _increment_staff_growth(event_type, snapshot)
            _increment_employee_status(event_type, snapshot)

        return {
            "success": True,
            "event_type": event_type,
            "report_date": str(report_date),
        }

    except Exception as e:
        logger.exception(f"Error in incremental HR reports update: {str(e)}")
        try:
            raise self.retry(exc=e, countdown=AGGREGATION_RETRY_DELAY * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            return {"success": False, "error": str(e)}


@shared_task(bind=True, max_retries=AGGREGATION_MAX_RETRIES)
def aggregate_hr_reports_batch(self, target_date: str | None = None) -> dict[str, Any]:
    """Batch aggregation of HR reports for a date range.

    This scheduled task re-aggregates all HR reports for dates that have
    been modified within the lookback period (up to 1 year). It ensures
    data consistency even when past records are modified or deleted.

    Args:
        self: Celery task instance
        target_date: Specific date to aggregate (ISO format YYYY-MM-DD).
                    If None, aggregates all affected dates in lookback period.

    Returns:
        dict: Aggregation result with success status and metadata
    """
    try:
        if target_date:
            # Specific date provided
            report_date = datetime.fromisoformat(target_date).date()
            dates_to_process = [report_date]
        else:
            # Find all dates with work history changes in lookback period
            cutoff_date = timezone.now().date() - timedelta(days=MAX_REPORT_LOOKBACK_DAYS)
            dates_to_process = list(
                EmployeeWorkHistory.objects.filter(
                    date__gte=cutoff_date
                ).values_list("date", flat=True).distinct().order_by("date")
            )

        if not dates_to_process:
            logger.info("No dates to process for HR reports batch aggregation")
            return {"success": True, "dates_processed": 0, "org_units_processed": 0}

        logger.info(
            f"Starting batch HR reports aggregation for {len(dates_to_process)} dates "
            f"(from {dates_to_process[0]} to {dates_to_process[-1]})"
        )

        total_org_units = 0
        
        for process_date in dates_to_process:
            # Get unique org units with work history on this date
            org_unit_ids = (
                EmployeeWorkHistory.objects.filter(date=process_date)
                .values_list("branch_id", "block_id", "department_id")
                .distinct()
            )

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


#### Helper functions for HR report aggregation


def _increment_staff_growth(event_type: str, snapshot: dict[str, Any]) -> None:
    """Incrementally update staff growth report based on event snapshot.

    Handles transfers correctly by updating both source and destination departments.

    Args:
        event_type: "create", "update", or "delete"
        snapshot: Dict with previous and current state
    """
    previous = snapshot.get("previous")
    current = snapshot.get("current")

    # Process based on event type
    if event_type == "create":
        # New work history record - increment counters
        _process_staff_growth_change(current, delta=1)
        
    elif event_type == "update":
        # Updated work history - revert old values and apply new values
        if previous:
            _process_staff_growth_change(previous, delta=-1)
        if current:
            _process_staff_growth_change(current, delta=1)
            
    elif event_type == "delete":
        # Deleted work history - decrement counters
        if previous:
            _process_staff_growth_change(previous, delta=-1)


def _process_staff_growth_change(data: dict[str, Any], delta: int) -> None:
    """Process a single staff growth change (increment or decrement).

    Args:
        data: Work history data snapshot
        delta: +1 for increment, -1 for decrement
    """
    report_date = data["date"]
    event_name = data["name"]
    status = data.get("status")
    previous_data = data.get("previous_data", {})
    
    # Calculate month and week keys
    month_key = report_date.strftime("%m/%Y")
    week_number = report_date.isocalendar()[1]
    week_key = f"Week {week_number} - {month_key}"

    # Handle transfers - affects both source and destination departments
    if event_name == EmployeeWorkHistory.EventType.TRANSFER:
        # Increment for current (destination) department
        _update_staff_growth_counter(
            report_date, data["branch_id"], data["block_id"], data["department_id"],
            "num_transfers", delta, month_key, week_key
        )
        
        # If there's previous org data, decrement from source department
        if previous_data:
            old_branch_id = previous_data.get("branch_id")
            old_block_id = previous_data.get("block_id")
            old_department_id = previous_data.get("department_id")
            
            if old_branch_id and old_block_id and old_department_id:
                # Different from current? Then update source department
                if (old_branch_id != data["branch_id"] or 
                    old_block_id != data["block_id"] or 
                    old_department_id != data["department_id"]):
                    _update_staff_growth_counter(
                        report_date, old_branch_id, old_block_id, old_department_id,
                        "num_transfers", -delta, month_key, week_key
                    )
    
    # Handle status changes
    elif event_name == EmployeeWorkHistory.EventType.CHANGE_STATUS:
        branch_id = data["branch_id"]
        block_id = data["block_id"]
        department_id = data["department_id"]
        
        if status == Employee.Status.RESIGNED:
            _update_staff_growth_counter(
                report_date, branch_id, block_id, department_id,
                "num_resignations", delta, month_key, week_key
            )
        elif status == Employee.Status.ACTIVE:
            # Check if it's a return (from onboarding or unpaid leave)
            old_status = previous_data.get("status")
            if old_status in [Employee.Status.ONBOARDING, Employee.Status.UNPAID_LEAVE]:
                _update_staff_growth_counter(
                    report_date, branch_id, block_id, department_id,
                    "num_returns", delta, month_key, week_key
                )


def _update_staff_growth_counter(
    report_date: date,
    branch_id: int,
    block_id: int,
    department_id: int,
    counter_field: str,
    delta: int,
    month_key: str,
    week_key: str,
) -> None:
    """Update a specific counter in StaffGrowthReport.

    Args:
        report_date: Date of the report
        branch_id: Branch ID
        block_id: Block ID
        department_id: Department ID
        counter_field: Field name to update (e.g., "num_transfers")
        delta: Value to add (positive or negative)
        month_key: Month key for the report
        week_key: Week key for the report
    """
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

    # Update the specific counter using F() for atomic operation
    setattr(report, counter_field, F(counter_field) + delta)
    report.save(update_fields=[counter_field])

    logger.debug(
        f"Updated {counter_field} by {delta} for {report_date} - "
        f"Branch{branch_id}/Block{block_id}/Dept{department_id}"
    )


def _increment_employee_status(event_type: str, snapshot: dict[str, Any]) -> None:
    """Incrementally update employee status breakdown based on event snapshot.

    For employee status, we need to re-aggregate as it's based on current employee
    state, not work history events. However, we only update the affected org unit.

    Args:
        event_type: "create", "update", or "delete"
        snapshot: Dict with previous and current state
    """
    # Get the date and org unit from the snapshot
    data = snapshot.get("current") or snapshot.get("previous")
    if not data:
        return
    
    report_date = data["date"]
    branch_id = data["branch_id"]
    block_id = data["block_id"]
    department_id = data["department_id"]
    
    # Get org unit objects
    try:
        branch = Branch.objects.get(id=branch_id)
        block = Block.objects.get(id=block_id)
        department = Department.objects.get(id=department_id)
    except (Branch.DoesNotExist, Block.DoesNotExist, Department.DoesNotExist):
        logger.warning(f"Org unit not found for status update: {branch_id}/{block_id}/{department_id}")
        return
    
    # Re-aggregate employee status for this org unit
    _aggregate_employee_status_for_date(report_date, branch, block, department)


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
