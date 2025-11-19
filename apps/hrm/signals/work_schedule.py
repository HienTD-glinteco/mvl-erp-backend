"""Signal handlers for WorkSchedule model.

Handles cache invalidation when WorkSchedule records are modified.
"""

import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.hrm.models import WorkSchedule
from apps.hrm.utils.work_schedule_cache import invalidate_work_schedule_cache

logger = logging.getLogger(__name__)


@receiver(post_save, sender=WorkSchedule)
def invalidate_cache_on_work_schedule_save(sender, instance, created, **kwargs):
    """Invalidate work schedule cache when a WorkSchedule is created or updated."""
    action = "created" if created else "updated"
    logger.info("WorkSchedule %s (weekday=%s) %s, invalidating cache", instance.id, instance.weekday, action)
    invalidate_work_schedule_cache()


@receiver(post_delete, sender=WorkSchedule)
def invalidate_cache_on_work_schedule_delete(sender, instance, **kwargs):
    """Invalidate work schedule cache when a WorkSchedule is deleted."""
    logger.info("WorkSchedule %s (weekday=%s) deleted, invalidating cache", instance.id, instance.weekday)
    invalidate_work_schedule_cache()
