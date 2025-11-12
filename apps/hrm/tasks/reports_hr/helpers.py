"""Helper functions for HR reports aggregation.

This module contains all helper functions used by both event-driven and batch tasks.
"""

import logging
from datetime import date
from typing import Any, cast

from django.db.models import F, Q

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


def _increment_staff_growth(event_type: str, snapshot: dict[str, Any]) -> None:
    """Incrementally update staff growth report based on event snapshot.

    Handles transfers correctly by updating both source and destination departments.

    Event Processing Logic:
    - CREATE: Increment counters for new work history (+1)
    - UPDATE: Revert old values (-1), apply new values (+1)
    - DELETE: Decrement counters for deleted work history (-1)

    Transfer Handling:
    - For transfers, BOTH source and destination departments are affected
    - Destination department: increment by delta
    - Source department: decrement by delta (opposite sign)

    Args:
        event_type: "create", "update", or "delete"
        snapshot: Dict with previous and current state:
            - previous: Old state (None for create, dict for update/delete)
            - current: New state (dict for create/update, None for delete)
    """
    previous = snapshot.get("previous")
    current = snapshot.get("current")

    # Process based on event type
    if event_type == "create":
        # New work history record - increment counters
        if isinstance(current, dict):
            _process_staff_growth_change(cast(dict[str, Any], current), delta=1)

    elif event_type == "update":
        # Updated work history - revert old values and apply new values
        if isinstance(previous, dict):
            _process_staff_growth_change(cast(dict[str, Any], previous), delta=-1)
        if isinstance(current, dict):
            _process_staff_growth_change(cast(dict[str, Any], current), delta=1)

    elif event_type == "delete":
        # Deleted work history - decrement counters
        if isinstance(previous, dict):
            _process_staff_growth_change(cast(dict[str, Any], previous), delta=-1)


def _process_staff_growth_change(data: dict[str, Any], delta: int) -> None:
    """Process a single staff growth change (increment or decrement).

    Calculation Rules:
    - New Hire: Increment num_new_hires when event = ONBOARDING
    - Resignation: Increment num_resignations when event = RESIGNATION
    - Transfer: Increment destination dept, decrement source dept when event = TRANSFER

    All counters are updated atomically using F() expressions for thread safety.

    Args:
        data: Work history data snapshot containing:
            - date: Report date
            - name: Event name (ONBOARDING, RESIGNATION, TRANSFER, etc.)
            - branch_id, block_id, department_id: Org unit identifiers
            - previous_data: Dict with old org unit IDs (for transfers)
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
            report_date,
            data["branch_id"],
            data["block_id"],
            data["department_id"],
            "num_transfers",
            delta,
            month_key,
            week_key,
        )

        # If there's previous org data, decrement from source department
        if previous_data:
            old_branch_id = previous_data.get("branch_id")
            old_block_id = previous_data.get("block_id")
            old_department_id = previous_data.get("department_id")

            if old_branch_id and old_block_id and old_department_id:
                # Different from current? Then update source department
                if (
                    old_branch_id != data["branch_id"]
                    or old_block_id != data["block_id"]
                    or old_department_id != data["department_id"]
                ):
                    # Source department loses a transfer (opposite sign of delta)
                    _update_staff_growth_counter(
                        report_date,
                        old_branch_id,
                        old_block_id,
                        old_department_id,
                        "num_transfers",
                        -delta,
                        month_key,
                        week_key,
                    )

    # Handle status changes
    elif event_name == EmployeeWorkHistory.EventType.CHANGE_STATUS:
        branch_id = data["branch_id"]
        block_id = data["block_id"]
        department_id = data["department_id"]

        if status == Employee.Status.RESIGNED:
            _update_staff_growth_counter(
                report_date, branch_id, block_id, department_id, "num_resignations", delta, month_key, week_key
            )
        elif status == Employee.Status.ACTIVE:
            # Check if it's a return (from onboarding or unpaid leave)
            old_status = previous_data.get("status")
            if old_status in Employee.Status.get_leave_statuses():
                _update_staff_growth_counter(
                    report_date, branch_id, block_id, department_id, "num_returns", delta, month_key, week_key
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
        f"Updated {counter_field} by {delta} for {report_date} - Branch{branch_id}/Block{block_id}/Dept{department_id}"
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

    num_returns = (
        work_histories.filter(
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.ACTIVE,
        )
        .filter(
            Q(previous_data__status=Employee.Status.ONBOARDING) | Q(previous_data__status=Employee.Status.UNPAID_LEAVE)
        )
        .count()
    )

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
            # Note: num_introductions and num_recruitment_source are set by other tasks
            # and should not be overwritten here
        },
    )

    logger.debug(
        f"Aggregated staff growth for {report_date} - "
        f"{branch.name}/{block.name}/{department.name}: "
        f"transfers={num_transfers}, resignations={num_resignations}, returns={num_returns}"
    )


def _aggregate_employee_status_for_date(report_date: date, branch, block, department) -> None:
    """Aggregate employee status breakdown using EmployeeWorkHistory for historical accuracy.

    Uses EmployeeWorkHistory to get the correct state of employees at the report_date,
    ensuring accurate historical snapshots.

    Args:
        report_date: Date to aggregate
        branch: Branch instance
        block: Block instance
        department: Department instance
    """
    # Get the latest work history for each employee up to the report_date
    # This gives us the historical snapshot of employee status at that point in time
    latest_work_histories = (
        EmployeeWorkHistory.objects.filter(
            branch=branch,
            block=block,
            department=department,
            date__lte=report_date,
        )
        .order_by("employee_id", "-date", "-id")
        .distinct("employee_id")
    )

    # Extract employee IDs and their statuses from work history
    employee_statuses: dict[int, Any] = {}
    employee_resignation_reasons: dict[int, str] = {}

    for wh in latest_work_histories:
        # Get the status from work history if it's a status change event
        if wh.name == EmployeeWorkHistory.EventType.CHANGE_STATUS and wh.status:
            employee_statuses[wh.employee_id] = wh.status
            if wh.status == Employee.Status.RESIGNED and wh.resignation_reason:
                employee_resignation_reasons[wh.employee_id] = wh.resignation_reason
        # Otherwise, use the employee's current status
        elif wh.employee_id not in employee_statuses:
            employee_statuses[wh.employee_id] = wh.employee.status
            if wh.employee.status == Employee.Status.RESIGNED and wh.employee.resignation_reason:
                employee_resignation_reasons[wh.employee_id] = wh.employee.resignation_reason

    # Count statuses
    status_counts: dict[Any, int] = {}
    for status in employee_statuses.values():
        status_counts[status] = status_counts.get(status, 0) + 1

    count_active = status_counts.get(Employee.Status.ACTIVE, 0)
    count_onboarding = status_counts.get(Employee.Status.ONBOARDING, 0)
    count_maternity_leave = status_counts.get(Employee.Status.MATERNITY_LEAVE, 0)
    count_unpaid_leave = status_counts.get(Employee.Status.UNPAID_LEAVE, 0)
    count_resigned = status_counts.get(Employee.Status.RESIGNED, 0)

    # Count resignation reasons
    resignation_reasons_dict: dict[str, int] = {}
    for reason in employee_resignation_reasons.values():
        resignation_reasons_dict[reason] = resignation_reasons_dict.get(reason, 0) + 1

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
