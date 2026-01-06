"""Signal handlers for dashboard cache invalidation.

Handles cache invalidation when relevant models are modified.
"""

import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.hrm.constants import AttendanceType
from apps.hrm.models import AttendanceRecord, Proposal, ProposalVerifier
from apps.hrm.utils.dashboard_cache import (
    invalidate_hrm_dashboard_cache,
    invalidate_manager_dashboard_cache,
)

__all__ = [
    "invalidate_hrm_cache_on_proposal_change",
    "invalidate_hrm_cache_on_attendance_record_change",
    "invalidate_manager_cache_on_proposal_verifier_change",
]

logger = logging.getLogger(__name__)


# HRM Dashboard cache invalidation signals


@receiver(post_save, sender=Proposal)
def invalidate_hrm_cache_on_proposal_save(sender, instance, created, **kwargs):
    """Invalidate HRM dashboard cache when a Proposal is created or updated."""
    action = "created" if created else "updated"
    logger.debug("Proposal %s %s, invalidating HRM dashboard cache", instance.id, action)
    invalidate_hrm_dashboard_cache()


@receiver(post_delete, sender=Proposal)
def invalidate_hrm_cache_on_proposal_delete(sender, instance, **kwargs):
    """Invalidate HRM dashboard cache when a Proposal is deleted."""
    logger.debug("Proposal %s deleted, invalidating HRM dashboard cache", instance.id)
    invalidate_hrm_dashboard_cache()


def invalidate_hrm_cache_on_proposal_change():
    """Explicit function to invalidate HRM cache for proposal changes."""
    invalidate_hrm_dashboard_cache()


@receiver(post_save, sender=AttendanceRecord)
def invalidate_hrm_cache_on_attendance_record_save(sender, instance, created, **kwargs):
    """Invalidate HRM dashboard cache when an AttendanceRecord (type=OTHER) is modified."""
    if instance.attendance_type == AttendanceType.OTHER:
        action = "created" if created else "updated"
        logger.debug(
            "AttendanceRecord %s (type=OTHER) %s, invalidating HRM dashboard cache",
            instance.id,
            action,
        )
        invalidate_hrm_dashboard_cache()


@receiver(post_delete, sender=AttendanceRecord)
def invalidate_hrm_cache_on_attendance_record_delete(sender, instance, **kwargs):
    """Invalidate HRM dashboard cache when an AttendanceRecord (type=OTHER) is deleted."""
    if instance.attendance_type == AttendanceType.OTHER:
        logger.debug(
            "AttendanceRecord %s (type=OTHER) deleted, invalidating HRM dashboard cache",
            instance.id,
        )
        invalidate_hrm_dashboard_cache()


def invalidate_hrm_cache_on_attendance_record_change():
    """Explicit function to invalidate HRM cache for attendance record changes."""
    invalidate_hrm_dashboard_cache()


# Manager Dashboard cache invalidation signals


@receiver(post_save, sender=ProposalVerifier)
def invalidate_manager_cache_on_proposal_verifier_save(sender, instance, created, **kwargs):
    """Invalidate manager dashboard cache when a ProposalVerifier is created or updated."""
    if instance.employee_id:
        action = "created" if created else "updated"
        logger.debug(
            "ProposalVerifier %s %s, invalidating manager dashboard cache for employee %s",
            instance.id,
            action,
            instance.employee_id,
        )
        invalidate_manager_dashboard_cache(instance.employee_id)


@receiver(post_delete, sender=ProposalVerifier)
def invalidate_manager_cache_on_proposal_verifier_delete(sender, instance, **kwargs):
    """Invalidate manager dashboard cache when a ProposalVerifier is deleted."""
    if instance.employee_id:
        logger.debug(
            "ProposalVerifier %s deleted, invalidating manager dashboard cache for employee %s",
            instance.id,
            instance.employee_id,
        )
        invalidate_manager_dashboard_cache(instance.employee_id)


def invalidate_manager_cache_on_proposal_verifier_change(employee_id: int):
    """Explicit function to invalidate manager cache for proposal verifier changes."""
    invalidate_manager_dashboard_cache(employee_id)
