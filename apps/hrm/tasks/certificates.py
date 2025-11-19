"""Celery tasks for HRM certificate management."""

import logging

from celery import shared_task

from apps.hrm.models import EmployeeCertificate

logger = logging.getLogger(__name__)


@shared_task
def update_certificate_statuses() -> dict[str, int]:
    """Update certificate statuses based on expiry dates.

    This task updates the status field of all EmployeeCertificate records
    based on their expiry_date values according to these rules:

    - No expiry_date → VALID
    - Current date > expiry_date → EXPIRED
    - Current date ≤ expiry_date and diff ≤ threshold → NEAR_EXPIRY
    - Current date ≤ expiry_date and diff > threshold → VALID

    The threshold is configured via HRM_CERTIFICATE_NEAR_EXPIRY_DAYS setting (default: 30 days).

    Returns:
        dict: Summary with keys:
            - total_certificates: int total number of certificates processed
            - updated_count: int number of certificates updated
            - valid_count: int number changed to VALID
            - near_expiry_count: int number changed to NEAR_EXPIRY
            - expired_count: int number changed to EXPIRED
    """
    logger.info("Starting certificate status update task")

    # Get all certificates
    certificates = EmployeeCertificate.objects.all()
    total_count = certificates.count()

    logger.info(f"Processing {total_count} certificates")

    updated_count = 0
    status_changes = {"valid": 0, "near_expiry": 0, "expired": 0}

    for certificate in certificates:
        old_status = certificate.status
        new_status = certificate.compute_status()

        if old_status != new_status:
            updated_count += 1
            status_changes[new_status] += 1

            logger.debug(f"Certificate {certificate.id}: {old_status} -> {new_status}")

            certificate.status = new_status
            # Skip validation and signals by using update_fields
            certificate.save(update_fields=["status", "updated_at"])

    logger.info(f"Certificate status update complete: {updated_count} certificates updated out of {total_count}")
    logger.info(
        f"Status changes - VALID: {status_changes['valid']}, "
        f"NEAR_EXPIRY: {status_changes['near_expiry']}, "
        f"EXPIRED: {status_changes['expired']}"
    )

    return {
        "total_certificates": total_count,
        "updated_count": updated_count,
        "valid_count": status_changes["valid"],
        "near_expiry_count": status_changes["near_expiry"],
        "expired_count": status_changes["expired"],
    }
