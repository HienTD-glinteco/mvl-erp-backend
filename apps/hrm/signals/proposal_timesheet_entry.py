from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.hrm.models import Proposal
from apps.hrm.models.timesheet import TimeSheetEntry
from apps.hrm.tasks.timesheets import (
    link_proposals_to_timesheet_entry_task,
    link_timesheet_entries_to_proposal_task,
)


@receiver(post_save, sender=TimeSheetEntry)
def trigger_link_proposals_to_timesheet_entry(sender, instance, created, **kwargs):
    """Trigger background task to link proposals when a new TimeSheetEntry is created."""
    if created:
        transaction.on_commit(lambda: link_proposals_to_timesheet_entry_task.delay(instance.id))


@receiver(post_save, sender=Proposal)
def trigger_link_timesheet_entries_to_proposal_save(sender, instance, created, **kwargs):
    """Trigger background task to link timesheets when a Proposal is created or updated."""
    # We trigger on both create and update because dates might change, requiring re-sync.
    transaction.on_commit(lambda: link_timesheet_entries_to_proposal_task.delay(instance.id))
