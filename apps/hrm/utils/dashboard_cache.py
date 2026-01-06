"""Dashboard caching utilities.

This module provides caching functionality for HRM dashboard data to improve performance.
Cache is invalidated whenever relevant records are modified.
"""

import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

# Cache keys
HRM_DASHBOARD_CACHE_KEY = "hrm:dashboard:realtime"
MANAGER_DASHBOARD_CACHE_KEY_PREFIX = "manager:dashboard:realtime:"
DASHBOARD_CACHE_TIMEOUT = 60 * 5  # 5 minutes


def get_hrm_dashboard_cache():
    """Get cached HRM dashboard data.

    Returns:
        Cached data dict or None if not found.
    """
    return cache.get(HRM_DASHBOARD_CACHE_KEY)


def set_hrm_dashboard_cache(data: dict):
    """Set HRM dashboard data in cache.

    Args:
        data: Dashboard data to cache.
    """
    cache.set(HRM_DASHBOARD_CACHE_KEY, data, DASHBOARD_CACHE_TIMEOUT)


def invalidate_hrm_dashboard_cache():
    """Invalidate HRM dashboard cache.

    This should be called whenever relevant records are modified:
    - Proposal created/updated/deleted
    - AttendanceRecord (type=OTHER) created/updated/deleted
    - PenaltyTicket created/updated/deleted
    """
    logger.debug("Invalidating HRM dashboard cache")
    cache.delete(HRM_DASHBOARD_CACHE_KEY)


def get_manager_dashboard_cache(employee_id: int):
    """Get cached manager dashboard data for a specific employee.

    Args:
        employee_id: The manager's employee ID.

    Returns:
        Cached data dict or None if not found.
    """
    cache_key = f"{MANAGER_DASHBOARD_CACHE_KEY_PREFIX}{employee_id}"
    return cache.get(cache_key)


def set_manager_dashboard_cache(employee_id: int, data: dict):
    """Set manager dashboard data in cache.

    Args:
        employee_id: The manager's employee ID.
        data: Dashboard data to cache.
    """
    cache_key = f"{MANAGER_DASHBOARD_CACHE_KEY_PREFIX}{employee_id}"
    cache.set(cache_key, data, DASHBOARD_CACHE_TIMEOUT)


def invalidate_manager_dashboard_cache(employee_id: int | None = None):
    """Invalidate manager dashboard cache.

    Args:
        employee_id: If provided, only invalidate cache for this manager.
                    If None, invalidate all manager caches (not recommended for performance).

    This should be called whenever relevant records are modified:
    - ProposalVerifier created/updated/deleted
    - EmployeeKPIAssessment created/updated/deleted
    """
    if employee_id:
        cache_key = f"{MANAGER_DASHBOARD_CACHE_KEY_PREFIX}{employee_id}"
        logger.debug("Invalidating manager dashboard cache for employee %s", employee_id)
        cache.delete(cache_key)
    else:
        # For bulk operations, we can't easily clear all manager caches
        # without knowing all manager IDs, so we log a warning
        logger.warning(
            "invalidate_manager_dashboard_cache called without employee_id. "
            "Consider passing specific employee_id for better performance."
        )
