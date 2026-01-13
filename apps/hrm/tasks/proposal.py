"""Proposal-related Celery tasks."""

import logging

from celery import shared_task
from django.utils import timezone

from apps.hrm.constants import ProposalStatus, ProposalType
from apps.hrm.models import Employee, Proposal

logger = logging.getLogger(__name__)


@shared_task()
def update_employee_status_from_approved_leave_proposals() -> None:
    """
    Task to update employee status based on approved leave proposals.

    This task finds all APPROVED proposals of type UNPAID_LEAVE and MATERNITY_LEAVE
    where today falls within the leave period (start_date <= today <= end_date),
    and updates the employee's status accordingly:
    - UNPAID_LEAVE proposal -> Employee.Status.UNPAID_LEAVE
    - MATERNITY_LEAVE proposal -> Employee.Status.MATERNITY_LEAVE

    Also sets resignation_start_date and resignation_end_date on the employee.

    This task is scheduled to run daily at 00:00.
    """
    today = timezone.localdate()

    employees_to_update: list[Employee] = []

    # Find approved UNPAID_LEAVE proposals where today is within the leave period
    unpaid_leave_proposals = Proposal.objects.filter(
        proposal_type=ProposalType.UNPAID_LEAVE,
        proposal_status=ProposalStatus.APPROVED,
        unpaid_leave_start_date__lte=today,
        unpaid_leave_end_date__gte=today,
    ).select_related("created_by")

    for proposal in unpaid_leave_proposals:
        employee = proposal.created_by
        if employee and employee.status != Employee.Status.UNPAID_LEAVE:
            employee.status = Employee.Status.UNPAID_LEAVE
            employee.resignation_start_date = proposal.unpaid_leave_start_date
            employee.resignation_end_date = proposal.unpaid_leave_end_date
            employees_to_update.append(employee)
            logger.info(
                "Marking employee %s for UNPAID_LEAVE status update from proposal %s",
                employee.id,
                proposal.code,
            )

    # Find approved MATERNITY_LEAVE proposals where today is within the leave period
    maternity_leave_proposals = Proposal.objects.filter(
        proposal_type=ProposalType.MATERNITY_LEAVE,
        proposal_status=ProposalStatus.APPROVED,
        maternity_leave_start_date__lte=today,
        maternity_leave_end_date__gte=today,
    ).select_related("created_by")

    for proposal in maternity_leave_proposals:
        employee = proposal.created_by
        if employee and employee.status != Employee.Status.MATERNITY_LEAVE:
            employee.status = Employee.Status.MATERNITY_LEAVE
            employee.resignation_start_date = proposal.maternity_leave_start_date
            employee.resignation_end_date = proposal.maternity_leave_end_date
            employees_to_update.append(employee)
            logger.info(
                "Marking employee %s for MATERNITY_LEAVE status update from proposal %s",
                employee.id,
                proposal.code,
            )

    # Bulk update all employees at once
    if employees_to_update:
        Employee.objects.bulk_update(
            employees_to_update,
            fields=["status", "resignation_start_date", "resignation_end_date"],
        )

    logger.info(
        "Employee status update task completed: %d employees updated",
        len(employees_to_update),
    )
