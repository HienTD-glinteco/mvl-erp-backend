"""Celery tasks for HR reports aggregation.

This module contains event-driven and batch tasks for aggregating HR reporting data.
Tasks aggregate data into StaffGrowthReport and EmployeeStatusBreakdownReport models.
"""

import logging
from datetime import date, datetime, timedelta
from typing import Any

from celery import shared_task
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.hrm.models import (
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
def aggregate_hr_reports_for_work_history(self, work_history_id: int) -> dict[str, Any]:
    """Aggregate HR reports for a single work history event.

    This event-driven task is triggered when an EmployeeWorkHistory record
    is created, updated, or deleted. It updates the relevant report records
    for the date of the work history event.

    Args:
        self: Celery task instance
        work_history_id: ID of the EmployeeWorkHistory record

    Returns:
        dict: Aggregation result with keys:
            - success: bool indicating if aggregation succeeded
            - work_history_id: int work history ID
            - report_date: date of the report
            - error: str error message (if failed)
    """
    try:
        # Get work history record
        try:
            work_history = EmployeeWorkHistory.objects.select_related(
                "employee", "branch", "block", "department"
            ).get(id=work_history_id)
        except EmployeeWorkHistory.DoesNotExist:
            logger.warning(f"Work history {work_history_id} does not exist, skipping aggregation")
            return {
                "success": True,
                "work_history_id": work_history_id,
                "report_date": None,
                "message": "Work history deleted, skipped",
            }

        report_date = work_history.date
        logger.info(
            f"Aggregating HR reports for work history {work_history_id} "
            f"(employee: {work_history.employee.code}, date: {report_date})"
        )

        # Aggregate reports for this date and organizational units
        with transaction.atomic():
            _aggregate_staff_growth_for_date(report_date, work_history.branch, work_history.block, work_history.department)
            _aggregate_employee_status_for_date(report_date, work_history.branch, work_history.block, work_history.department)

        logger.info(f"Successfully aggregated HR reports for work history {work_history_id}")
        return {
            "success": True,
            "work_history_id": work_history_id,
            "report_date": str(report_date),
            "error": None,
        }

    except Exception as e:
        logger.exception(f"Error aggregating HR reports for work history {work_history_id}: {str(e)}")
        # Retry on failure
        try:
            raise self.retry(exc=e, countdown=AGGREGATION_RETRY_DELAY * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            return {
                "success": False,
                "work_history_id": work_history_id,
                "report_date": None,
                "error": str(e),
            }


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

        logger.info(f"Starting batch HR reports aggregation for {report_date}")

        # Get all unique organizational unit combinations that have work history on this date
        org_units = (
            EmployeeWorkHistory.objects.filter(date=report_date)
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

                    _aggregate_staff_growth_for_date(report_date, branch, block, department)
                    _aggregate_employee_status_for_date(report_date, branch, block, department)
                    org_units_count += 1

        logger.info(
            f"Successfully completed batch HR reports aggregation for {report_date}. "
            f"Processed {org_units_count} organizational units."
        )

        return {
            "success": True,
            "target_date": str(report_date),
            "org_units_processed": org_units_count,
            "error": None,
        }

    except Exception as e:
        logger.exception(f"Error in batch HR reports aggregation: {str(e)}")
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


#### Helper functions for HR report aggregation


def _aggregate_staff_growth_for_date(report_date: date, branch, block, department) -> None:
    """Aggregate staff growth report for a specific date and organizational unit.

    Args:
        report_date: Date to aggregate
        branch: Branch instance
        block: Block instance
        department: Department instance
    """
    # Calculate month and week keys
    month_key = report_date.strftime("%m/%Y")
    # Week key format: "Week W - MM/YYYY"
    week_number = report_date.isocalendar()[1]
    week_key = f"Week {week_number} - {month_key}"

    # Count work history events on this date for this org unit
    work_histories = EmployeeWorkHistory.objects.filter(
        date=report_date,
        branch=branch,
        block=block,
        department=department,
    )

    # Count different event types
    num_transfers = work_histories.filter(
        name=EmployeeWorkHistory.EventType.TRANSFER
    ).count()

    # Count status changes to different statuses
    num_resignations = work_histories.filter(
        name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
        status=Employee.Status.RESIGNED,
    ).count()

    # Count new hires (status changes from onboarding to active)
    num_returns = work_histories.filter(
        name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
        status=Employee.Status.ACTIVE,
    ).filter(
        Q(previous_data__status=Employee.Status.ONBOARDING) |
        Q(previous_data__status=Employee.Status.UNPAID_LEAVE)
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
            "num_introductions": 0,  # Placeholder - would need Employee model changes
            "num_recruitment_source": 0,  # Placeholder - would be populated from recruitment
        },
    )

    logger.debug(
        f"Aggregated staff growth for {report_date} - "
        f"{branch.name}/{block.name}/{department.name}: "
        f"transfers={num_transfers}, resignations={num_resignations}, returns={num_returns}"
    )


def _aggregate_employee_status_for_date(report_date: date, branch, block, department) -> None:
    """Aggregate employee status breakdown for a specific date and organizational unit.

    Args:
        report_date: Date to aggregate
        branch: Branch instance
        block: Block instance
        department: Department instance
    """
    # Get all employees in this org unit as of the report date
    employees = Employee.objects.filter(
        branch=branch,
        block=block,
        department=department,
    )

    # Count by status
    status_counts = employees.values("status").annotate(count=Count("id"))
    status_dict = {item["status"]: item["count"] for item in status_counts}

    count_active = status_dict.get(Employee.Status.ACTIVE, 0)
    count_onboarding = status_dict.get(Employee.Status.ONBOARDING, 0)
    count_maternity_leave = status_dict.get(Employee.Status.MATERNITY_LEAVE, 0)
    count_unpaid_leave = status_dict.get(Employee.Status.UNPAID_LEAVE, 0)
    count_resigned = status_dict.get(Employee.Status.RESIGNED, 0)

    # Count resignation reasons
    resignation_reasons = employees.filter(
        status=Employee.Status.RESIGNED
    ).values("resignation_reason").annotate(count=Count("id"))

    resignation_reasons_dict = {
        item["resignation_reason"]: item["count"]
        for item in resignation_reasons
        if item["resignation_reason"]
    }

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
        f"active={count_active}, resigned={count_resigned}, total_not_resigned={total_not_resigned}"
    )
