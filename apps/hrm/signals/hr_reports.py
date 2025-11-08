"""Signal handlers for HR reports aggregation."""

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.hrm.models import EmployeeWorkHistory
from apps.hrm.tasks import aggregate_hr_reports_for_work_history


@receiver(pre_save, sender=EmployeeWorkHistory)
def track_work_history_changes(sender, instance, **kwargs):  # noqa: ARG001
    """Track work history changes before save.

    Store the old state in a temporary attribute so we can create a snapshot
    in the post_save signal.
    """
    if instance.pk:
        try:
            old_instance = EmployeeWorkHistory.objects.get(pk=instance.pk)
            instance._old_snapshot = {
                "date": old_instance.date,
                "name": old_instance.name,
                "branch_id": old_instance.branch_id,
                "block_id": old_instance.block_id,
                "department_id": old_instance.department_id,
                "status": old_instance.status,
                "previous_data": old_instance.previous_data,
            }
        except EmployeeWorkHistory.DoesNotExist:
            instance._old_snapshot = None
    else:
        instance._old_snapshot = None


@receiver(post_save, sender=EmployeeWorkHistory)
def trigger_hr_reports_aggregation_on_save(sender, instance, created, **kwargs):  # noqa: ARG001
    """Trigger HR reports aggregation when work history is created or updated.

    This signal fires a Celery task to incrementally update HR reports
    using snapshot data to avoid race conditions.
    """
    # Only trigger if the work history has required organizational fields
    if instance.branch_id and instance.block_id and instance.department_id:
        # Create current snapshot
        current_snapshot = {
            "date": instance.date,
            "name": instance.name,
            "branch_id": instance.branch_id,
            "block_id": instance.block_id,
            "department_id": instance.department_id,
            "status": instance.status,
            "previous_data": instance.previous_data,
        }

        if created:
            # Create event: previous is None, current is new state
            snapshot = {"previous": None, "current": current_snapshot}
            aggregate_hr_reports_for_work_history.delay("create", snapshot)
        else:
            # Update event: previous is old state, current is new state
            previous_snapshot = getattr(instance, "_old_snapshot", None)
            snapshot = {"previous": previous_snapshot, "current": current_snapshot}
            aggregate_hr_reports_for_work_history.delay("update", snapshot)


@receiver(post_delete, sender=EmployeeWorkHistory)
def trigger_hr_reports_aggregation_on_delete(sender, instance, **kwargs):  # noqa: ARG001
    """Trigger HR reports aggregation when work history is deleted.

    This signal fires a Celery task to decrementally update HR reports
    using snapshot data.
    """
    # Trigger incremental update for deletion
    if instance.date and instance.branch_id and instance.block_id and instance.department_id:
        # Delete event: previous is deleted state, current is None
        previous_snapshot = {
            "date": instance.date,
            "name": instance.name,
            "branch_id": instance.branch_id,
            "block_id": instance.block_id,
            "department_id": instance.department_id,
            "status": instance.status,
            "previous_data": instance.previous_data,
        }
        snapshot = {"previous": previous_snapshot, "current": None}
        aggregate_hr_reports_for_work_history.delay("delete", snapshot)
