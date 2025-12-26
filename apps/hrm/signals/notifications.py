from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils.translation import gettext as _

from apps.core.models import UserDevice
from apps.hrm.constants import ProposalStatus, ProposalType, ProposalVerifierStatus
from apps.hrm.models import Proposal, ProposalVerifier
from apps.notifications.utils import create_notification


@receiver(pre_save, sender=Proposal)
def track_proposal_status_change(sender, instance, **kwargs):
    """Track proposal status change."""
    if instance.pk:
        try:
            old_instance = Proposal.objects.get(pk=instance.pk)
            instance._old_status = old_instance.proposal_status
        except Proposal.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None


@receiver(post_save, sender=Proposal)
def notify_proposal_status_change(sender, instance, created, **kwargs):
    """Notify employee when their proposal status changes."""
    if created:
        return

    # Check if status has changed
    old_status = getattr(instance, "_old_status", None)
    if old_status == instance.proposal_status:
        return

    # HR Approval/Rejection
    # Assuming direct modification of proposal_status implies HR action (or final system action)

    if instance.proposal_status == ProposalStatus.APPROVED:
        # HR Approved
        _send_hr_notification(instance, approved=True)

    elif instance.proposal_status == ProposalStatus.REJECTED:
        # Rejected by HR.
        _send_hr_notification(instance, approved=False)


def _send_hr_notification(proposal, approved):
    recipient = proposal.created_by.user
    if not recipient:
        return

    # Scenario A: Timekeeping Complaint
    if proposal.proposal_type == ProposalType.TIMESHEET_ENTRY_COMPLAINT:
        if approved:
            message = _("Your timekeeping complaint has been approved by HR.")
        else:
            note = proposal.approval_note or ""
            message = _('Your timekeeping complaint was rejected by HR with note: "%(note)s"..') % {"note": note}

    # Scenario B: General Proposal
    else:
        proposal_type_display = proposal.get_proposal_type_display()
        if approved:
            message = _("Your %(proposal_type)s proposal has been approved by HR.") % {
                "proposal_type": proposal_type_display
            }
        else:
            note = proposal.approval_note or ""
            message = _('Your %(proposal_type)s proposal was rejected by HR with note: "%(note)s"..') % {
                "note": note,
                "proposal_type": proposal_type_display,
            }

    create_notification(
        actor=proposal.approved_by.user
        if proposal.approved_by and proposal.approved_by.user
        else recipient,  # Fallback to recipient if no actor, but ideally should be system or HR user
        recipient=recipient,
        verb="updated" if approved else "rejected",
        target=proposal,
        message=message,
        target_client=UserDevice.Client.MOBILE,
    )


@receiver(pre_save, sender=ProposalVerifier)
def track_proposal_verifier_status_change(sender, instance, **kwargs):
    """Track proposal verifier status change."""
    if instance.pk:
        try:
            old_instance = ProposalVerifier.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
        except ProposalVerifier.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None


@receiver(post_save, sender=ProposalVerifier)
def notify_proposal_verifier_change(sender, instance, created, **kwargs):
    """Notify employee when a manager verifies (confirms) or rejects their proposal."""
    # instance is ProposalVerifier

    # Check if status has changed
    old_status = getattr(instance, "_old_status", None)
    if old_status == instance.status:
        return

    proposal = instance.proposal
    recipient = proposal.created_by.user
    if not recipient:
        return

    manager_name = instance.employee.fullname

    if instance.status == ProposalVerifierStatus.VERIFIED:
        # Confirmed by Manager
        if proposal.proposal_type == ProposalType.TIMESHEET_ENTRY_COMPLAINT:
            message = _("Your timekeeping complaint has been confirmed by %(manager_name)s.") % {
                "manager_name": manager_name
            }
        else:
            proposal_type_display = proposal.get_proposal_type_display()
            message = _("Your %(proposal_type)s proposal has been confirmed by %(manager_name)s.") % {
                "proposal_type": proposal_type_display,
                "manager_name": manager_name,
            }

        create_notification(
            actor=instance.employee.user if instance.employee.user else recipient,
            recipient=recipient,
            verb="confirmed",
            target=proposal,
            message=message,
            target_client=UserDevice.Client.MOBILE,
        )

    elif instance.status == ProposalVerifierStatus.NOT_VERIFIED:
        note = instance.note or ""

        if proposal.proposal_type == ProposalType.TIMESHEET_ENTRY_COMPLAINT:
            message = _('Your timekeeping complaint was rejected by %(manager_name)s with note: "%(note)s"..') % {
                "manager_name": manager_name,
                "note": note,
            }
        else:
            proposal_type_display = proposal.get_proposal_type_display()
            message = _('Your %(proposal_type)s proposal was rejected by %(manager_name)s with note: "%(note)s"..') % {
                "proposal_type": proposal_type_display,
                "manager_name": manager_name,
                "note": note,
            }

        create_notification(
            actor=instance.employee.user if instance.employee.user else recipient,
            recipient=recipient,
            verb="rejected",
            target=proposal,
            message=message,
            target_client=UserDevice.Client.MOBILE,
        )
