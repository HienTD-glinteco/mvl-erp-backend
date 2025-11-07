"""Data scope filtering utilities for position-based access control."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from django.contrib.auth import get_user_model
from django.db.models import Q, QuerySet

from apps.hrm.constants import DataScope

if TYPE_CHECKING:
    from apps.core.models import User as UserType
else:
    UserType = Any

User = get_user_model()
logger = logging.getLogger(__name__)


@dataclass
class AllowedUnits:
    """Container for allowed organizational units based on data scope"""

    has_all: bool = False
    branches: set[int] = None  # type: ignore[assignment]
    blocks: set[int] = None  # type: ignore[assignment]
    departments: set[int] = None  # type: ignore[assignment]
    employees: set[int] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        """Initialize empty sets if None"""
        if self.branches is None:
            self.branches = set()
        if self.blocks is None:
            self.blocks = set()
        if self.departments is None:
            self.departments = set()
        if self.employees is None:
            self.employees = set()


def collect_allowed_units(user: UserType) -> AllowedUnits:  # noqa: C901
    """
    Collect allowed organizational units based on user's employee position and data scope.

    Args:
        user: The authenticated user

    Returns:
        AllowedUnits: Container with allowed branches, blocks, departments, and employees
    """
    if user.is_superuser:
        return AllowedUnits(has_all=True)

    allowed = AllowedUnits()

    # Get employee record for the user
    if not hasattr(user, "employee") or not user.employee:
        logger.warning("User %s has no employee record - returning empty units", user.id)
        return allowed

    employee = user.employee
    position = employee.position

    # User must have a position to access data
    if not position:
        logger.warning("User %s has no position assigned - returning empty units", user.id)
        return allowed

    data_scope = position.data_scope

    # If position has 'all' scope, grant full access
    if data_scope == DataScope.ALL:
        allowed.has_all = True
        logger.debug(
            "User %s has position %s with 'all' data scope - granting full access",
            user.id,
            position.id,
        )
        return allowed

    # Get organizational units from employee
    employee_branch = employee.branch
    employee_block = employee.block
    employee_department = employee.department

    # Apply data scope to collect allowed units
    if data_scope == DataScope.BRANCH and employee_branch:
        allowed.branches.add(employee_branch.id)
        logger.debug(
            "User %s position %s: branch scope, added branch %s",
            user.id,
            position.id,
            employee_branch.id,
        )

    elif data_scope == DataScope.BLOCK and employee_block:
        allowed.blocks.add(employee_block.id)
        logger.debug(
            "User %s position %s: block scope, added block %s",
            user.id,
            position.id,
            employee_block.id,
        )

    elif data_scope == DataScope.DEPARTMENT and employee_department:
        allowed.departments.add(employee_department.id)
        logger.debug(
            "User %s position %s: department scope, added department %s",
            user.id,
            position.id,
            employee_department.id,
        )

    elif data_scope == DataScope.SELF:
        allowed.employees.add(user.id)
        logger.debug(
            "User %s position %s: self scope, added employee %s",
            user.id,
            position.id,
            user.id,
        )

    logger.info(
        "User %s allowed units: branches=%d, blocks=%d, departments=%d, employees=%d",
        user.id,
        len(allowed.branches),
        len(allowed.blocks),
        len(allowed.departments),
        len(allowed.employees),
    )

    return allowed


def filter_queryset_by_data_scope(  # noqa: C901
    queryset: QuerySet, user: UserType, org_field: str = "department"
) -> QuerySet:
    """
    Filter a queryset based on user's position data scopes.

    Args:
        queryset: The queryset to filter
        user: The authenticated user
        org_field: The field name linking the model to organizational units.
                   Examples: "department", "employee__department", "department__block"

    Returns:
        QuerySet: Filtered queryset based on allowed data scope

    Raises:
        ValueError: If org_field is invalid or cannot be resolved
    """
    if user.is_superuser:
        logger.debug("User %s is superuser - no filtering applied", user.id)
        return queryset

    allowed = collect_allowed_units(user)

    if allowed.has_all:
        logger.debug("User %s has 'all' data scope - no filtering applied", user.id)
        return queryset

    # If user has no allowed units, return empty queryset
    if not any([allowed.branches, allowed.blocks, allowed.departments, allowed.employees]):
        logger.warning("User %s has no allowed units - returning empty queryset", user.id)
        return queryset.none()

    # Build filter query
    q_filter = Q()

    # Add branch filter - try all possible paths and combine with OR
    if allowed.branches:
        branch_q = Q()
        # Path 1: through department -> block -> branch (for records with department)
        try:
            test_q = Q(**{f"{org_field}__block__branch__in": allowed.branches})
            # Test if this field path is valid by attempting to build it
            queryset.filter(test_q).query  # noqa: B018
            branch_q |= test_q
        except Exception as e:  # noqa: S110
            logger.debug(f"Branch filter path not valid for {org_field}: {e}")
        # Path 2: direct branch on the related model (for branch-level assignments)
        # Remove the last part of org_field (e.g., "department") and add "branch"
        if "__" in org_field:
            try:
                base_field = org_field.rsplit("__", 1)[0]
                test_q = Q(**{f"{base_field}__branch__in": allowed.branches})
                queryset.filter(test_q).query  # noqa: B018
                branch_q |= test_q
            except Exception as e:  # noqa: S110
                logger.debug(f"Branch filter path not valid for {base_field}: {e}")
        # Path 3: direct branch field on the model (for OrganizationChart, etc.)
        try:
            test_q = Q(**{"branch__in": allowed.branches})
            queryset.filter(test_q).query  # noqa: B018
            branch_q |= test_q
        except Exception as e:  # noqa: S110
            logger.debug(f"Direct branch filter not valid: {e}")

        if branch_q:
            q_filter |= branch_q

    # Add block filter - try all possible paths and combine with OR
    if allowed.blocks:
        block_q = Q()
        # Path 1: through org_field -> block
        try:
            test_q = Q(**{f"{org_field}__block__in": allowed.blocks})
            queryset.filter(test_q).query  # noqa: B018
            block_q |= test_q
        except Exception as e:  # noqa: S110
            logger.debug(f"Block filter path not valid for {org_field}: {e}")
        # Path 2: direct block relationship
        if "__" in org_field:
            try:
                base_field = org_field.rsplit("__", 1)[0]
                test_q = Q(**{f"{base_field}__block__in": allowed.blocks})
                queryset.filter(test_q).query  # noqa: B018
                block_q |= test_q
            except Exception as e:  # noqa: S110
                logger.debug(f"Block filter path not valid for {base_field}: {e}")
        # Path 3: direct block field on the model
        try:
            test_q = Q(**{"block__in": allowed.blocks})
            queryset.filter(test_q).query  # noqa: B018
            block_q |= test_q
        except Exception as e:  # noqa: S110
            logger.debug(f"Direct block filter not valid: {e}")

        if block_q:
            q_filter |= block_q

    # Add department filter
    if allowed.departments:
        department_q = Q()
        try:
            test_q = Q(**{f"{org_field}__in": allowed.departments})
            queryset.filter(test_q).query  # noqa: B018
            department_q |= test_q
        except Exception as e:  # noqa: S110
            logger.debug(f"Department filter path not valid for {org_field}: {e}")
        try:
            test_q = Q(**{f"{org_field}__id__in": allowed.departments})
            queryset.filter(test_q).query  # noqa: B018
            department_q |= test_q
        except Exception as e:  # noqa: S110
            logger.debug(f"Department filter path not valid for {org_field}__id: {e}")
        try:
            test_q = Q(**{"department__in": allowed.departments})
            queryset.filter(test_q).query  # noqa: B018
            department_q |= test_q
        except Exception as e:  # noqa: S110
            logger.debug(f"Direct department filter not valid: {e}")
        try:
            test_q = Q(**{"department__id__in": allowed.departments})
            queryset.filter(test_q).query  # noqa: B018
            department_q |= test_q
        except Exception as e:  # noqa: S110
            logger.debug(f"Direct department__id filter not valid: {e}")

        if department_q:
            q_filter |= department_q

    # Add employee filter (for self scope)
    if allowed.employees:
        employee_q = Q()
        try:
            test_q = Q(**{"employee__in": allowed.employees})
            queryset.filter(test_q).query  # noqa: B018
            employee_q |= test_q
        except Exception as e:  # noqa: S110
            logger.debug(f"Employee filter not valid: {e}")
        try:
            test_q = Q(**{"employee__id__in": allowed.employees})
            queryset.filter(test_q).query  # noqa: B018
            employee_q |= test_q
        except Exception as e:  # noqa: S110
            logger.debug(f"Employee__id filter not valid: {e}")
        try:
            test_q = Q(**{"id__in": allowed.employees})  # If the model itself is User
            queryset.filter(test_q).query  # noqa: B018
            employee_q |= test_q
        except Exception as e:  # noqa: S110
            logger.debug(f"ID filter not valid: {e}")

        if employee_q:
            q_filter |= employee_q

    if not q_filter:
        logger.error("Failed to build filter for org_field=%s - returning empty queryset", org_field)
        return queryset.none()

    filtered_qs = queryset.filter(q_filter).distinct()
    logger.debug(
        "Filtered queryset for user %s with org_field=%s: %d results",
        user.id,
        org_field,
        filtered_qs.count() if filtered_qs._result_cache is None else len(filtered_qs),
    )

    return filtered_qs


def filter_by_leadership(queryset: QuerySet, leadership_only: bool = True) -> QuerySet:
    """
    Filter queryset to include only employees with leadership positions.

    This should be applied AFTER data scope filtering.

    Args:
        queryset: The queryset to filter (typically Employee or User queryset)
        leadership_only: If True, filter to leadership only. If False, no filtering.

    Returns:
        QuerySet: Filtered queryset
    """
    if not leadership_only:
        return queryset

    # Filter for employees who have a leadership position
    return queryset.filter(
        employee__position__is_leadership=True,
    ).distinct()
