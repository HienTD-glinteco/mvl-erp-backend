"""Data scope filtering utilities for position-based access control."""

import logging
from dataclasses import dataclass
from typing import Optional

from django.contrib.auth import get_user_model
from django.db.models import Q, QuerySet

from apps.hrm.constants import DataScope

User = get_user_model()
logger = logging.getLogger(__name__)


@dataclass
class AllowedUnits:
    """Container for allowed organizational units based on data scope"""

    has_all: bool = False
    branches: set = None
    blocks: set = None
    departments: set = None
    employees: set = None

    def __post_init__(self):
        """Initialize empty sets if None"""
        if self.branches is None:
            self.branches = set()
        if self.blocks is None:
            self.blocks = set()
        if self.departments is None:
            self.departments = set()
        if self.employees is None:
            self.employees = set()


def collect_allowed_units(user: User) -> AllowedUnits:
    """
    Collect allowed organizational units based on user's positions and their data scopes.

    Args:
        user: The authenticated user

    Returns:
        AllowedUnits: Container with allowed branches, blocks, departments, and employees
    """
    if user.is_superuser:
        return AllowedUnits(has_all=True)

    allowed = AllowedUnits()

    # Get all active assignments for the user
    assignments = user.organization_positions.filter(
        is_active=True, end_date__isnull=True
    ).select_related("position", "department__block__branch", "block__branch", "branch")

    for assignment in assignments:
        position = assignment.position
        data_scope = position.data_scope

        # If any position has 'all' scope, grant full access
        if data_scope == DataScope.ALL:
            allowed.has_all = True
            logger.debug(
                "User %s has position %s with 'all' data scope - granting full access",
                user.id,
                position.id,
            )
            return allowed

        # Determine the organizational unit from the assignment
        # Priority: branch > block > department
        assignment_branch = assignment.branch
        assignment_block = assignment.block
        assignment_department = assignment.department

        # Auto-derive missing units from available ones
        if assignment_department and not assignment_block:
            assignment_block = assignment_department.block
        if assignment_department and not assignment_branch:
            assignment_branch = assignment_department.block.branch
        if assignment_block and not assignment_branch:
            assignment_branch = assignment_block.branch

        # Apply data scope to collect allowed units
        if data_scope == DataScope.BRANCH and assignment_branch:
            allowed.branches.add(assignment_branch.id)
            logger.debug(
                "User %s position %s: branch scope, added branch %s",
                user.id,
                position.id,
                assignment_branch.id,
            )

        elif data_scope == DataScope.BLOCK and assignment_block:
            allowed.blocks.add(assignment_block.id)
            logger.debug(
                "User %s position %s: block scope, added block %s",
                user.id,
                position.id,
                assignment_block.id,
            )

        elif data_scope == DataScope.DEPARTMENT and assignment_department:
            allowed.departments.add(assignment_department.id)
            logger.debug(
                "User %s position %s: department scope, added department %s",
                user.id,
                position.id,
                assignment_department.id,
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


def filter_queryset_by_data_scope(
    queryset: QuerySet, user: User, org_field: str = "department"
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

    # Add branch filter
    if allowed.branches:
        # Try multiple field patterns
        branch_fields = [
            f"{org_field}__block__branch__in",
            f"{org_field}__branch__in",
            "branch__in",
        ]
        for field in branch_fields:
            try:
                q_filter |= Q(**{field: allowed.branches})
                break
            except Exception:
                continue

    # Add block filter
    if allowed.blocks:
        block_fields = [
            f"{org_field}__block__in",
            "block__in",
        ]
        for field in block_fields:
            try:
                q_filter |= Q(**{field: allowed.blocks})
                break
            except Exception:
                continue

    # Add department filter
    if allowed.departments:
        department_fields = [
            f"{org_field}__in",
            f"{org_field}__id__in",
            "department__in",
            "department__id__in",
        ]
        for field in department_fields:
            try:
                q_filter |= Q(**{field: allowed.departments})
                break
            except Exception:
                continue

    # Add employee filter (for self scope)
    if allowed.employees:
        employee_fields = [
            "employee__in",
            "employee__id__in",
            "id__in",  # If the model itself is User
        ]
        for field in employee_fields:
            try:
                q_filter |= Q(**{field: allowed.employees})
                break
            except Exception:
                continue

    if not q_filter:
        logger.error(
            "Failed to build filter for org_field=%s - returning empty queryset", org_field
        )
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

    # Filter for employees who have at least one active leadership position
    return queryset.filter(
        organization_positions__position__is_leadership=True,
        organization_positions__is_active=True,
        organization_positions__end_date__isnull=True,
    ).distinct()
