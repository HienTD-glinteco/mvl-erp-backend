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
                "employee_id": old_instance.employee.id,
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
            "employee_id": instance.employee.id,
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
            "employee_id": instance.employee.id,
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
        # "report_date": report_date, # StaffGrowthReport no longer uses report_date for uniqueness or as a primary filter
        "branch_id": branch_id,
    }
    if block_id:
        filter_criteria["block_id"] = block_id
    if department_id:
        filter_criteria["department_id"] = department_id

    # Since StaffGrowthReport changed structure, marking it for refresh via report_date is tricky
    # because it is now aggregated by Week/Month.
    # However, BaseReportModel still has need_refresh.
    # But filtering by report_date=report_date might miss if the record stores report_date as start of week/month or something else.
    # The new `StaffGrowthReport` logic doesn't strictly rely on `report_date` field for business logic,
    # but uses `timeframe_key`.
    # And `_record_staff_growth_event` sets `report_date` to `event_date`.
    # So actually `report_date` on `StaffGrowthReport` will be the date of the FIRST event that created the report.
    # Or updated via `defaults`.

    # If we want to mark it for refresh, we'd need to find the report for the timeframe of `report_date`.
    # But since we are moving away from batch aggregation for StaffGrowthReport (using direct event logging),
    # maybe `need_refresh` is less relevant for `StaffGrowthReport`?
    # The plan says "No aggregation at API level - data has pre-calculated correct".
    # And "Data Rebuild Strategy" is a script.

    # So I will keep marking other reports, but maybe for `StaffGrowthReport` it's not as critical
    # OR I should try to find the relevant reports.

    # For now, I'll comment out StaffGrowthReport marking or leave it as best effort.
    # But `StaffGrowthReport` model has changed, so `filter_criteria` with `report_date` might not match anything
    # if `report_date` in DB is different from `instance.date`.
    # Actually, `_record_staff_growth_event` sets `report_date=event_date` on creation.
    # So if multiple events happen on different dates in the same month, `report_date` will be the date of the first event.
    # So filtering by `report_date` won't work reliably to find the monthly report.

    # I will skip marking `StaffGrowthReport` for refresh here as the new architecture relies on real-time event logging.
    # StaffGrowthReport.objects.filter(**filter_criteria).update(need_refresh=True)

    # Mark EmployeeStatusBreakdownReport records (still daily)
    # Re-add report_date to filter for these models
    filter_criteria["report_date"] = report_date

    EmployeeStatusBreakdownReport.objects.filter(**filter_criteria).update(need_refresh=True)

    # Mark EmployeeResignedReasonReport records (still daily)
    EmployeeResignedReasonReport.objects.filter(**filter_criteria).update(need_refresh=True)
