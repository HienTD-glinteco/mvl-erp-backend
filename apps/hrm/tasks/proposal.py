"""Proposal-related Celery tasks."""

import logging

from celery import shared_task
from django.db.models import Exists, OuterRef, Q
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

    updated_count = 0
    leave_statuses = [Employee.Status.UNPAID_LEAVE, Employee.Status.MATERNITY_LEAVE]

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
            employee.save(update_fields=["status", "resignation_start_date", "resignation_end_date"])
            updated_count += 1
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
            employee.save(update_fields=["status", "resignation_start_date", "resignation_end_date"])
            updated_count += 1
            logger.info(
                "Marking employee %s for MATERNITY_LEAVE status update from proposal %s",
                employee.id,
                proposal.code,
            )

    active_leave_subquery = Proposal.objects.filter(
        proposal_status=ProposalStatus.APPROVED,
        created_by=OuterRef("pk"),
    ).filter(
        Q(
            proposal_type=ProposalType.UNPAID_LEAVE,
            unpaid_leave_start_date__lte=today,
            unpaid_leave_end_date__gte=today,
        )
        | Q(
            proposal_type=ProposalType.MATERNITY_LEAVE,
            maternity_leave_start_date__lte=today,
            maternity_leave_end_date__gte=today,
        )
    )

    ended_leave_subquery = Proposal.objects.filter(
        proposal_status=ProposalStatus.APPROVED,
        created_by=OuterRef("pk"),
    ).filter(
        Q(proposal_type=ProposalType.UNPAID_LEAVE, unpaid_leave_end_date__lt=today)
        | Q(proposal_type=ProposalType.MATERNITY_LEAVE, maternity_leave_end_date__lt=today)
    )

    employees_to_reactivate = (
        Employee.objects.filter(status__in=leave_statuses)
        .annotate(has_active_leave=Exists(active_leave_subquery), has_ended_leave=Exists(ended_leave_subquery))
        .filter(has_active_leave=False, has_ended_leave=True)
    )

    for employee in employees_to_reactivate.iterator():
        employee.status = Employee.Status.ACTIVE
        employee.resignation_start_date = None
        employee.resignation_end_date = None
        employee.resignation_reason = None
        employee.save(update_fields=["status", "resignation_start_date", "resignation_end_date", "resignation_reason"])
        updated_count += 1
        logger.info("Marking employee %s for ACTIVE status update after leave end", employee.id)

    logger.info(
        "Employee status update task completed: %d employees updated",
        updated_count,
    )
