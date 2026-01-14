"""Helper functions for HR reports aggregation.

This module contains all helper functions used by both event-driven and batch tasks.
"""

import logging
from datetime import date, timedelta
from typing import Any, cast

from django.db.models import Exists, F, OuterRef, Q, QuerySet, Value, Window
from django.db.models.functions import Greatest, RowNumber

from apps.hrm.models import (
    Block,
    Branch,
    Department,
    Employee,
    EmployeeResignedReasonReport,
    EmployeeStatusBreakdownReport,
    EmployeeWorkHistory,
    Position,
    StaffGrowthReport,
)

logger = logging.getLogger(__name__)


def _get_work_history_queryset(filters: dict[str, Any] | None = None) -> QuerySet[EmployeeWorkHistory]:
    """Get a filtered EmployeeWorkHistory queryset with common exclusions.

    This helper function creates a queryset that:
    - Excludes employees with code_type="OS"
    - Excludes employees whose position has include_in_employee_report=False (using Exists subquery)
    - Applies additional filters if provided

    Args:
        filters: Optional dict of additional filters to apply to the queryset.
                 Keys should be valid field lookups for EmployeeWorkHistory.
                 Example: {"date": report_date, "branch": branch, "block": block}

    Returns:
        QuerySet[EmployeeWorkHistory]: Filtered queryset ready for further operations
    """
    # Build subquery for positions that should be excluded
    # Using Exists is more efficient than direct join for exclusion
    excluded_positions_subquery = Position.objects.filter(
        id=OuterRef("employee__position_id"),
        include_in_employee_report=False,
    )

    # Start with base queryset
    queryset = EmployeeWorkHistory.objects.all()

    # Apply additional filters if provided
    if filters:
        queryset = queryset.filter(**filters)

    # Apply common exclusions
    # 1. Exclude employees with code_type="OS"
    # 2. Exclude employees whose position has include_in_employee_report=False
    queryset = queryset.exclude(employee__code_type=Employee.CodeType.OS).exclude(Exists(excluded_positions_subquery))

    return queryset


def _should_process_employee(data: dict[str, Any]) -> bool:
    """Check if employee data should be processed in reports.

    Employees with code_type="OS" are excluded from reports.
    If employee_code_type is missing from data, defaults to processing the employee
    (safer to include than exclude).

    Args:
        data: Dictionary containing employee data with 'employee_code_type' key

    Returns:
        bool: True if employee should be processed, False if should be excluded
    """
    employee_code_type = data.get("employee_code_type")
    # Exclude only if explicitly set to OS; otherwise, include by default
    return employee_code_type != Employee.CodeType.OS


def _get_timeframe_range(event_date: date, timeframe_type: str) -> tuple[date, date]:
    """Get start and end dates for a timeframe."""
    if timeframe_type == StaffGrowthReport.TimeframeType.WEEK:
        # ISO week: Monday to Sunday
        start = event_date - timedelta(days=event_date.weekday())
        end = start + timedelta(days=6)
    else:  # MONTH
        start = event_date.replace(day=1)
        # Last day of month
        if event_date.month == 12:
            end = date(event_date.year, 12, 31)
        else:
            end = date(event_date.year, event_date.month + 1, 1) - timedelta(days=1)
    return start, end


def _get_event_history_filter(event_type: str) -> dict:
    """Map event_type to EmployeeWorkHistory filter kwargs."""
    filters = {
        "resignation": {
            "name": EmployeeWorkHistory.EventType.CHANGE_STATUS,
            "status": Employee.Status.RESIGNED,
        },
        "transfer": {"name": EmployeeWorkHistory.EventType.TRANSFER},
        "return": {
            "name": EmployeeWorkHistory.EventType.CHANGE_STATUS,
            "status": Employee.Status.ACTIVE,
        },
    }

    # Check if event types exist before adding them
    if hasattr(EmployeeWorkHistory.EventType, "INTRODUCTION"):
        filters["introduction"] = {"name": EmployeeWorkHistory.EventType.INTRODUCTION}

    if hasattr(EmployeeWorkHistory.EventType, "RECRUITMENT_SOURCE"):
        filters["recruitment_source"] = {"name": EmployeeWorkHistory.EventType.RECRUITMENT_SOURCE}

    return filters.get(event_type, {})


def _employee_already_counted_in_timeframe(
    employee_id: int,
    event_type: str,
    current_event_id: int | None,
    timeframe_start: date,
    timeframe_end: date,
    department_id: int,
) -> bool:
    """Check if employee already has this event type in timeframe (excluding current event).

    Returns True if there's ANOTHER event of same type for this employee
    in the same timeframe (meaning we should skip counting).
    """
    event_filter = _get_event_history_filter(event_type)
    if not event_filter:
        return False

    qs = EmployeeWorkHistory.objects.filter(
        employee_id=employee_id,
        department_id=department_id,
        date__range=(timeframe_start, timeframe_end),
        **event_filter,
    )

    if current_event_id:
        qs = qs.exclude(id=current_event_id)

    return qs.exists()


def _record_staff_growth_event(
    employee: Employee,
    event_type: str,
    event_date: date,
    event_id: int,
    branch: Branch,
    block: Block,
    department: Department,
) -> None:
    """Record a staff growth event with deduplication via EmployeeWorkHistory.

    Updates BOTH weekly and monthly reports. Uses EmployeeWorkHistory to check
    if employee was already counted in the timeframe (excluding current event).
    """
    # Calculate timeframe keys
    week_number = event_date.isocalendar()[1]
    year = event_date.isocalendar()[0]  # ISO year for week
    week_key = f"W{week_number:02d}-{year}"
    month_key = event_date.strftime("%m/%Y")

    # Map event_type to counter field
    counter_field_map = {
        "resignation": "num_resignations",
        "transfer": "num_transfers",
        "return": "num_returns",
        "introduction": "num_introductions",
        "recruitment_source": "num_recruitment_source",
    }
    counter_field = counter_field_map.get(event_type)
    if not counter_field:
        logger.warning(f"Unknown event type for staff growth: {event_type}")
        return

    # Process BOTH weekly and monthly timeframes
    timeframes = [
        (StaffGrowthReport.TimeframeType.WEEK, week_key),
        (StaffGrowthReport.TimeframeType.MONTH, month_key),
    ]

    for timeframe_type, timeframe_key in timeframes:
        # Get timeframe date range
        start_date, end_date = _get_timeframe_range(event_date, timeframe_type)

        # Check if employee already counted in this timeframe (excluding current event)
        if _employee_already_counted_in_timeframe(
            employee.id, event_type, event_id, start_date, end_date, department.id
        ):
            logger.debug(
                f"Skipped duplicate {event_type} for {employee.code} in {timeframe_key}"
            )
            continue

        # First event for this employee in timeframe → count it
        report, created = StaffGrowthReport.objects.get_or_create(
            timeframe_type=timeframe_type,
            timeframe_key=timeframe_key,
            branch=branch,
            block=block,
            department=department,
            defaults={
                "report_date": event_date, # BaseReportModel requires report_date
            }
        )

        setattr(report, counter_field, getattr(report, counter_field) + 1)
        report.save(update_fields=[counter_field])
        logger.debug(
            f"Recorded {event_type} for {employee.code} in {timeframe_key}"
        )


def _remove_staff_growth_event(
    employee_id: int,
    event_type: str,
    event_date: date,
    branch_id: int,
    block_id: int,
    department_id: int,
    current_event_id: int | None = None,
) -> None:
    """Remove a staff growth event (when deleted/reverted).

    Decrements counter only if no OTHER events of same type exist
    for this employee in the timeframe.
    """
    week_number = event_date.isocalendar()[1]
    year = event_date.isocalendar()[0]
    week_key = f"W{week_number:02d}-{year}"
    month_key = event_date.strftime("%m/%Y")

    counter_field_map = {
        "resignation": "num_resignations",
        "transfer": "num_transfers",
        "return": "num_returns",
        "introduction": "num_introductions",
        "recruitment_source": "num_recruitment_source",
    }
    counter_field = counter_field_map.get(event_type)
    if not counter_field:
        return

    timeframes = [
        (StaffGrowthReport.TimeframeType.WEEK, week_key),
        (StaffGrowthReport.TimeframeType.MONTH, month_key),
    ]

    for timeframe_type, timeframe_key in timeframes:
        start_date, end_date = _get_timeframe_range(event_date, timeframe_type)

        # Check if any OTHER events exist for this employee in timeframe
        # We pass current_event_id to exclude the event being deleted (if it's still visible)
        other_events_exist = _employee_already_counted_in_timeframe(
             employee_id, event_type, current_event_id, start_date, end_date, department_id
        )

        if not other_events_exist:
            # No more events → decrement counter
            try:
                report = StaffGrowthReport.objects.get(
                    timeframe_type=timeframe_type,
                    timeframe_key=timeframe_key,
                    branch_id=branch_id,
                    block_id=block_id,
                    department_id=department_id,
                )
                current_value = getattr(report, counter_field)
                if current_value > 0:
                    setattr(report, counter_field, current_value - 1)
                    report.save(update_fields=[counter_field])
                    logger.debug(
                        f"Decremented {event_type} for employee {employee_id} in {timeframe_key}"
                    )
            except StaffGrowthReport.DoesNotExist:
                pass


def _update_staff_growth_event(
    employee: Employee,
    event_type: str,
    old_event_date: date,
    new_event_date: date,
    event_id: int,
    old_branch_id: int,
    new_branch: Branch,
    old_block_id: int,
    new_block: Block,
    old_department_id: int,
    new_department: Department,
) -> None:
    """Handle event update - may need to move count between timeframes.

    Called when an EmployeeWorkHistory record is updated (date or org changed).
    """
    # Helper to compare timeframe keys
    def get_keys(d: date) -> tuple[str, str]:
        wn = d.isocalendar()[1]
        y = d.isocalendar()[0]
        return f"W{wn:02d}-{y}", d.strftime("%m/%Y")

    old_week_key, old_month_key = get_keys(old_event_date)
    new_week_key, new_month_key = get_keys(new_event_date)

    # Check if anything relevant changed
    week_changed = (old_week_key != new_week_key) or (old_department_id != new_department.id)
    month_changed = (old_month_key != new_month_key) or (old_department_id != new_department.id)

    # If strictly within same timeframe and same org, nothing to do (deduplication handles it)
    if not week_changed and not month_changed:
        return

    # If changed, treat as remove + add
    _remove_staff_growth_event(
        employee.id, event_type, old_event_date,
        old_branch_id, old_block_id, old_department_id,
        current_event_id=event_id
    )
    _record_staff_growth_event(
        employee, event_type, new_event_date, event_id,
        new_branch, new_block, new_department
    )


def _increment_staff_growth(event_type: str, snapshot: dict[str, Any]) -> None:
    """Incrementally update staff growth report based on event snapshot.

    Handles transfers correctly by updating both source and destination departments.

    Event Processing Logic:
    - CREATE: Record new event with deduplication
    - UPDATE: Revert old event and record new one
    - DELETE: Remove event if no others exist

    Args:
        event_type: "create", "update", or "delete"
        snapshot: Dict with previous and current state
    """
    previous = snapshot.get("previous")
    current = snapshot.get("current")

    # Helper to extract IDs and objects
    def get_org_objects(data_dict: dict[str, Any]) -> tuple[Branch, Block, Department]:
        return (
            Branch.objects.get(id=data_dict["branch_id"]),
            Block.objects.get(id=data_dict["block_id"]),
            Department.objects.get(id=data_dict["department_id"]),
        )

    # Determine specific event type (resignation, transfer, etc.)
    # We look at 'current' for create/update, 'previous' for delete
    data_for_type = current if current else previous
    if not data_for_type:
        return

    staff_event_type = None
    if data_for_type["name"] == EmployeeWorkHistory.EventType.TRANSFER:
        staff_event_type = "transfer"
    elif data_for_type["name"] == EmployeeWorkHistory.EventType.CHANGE_STATUS:
        if data_for_type.get("status") == Employee.Status.RESIGNED:
            staff_event_type = "resignation"
        elif data_for_type.get("status") == Employee.Status.ACTIVE:
             # Check return logic
            prev_data = data_for_type.get("previous_data", {})
            if prev_data and prev_data.get("status") in Employee.Status.get_leave_statuses():
                staff_event_type = "return"
    elif hasattr(EmployeeWorkHistory.EventType, "INTRODUCTION") and data_for_type["name"] == EmployeeWorkHistory.EventType.INTRODUCTION:
        staff_event_type = "introduction"
    elif hasattr(EmployeeWorkHistory.EventType, "RECRUITMENT_SOURCE") and data_for_type["name"] == EmployeeWorkHistory.EventType.RECRUITMENT_SOURCE:
        staff_event_type = "recruitment_source"

    if not staff_event_type:
        return

    # Process based on event type
    if event_type == "create":
        if isinstance(current, dict) and _should_process_employee(current):
            try:
                branch, block, department = get_org_objects(current)

                emp_id = current.get("employee_id")
                if not emp_id:
                     logger.warning("Employee ID missing in snapshot")
                     return

                employee = Employee.objects.get(id=emp_id)

                # We need event_id for deduplication exception
                event_id = current.get("id", 0)

                _record_staff_growth_event(
                    employee, staff_event_type, current["date"], event_id,
                    branch, block, department
                )

            except (Branch.DoesNotExist, Block.DoesNotExist, Department.DoesNotExist, Employee.DoesNotExist) as e:
                logger.warning(f"Missing related objects for staff growth create: {e}")

    elif event_type == "update":
        # Handle update via _update_staff_growth_event
        if isinstance(previous, dict) and isinstance(current, dict):
             # Check if we should process
            if not _should_process_employee(current) and not _should_process_employee(previous):
                return

            try:
                emp_id = current.get("employee_id") or previous.get("employee_id")
                if not emp_id:
                    logger.warning("Employee ID missing in snapshot for update")
                    return

                employee = Employee.objects.get(id=emp_id)
                event_id = current.get("id", 0)

                new_branch, new_block, new_department = get_org_objects(current)

                _update_staff_growth_event(
                    employee, staff_event_type,
                    previous["date"], current["date"],
                    event_id,
                    previous["branch_id"], new_branch,
                    previous["block_id"], new_block,
                    previous["department_id"], new_department
                )
            except (Branch.DoesNotExist, Block.DoesNotExist, Department.DoesNotExist, Employee.DoesNotExist) as e:
                logger.warning(f"Missing related objects for staff growth update: {e}")

    elif event_type == "delete":
        if isinstance(previous, dict) and _should_process_employee(previous):
            _remove_staff_growth_event(
                previous.get("employee_id"), staff_event_type, previous["date"],
                previous["branch_id"], previous["block_id"], previous["department_id"],
                current_event_id=previous.get("id")
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

    # Skip if employee has code_type="OS"
    if not _should_process_employee(data):
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


def _increment_employee_resigned_reason(event_type: str, snapshot: dict[str, Any]) -> None:
    """Incrementally update employee resigned reason report based on event snapshot.

    For resigned reason report, we need to re-aggregate as it's based on resignation dates
    and reasons. We only update the affected org unit.

    Args:
        event_type: "create", "update", or "delete"
        snapshot: Dict with previous and current state
    """
    # Get the date and org unit from the snapshot
    data = snapshot.get("current") or snapshot.get("previous")
    if not data:
        return

    # Skip if employee has code_type="OS"
    if not _should_process_employee(data):
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
        logger.warning(f"Org unit not found for resigned reason update: {branch_id}/{block_id}/{department_id}")
        return

    # Re-aggregate employee resigned reasons for this org unit
    _aggregate_employee_resigned_reason_for_date(report_date, branch, block, department)


def _aggregate_staff_growth_for_date(report_date: date, branch, block, department) -> None:
    """Full re-aggregation of staff growth report for batch processing.

    DEPRECATED: StaffGrowthReport is now updated incrementally via events.
    This function is kept for backward compatibility if needed, but logic
    has been moved to event-based tracking.
    """
    pass


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
    # Uses helper function to apply common exclusions
    # Use Window function with RowNumber to get latest record per employee
    # This approach works on both PostgreSQL and SQLite (unlike distinct("employee_id"))
    latest_work_histories = (
        _get_work_history_queryset(
            filters={
                "branch": branch,
                "block": block,
                "department": department,
                "date__lte": report_date,
            }
        )
        .annotate(
            row_num=Window(
                expression=RowNumber(),
                partition_by=[F("employee_id")],
                order_by=[F("date").desc(), F("id").desc()],
            )
        )
        .filter(row_num=1)
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


def _aggregate_employee_resigned_reason_for_date(report_date: date, branch, block, department) -> None:
    """Aggregate employee resigned reason report using EmployeeWorkHistory for historical accuracy.

    Uses EmployeeWorkHistory to get resigned employees for the specified date,
    counting by resignation reason. Only counts employees who:
    - Changed status to RESIGNED on the report_date
    - Do not have code_type = "OS"
    - Have valid resignation_reason

    Args:
        report_date: Date to aggregate (counts resignations that occurred on this date)
        branch: Branch instance
        block: Block instance
        department: Department instance
    """
    # Get work history records for employees who resigned on this specific date
    # Filter for CHANGE_STATUS events where status changed to RESIGNED
    # Uses helper function to apply common exclusions
    resigned_work_histories = _get_work_history_queryset(
        filters={
            "branch": branch,
            "block": block,
            "department": department,
            "date": report_date,
            "name": EmployeeWorkHistory.EventType.CHANGE_STATUS,
            "status": Employee.Status.RESIGNED,
        }
    ).select_related("employee")

    # Process resignation reasons and count resigned employees
    employee_resignation_reasons: dict[str, int] = {}
    count_resigned = 0

    for wh in resigned_work_histories:
        employee = wh.employee
        count_resigned += 1
        # Get resignation reason from work history or employee record
        reason = wh.resignation_reason or employee.resignation_reason
        if reason:
            # Map resignation reason to field name
            field_name = _get_resignation_reason_field_name(reason)
            if field_name:
                employee_resignation_reasons[field_name] = employee_resignation_reasons.get(field_name, 0) + 1

    # Prepare defaults dict with all reason fields
    defaults = {
        "count_resigned": count_resigned,
        "agreement_termination": employee_resignation_reasons.get("agreement_termination", 0),
        "probation_fail": employee_resignation_reasons.get("probation_fail", 0),
        "job_abandonment": employee_resignation_reasons.get("job_abandonment", 0),
        "disciplinary_termination": employee_resignation_reasons.get("disciplinary_termination", 0),
        "workforce_reduction": employee_resignation_reasons.get("workforce_reduction", 0),
        "underperforming": employee_resignation_reasons.get("underperforming", 0),
        "contract_expired": employee_resignation_reasons.get("contract_expired", 0),
        "voluntary_health": employee_resignation_reasons.get("voluntary_health", 0),
        "voluntary_personal": employee_resignation_reasons.get("voluntary_personal", 0),
        "voluntary_career_change": employee_resignation_reasons.get("voluntary_career_change", 0),
        "voluntary_other": employee_resignation_reasons.get("voluntary_other", 0),
        "other": employee_resignation_reasons.get("other", 0),
    }

    # Update or create the report record
    EmployeeResignedReasonReport.objects.update_or_create(
        report_date=report_date,
        branch=branch,
        block=block,
        department=department,
        defaults=defaults,
    )

    logger.debug(
        f"Aggregated employee resigned reasons for {report_date} - "
        f"{branch.name}/{block.name}/{department.name}: "
        f"total_resigned={count_resigned}"
    )


def _get_resignation_reason_field_name(reason: str | Employee.ResignationReason) -> str | None:
    """Map Employee.ResignationReason enum value to EmployeeResignedReasonReport field name.

    Args:
        reason: Resignation reason (string value or enum member)

    Returns:
        Field name in snake_case (e.g., "agreement_termination") or None if invalid
    """
    # Convert string to enum if needed
    if isinstance(reason, str):
        try:
            reason = Employee.ResignationReason(reason)
        except ValueError:
            return None

    reason_field_map = {
        Employee.ResignationReason.AGREEMENT_TERMINATION: "agreement_termination",
        Employee.ResignationReason.PROBATION_FAIL: "probation_fail",
        Employee.ResignationReason.JOB_ABANDONMENT: "job_abandonment",
        Employee.ResignationReason.DISCIPLINARY_TERMINATION: "disciplinary_termination",
        Employee.ResignationReason.WORKFORCE_REDUCTION: "workforce_reduction",
        Employee.ResignationReason.UNDERPERFORMING: "underperforming",
        Employee.ResignationReason.CONTRACT_EXPIRED: "contract_expired",
        Employee.ResignationReason.VOLUNTARY_HEALTH: "voluntary_health",
        Employee.ResignationReason.VOLUNTARY_PERSONAL: "voluntary_personal",
        Employee.ResignationReason.VOLUNTARY_CAREER_CHANGE: "voluntary_career_change",
        Employee.ResignationReason.VOLUNTARY_OTHER: "voluntary_other",
        Employee.ResignationReason.OTHER: "other",
    }
    return reason_field_map.get(reason)
