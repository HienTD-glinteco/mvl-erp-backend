from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.hrm.constants import ProposalType
from apps.hrm.models import (
    AttendanceExemption,
    CompensatoryWorkday,
    Contract,
    Holiday,
    Proposal,
)
from apps.hrm.tasks.timesheet_triggers import (
    process_calendar_change,
    process_contract_change,
    process_exemption_change,
    process_proposal_change,
)


@receiver(post_save, sender=Contract)
def contract_changed_handler(sender, instance: Contract, created, **kwargs):
    """
    Handle Contract changes.
    Only update snapshot fields (contract, net_percentage, is_full_salary).
    Do NOT recalculate hours/working_days as contract doesn't affect them.
    """
    if not instance.effective_date or not instance.employee_id:
        return

    # UPDATED: Trigger for ACTIVE, ABOUT_TO_EXPIRE, and EXPIRED.
    # The important part is that the task handles retroactive updates correctly.
    if instance.status in [
        Contract.ContractStatus.ACTIVE,
        Contract.ContractStatus.ABOUT_TO_EXPIRE,
        Contract.ContractStatus.EXPIRED,
    ]:
        transaction.on_commit(lambda: process_contract_change.delay(instance))


@receiver([post_save, post_delete], sender=Holiday)
@receiver([post_save, post_delete], sender=CompensatoryWorkday)
def calendar_event_changed_handler(sender, instance, **kwargs):
    """
    Handle Holiday or CompensatoryWorkday changes.
    Affects 'day_type' and potentially status/working_days.
    """
    # Determine date range
    start_date = getattr(instance, "start_date", None) or getattr(instance, "date", None)
    end_date = getattr(instance, "end_date", None) or getattr(instance, "date", None)

    if not start_date:
        return

    if not end_date:
        end_date = start_date

    transaction.on_commit(lambda: process_calendar_change.delay(start_date, end_date))


@receiver([post_save, post_delete], sender=AttendanceExemption)
def exemption_changed_handler(sender, instance: AttendanceExemption, **kwargs):
    """
    Handle AttendanceExemption changes.
    """
    if not instance.employee_id or not instance.effective_date:
        return

    transaction.on_commit(lambda: process_exemption_change.delay(instance))


@receiver([post_save, post_delete], sender=Proposal)
def proposal_changed_handler(sender, instance: Proposal, **kwargs):
    """
    Handle Proposal changes (Leaves, OT, etc).
    """
    if not instance.created_by_id:
        return

    if instance.proposal_type not in [
        ProposalType.PAID_LEAVE,
        ProposalType.UNPAID_LEAVE,
        ProposalType.MATERNITY_LEAVE,
        ProposalType.OVERTIME_WORK,
        ProposalType.LATE_EXEMPTION,
        ProposalType.POST_MATERNITY_BENEFITS,
        ProposalType.TIMESHEET_ENTRY_COMPLAINT,
    ]:
        return

    transaction.on_commit(lambda: process_proposal_change.delay(instance))
