"""Work schedule caching utilities.

This module provides caching functionality for WorkSchedule data to improve performance.
Cache is invalidated whenever WorkSchedule records are modified.
"""

from django.core.cache import cache
from django.db.models import QuerySet

from apps.hrm.models import WorkSchedule

# Cache keys
WORK_SCHEDULE_CACHE_KEY = "work_schedule:all"
WORK_SCHEDULE_BY_WEEKDAY_KEY = "work_schedule:weekday:{weekday}"
WORK_SCHEDULE_CACHE_TIMEOUT = 60 * 60 * 24  # 24 hours


def get_all_work_schedules(use_cache: bool = True) -> QuerySet:
    """Get all work schedules, using cache if available.

    Args:
        use_cache: If True, use cached data. If False, query database directly.

    Returns:
        QuerySet of WorkSchedule objects.
    """
    if not use_cache:
        return WorkSchedule.objects.all()

    cached_schedules = cache.get(WORK_SCHEDULE_CACHE_KEY)
    if cached_schedules is not None:
        return cached_schedules

    schedules = list(WorkSchedule.objects.all())
    cache.set(WORK_SCHEDULE_CACHE_KEY, schedules, WORK_SCHEDULE_CACHE_TIMEOUT)
    return schedules


def get_work_schedule_by_weekday(weekday: int, use_cache: bool = True) -> WorkSchedule | None:
    """Get work schedule for a specific weekday, using cache if available.

    Args:
        weekday: Integer representing weekday (from WorkSchedule.Weekday choices).
        use_cache: If True, use cached data. If False, query database directly.

    Returns:
        WorkSchedule instance or None if not found.
    """
    if not use_cache:
        return WorkSchedule.objects.filter(weekday=weekday).first()

    cache_key = WORK_SCHEDULE_BY_WEEKDAY_KEY.format(weekday=weekday)
    cached_schedule = cache.get(cache_key)
    if cached_schedule is not None:
        return cached_schedule

    schedule = WorkSchedule.objects.filter(weekday=weekday).first()
    if schedule:
        cache.set(cache_key, schedule, WORK_SCHEDULE_CACHE_TIMEOUT)
    return schedule


def invalidate_work_schedule_cache():
    """Invalidate all work schedule caches.

    This should be called whenever WorkSchedule records are created, updated, or deleted.
    """
    # Clear the all schedules cache
    cache.delete(WORK_SCHEDULE_CACHE_KEY)

    # Clear individual weekday caches
    for weekday_choice in WorkSchedule.Weekday.values:
        cache_key = WORK_SCHEDULE_BY_WEEKDAY_KEY.format(weekday=weekday_choice)
        cache.delete(cache_key)
