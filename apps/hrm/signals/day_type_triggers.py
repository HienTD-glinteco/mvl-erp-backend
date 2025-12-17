from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.hrm.models.holiday import CompensatoryWorkday, Holiday
from apps.hrm.services.timesheets import update_day_types_for_range


@receiver(post_save, sender=Holiday)
@receiver(post_delete, sender=Holiday)
def handle_holiday_change(sender, instance, **kwargs):
    """Trigger day_type updates when a Holiday is created, updated, or deleted."""
    update_day_types_for_range(instance.start_date, instance.end_date)


@receiver(post_save, sender=CompensatoryWorkday)
@receiver(post_delete, sender=CompensatoryWorkday)
def handle_compensatory_workday_change(sender, instance, **kwargs):
    """Trigger day_type updates when a CompensatoryWorkday is created, updated, or deleted."""
    update_day_types_for_range(instance.date, instance.date)
