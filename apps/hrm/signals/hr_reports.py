"""Signal handlers for HR reports aggregation."""

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.hrm.models import (
    EmployeeResignedReasonReport,
    EmployeeStatusBreakdownReport,
    EmployeeWorkHistory,
    StaffGrowthReport,
)
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
                "employee_code_type": old_instance.employee.code_type,
                "id": old_instance.pk,
                "employee_id": old_instance.employee_id,
            }
        except EmployeeWorkHistory.DoesNotExist:
            instance._old_snapshot = None
    else:
        instance._old_snapshot = None


@receiver(post_save, sender=EmployeeWorkHistory)
def trigger_hr_reports_aggregation_on_save(sender, instance, created, **kwargs):  # noqa: ARG001
    """Trigger HR reports aggregation when work history is created or updated.

    This signal:
    1. Fires a Celery task to incrementally update HR reports using snapshot data
    2. Marks affected report records with need_refresh=True for batch reconciliation
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
            "employee_code_type": instance.employee.code_type,
            "id": instance.pk,
            "employee_id": instance.employee_id,
        }

        # Mark affected reports for batch refresh
        _mark_hr_reports_for_refresh(
            report_date=instance.date,
            branch_id=instance.branch_id,
            block_id=instance.block_id,
            department_id=instance.department_id,
        )

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

    This signal:
    1. Fires a Celery task to decrementally update HR reports using snapshot data
    2. Marks affected report records with need_refresh=True for batch reconciliation
    """
    # Trigger incremental update for deletion
    if instance.date and instance.branch_id and instance.block_id and instance.department_id:
        # Mark affected reports for batch refresh
        _mark_hr_reports_for_refresh(
            report_date=instance.date,
            branch_id=instance.branch_id,
            block_id=instance.block_id,
            department_id=instance.department_id,
        )

        # Delete event: previous is deleted state, current is None
        previous_snapshot = {
            "date": instance.date,
            "name": instance.name,
            "branch_id": instance.branch_id,
            "block_id": instance.block_id,
            "department_id": instance.department_id,
            "status": instance.status,
            "previous_data": instance.previous_data,
            "employee_code_type": instance.employee.code_type,
            "id": instance.pk,
            "employee_id": instance.employee_id,
        }
        snapshot = {"previous": previous_snapshot, "current": None}
        aggregate_hr_reports_for_work_history.delay("delete", snapshot)


def _mark_hr_reports_for_refresh(report_date, branch_id, block_id, department_id):  # noqa: ANN001, ANN201
    """Mark affected HR report records with need_refresh=True.

    Only marks the specific report record matching the exact date and org unit,
    avoiding bulk updates of large date ranges.

    Args:
        report_date: The report date to mark
        branch_id: Branch ID
        block_id: Block ID (can be None)
        department_id: Department ID (can be None)
    """
    # Build filter criteria for exact org unit match
    filter_criteria = {
        "report_date": report_date,
        "branch_id": branch_id,
    }
    if block_id:
        filter_criteria["block_id"] = block_id
    if department_id:
        filter_criteria["department_id"] = department_id

    # Mark StaffGrowthReport records
    StaffGrowthReport.objects.filter(**filter_criteria).update(need_refresh=True)

    # Mark EmployeeStatusBreakdownReport records
    EmployeeStatusBreakdownReport.objects.filter(**filter_criteria).update(need_refresh=True)

    # Mark EmployeeResignedReasonReport records
    EmployeeResignedReasonReport.objects.filter(**filter_criteria).update(need_refresh=True)
