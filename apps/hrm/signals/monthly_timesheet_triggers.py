from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.hrm.models import EmployeeMonthlyTimesheet, TimeSheetEntry


@receiver(post_save, sender=TimeSheetEntry)
def trigger_monthly_refresh(sender, instance, **kwargs):
    """Mark monthly timesheet for refresh when a daily entry is updated.

    This ensures that any change to a daily timesheet (working_days, hours, status, etc.)
    is reflected in the aggregated monthly report.
    """
    date_obj = instance.date
    month_key = f"{date_obj.year:04d}{date_obj.month:02d}"
    report_date = date_obj.replace(day=1)

    # Efficiently mark for refresh
    updated = EmployeeMonthlyTimesheet.objects.filter(employee_id=instance.employee_id, month_key=month_key).update(
        need_refresh=True
    )

    # If not found, create and mark (though usually the periodic task handles creation,
    # it's safe to create here if missing)
    if updated == 0:
        EmployeeMonthlyTimesheet.objects.get_or_create(
            employee_id=instance.employee_id,
            month_key=month_key,
            defaults={"report_date": report_date, "need_refresh": True},
        )
