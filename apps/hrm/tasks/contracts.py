"""Celery tasks for HRM contract management."""

import logging

from celery import shared_task

from apps.hrm.models import Contract

logger = logging.getLogger(__name__)


@shared_task
def check_contract_status() -> dict[str, int]:
    """Update contract statuses based on effective and expiration dates.

    This task updates the status field of all Contract records
    based on their effective_date and expiration_date values according to these rules:

    - If status is DRAFT: Keep DRAFT (preserved)
    - If effective_date > today: NOT_EFFECTIVE
    - If expiration_date is None (indefinite): ACTIVE
    - If expiration_date < today: EXPIRED
    - If days until expiration <= 30: ABOUT_TO_EXPIRE
    - Otherwise: ACTIVE

    The task is designed to run daily to automatically transition contracts
    from ACTIVE → ABOUT_TO_EXPIRE → EXPIRED.

    Returns:
        dict: Summary with keys:
            - total_contracts: int total number of contracts processed
            - updated_count: int number of contracts updated
            - active_count: int number changed to ACTIVE
            - about_to_expire_count: int number changed to ABOUT_TO_EXPIRE
            - expired_count: int number changed to EXPIRED
            - not_effective_count: int number changed to NOT_EFFECTIVE
    """
    logger.info("Starting contract status update task")

    # Get all contracts except DRAFT status (DRAFT is preserved and not auto-updated)
    contracts = Contract.objects.exclude(status=Contract.ContractStatus.DRAFT)
    total_count = contracts.count()

    logger.info("Processing %d contracts", total_count)

    updated_count = 0
    status_changes: dict[str, int] = {
        "active": 0,
        "about_to_expire": 0,
        "expired": 0,
        "not_effective": 0,
    }

    for contract in contracts:
        old_status = contract.status
        new_status = contract.calculate_status()

        if old_status != new_status:
            updated_count += 1
            status_changes[new_status] += 1

            logger.debug(
                "Contract %s (%s): %s -> %s",
                contract.id,
                contract.code,
                old_status,
                new_status,
            )

            contract.status = new_status
            # Skip validation and signals by using update_fields
            contract.save(update_fields=["status", "updated_at"])

    logger.info(
        "Contract status update complete: %d contracts updated out of %d",
        updated_count,
        total_count,
    )
    logger.info(
        "Status changes - ACTIVE: %d, ABOUT_TO_EXPIRE: %d, EXPIRED: %d, NOT_EFFECTIVE: %d",
        status_changes["active"],
        status_changes["about_to_expire"],
        status_changes["expired"],
        status_changes["not_effective"],
    )

    return {
        "total_contracts": total_count,
        "updated_count": updated_count,
        "active_count": status_changes["active"],
        "about_to_expire_count": status_changes["about_to_expire"],
        "expired_count": status_changes["expired"],
        "not_effective_count": status_changes["not_effective"],
    }
