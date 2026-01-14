"""Celery tasks for HRM contract management."""

import logging
from collections import defaultdict

from celery import shared_task
from django.utils import timezone

from apps.hrm.models import Contract

logger = logging.getLogger(__name__)


@shared_task
def check_contract_status() -> dict[str, int]:
    """Update contract statuses based on effective and expiration dates.

    This task processes contracts per employee:
    1. For each employee, identify the most recent contract (by effective_date, then created_at)
    2. Update only the most recent contract's status based on date rules:
       - If status is DRAFT: Keep DRAFT (preserved)
       - If effective_date > today: NOT_EFFECTIVE
       - If expiration_date is None (indefinite): ACTIVE
       - If expiration_date < today: EXPIRED
       - If days until expiration <= 30: ABOUT_TO_EXPIRE
       - Otherwise: ACTIVE
    3. Mark all older contracts for the same employee as EXPIRED

    This ensures only one contract per employee can be ACTIVE/ABOUT_TO_EXPIRE at a time.

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
    # Order by employee_id and -id (largest id = most recent contract)
    contracts = Contract.objects.exclude(status=Contract.ContractStatus.DRAFT).order_by("employee_id", "-id")
    total_count = contracts.count()

    logger.info("Processing %d contracts", total_count)

    status_changes: dict[str, int] = {
        "active": 0,
        "about_to_expire": 0,
        "expired": 0,
        "not_effective": 0,
    }

    # Group contracts by employee
    contracts_by_employee: dict[int, list[Contract]] = defaultdict(list)
    for contract in contracts:
        contracts_by_employee[contract.employee_id].append(contract)

    # Process each employee's contracts
    contracts_to_save: list[Contract] = []
    contracts_to_force_update: list[Contract] = []
    now = timezone.now()

    for employee_id, employee_contracts in contracts_by_employee.items():
        # employee_contracts is already sorted by -effective_date, -created_at
        # First contract is the most recent one
        for idx, contract in enumerate(employee_contracts):
            old_status = contract.status

            if idx == 0:
                # Most recent contract: calculate status from dates
                new_status = contract.calculate_status()
                # For most recent contract, we want to use save() to trigger signals and logic
                target_list = contracts_to_save
            else:
                # Older contracts: always expire them
                new_status = Contract.ContractStatus.EXPIRED
                # For older contracts, we MUST use update/bulk_update to bypass correct status calculation
                # because save() would reset status to ACTIVE if dates are still valid.
                target_list = contracts_to_force_update

            if old_status != new_status:
                status_changes[new_status] += 1

                logger.debug(
                    "Contract %s (%s): %s -> %s%s",
                    contract.id,
                    contract.code,
                    old_status,
                    new_status,
                    "" if idx == 0 else " (older contract expired)",
                )

                contract.status = new_status
                contract.updated_at = now
                target_list.append(contract)

    # Process save list (triggers signals and internal logic like expire_previous_contracts)
    saved_count = len(contracts_to_save)
    if contracts_to_save:
        for contract in contracts_to_save:
            contract.save(update_fields=["status", "updated_at"])
        logger.info("Updated (saved) %d active/recent contracts", saved_count)

    # Process force update list (bypasses save logic to force expire)
    force_updated_count = len(contracts_to_force_update)
    if contracts_to_force_update:
        Contract.objects.bulk_update(contracts_to_force_update, ["status", "updated_at"])
        logger.info("Force updated (expired) %d older contracts", force_updated_count)

    updated_count = saved_count + force_updated_count

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
