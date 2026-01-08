"""
Role Data Scope Utilities

This module provides utilities for role-based data scope filtering,
including caching and helper functions for determining allowed organizational units.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Q, QuerySet

from apps.core.models.role import DataScopeLevel

if TYPE_CHECKING:
    from apps.core.models import User as UserType
else:
    UserType = Any

User = get_user_model()
logger = logging.getLogger(__name__)

# Cache timeout for role allowed units (5 minutes)
ROLE_UNITS_CACHE_TIMEOUT = 300


@dataclass
class RoleAllowedUnits:
    """Container for allowed organizational units based on role data scope"""

    has_all: bool = False
    branches: set[int] = None  # type: ignore[assignment]
    blocks: set[int] = None  # type: ignore[assignment]
    departments: set[int] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.branches is None:
            self.branches = set()
        if self.blocks is None:
            self.blocks = set()
        if self.departments is None:
            self.departments = set()

    @property
    def is_empty(self) -> bool:
        """Check if no units are allowed"""
        return not self.has_all and not any([self.branches, self.blocks, self.departments])

    def to_cache_dict(self) -> dict:
        """Convert to a cacheable dictionary"""
        return {
            "has_all": self.has_all,
            "branches": list(self.branches),
            "blocks": list(self.blocks),
            "departments": list(self.departments),
        }

    @classmethod
    def from_cache_dict(cls, data: dict) -> "RoleAllowedUnits":
        """Create instance from cached dictionary"""
        return cls(
            has_all=data["has_all"],
            branches=set(data["branches"]),
            blocks=set(data["blocks"]),
            departments=set(data["departments"]),
        )


def get_role_units_cache_key(user_id: int) -> str:
    """Generate cache key for user's role allowed units"""
    return f"role_allowed_units:{user_id}"


def invalidate_role_units_cache(user_id: int) -> None:
    """Invalidate cache for a specific user's role units"""
    cache.delete(get_role_units_cache_key(user_id))


def invalidate_role_units_cache_for_role(role_id: int) -> None:
    """Invalidate cache for all users with a specific role"""
    from apps.core.models import User

    user_ids = User.objects.filter(role_id=role_id).values_list("id", flat=True)
    cache.delete_many([get_role_units_cache_key(uid) for uid in user_ids])


def collect_role_allowed_units(user: UserType, use_cache: bool = True) -> RoleAllowedUnits:
    """
    Collect allowed organizational units based on user's role data scope.

    Uses caching to improve performance. Cache is invalidated when:
    - Role scope assignments change (via signals)
    - User's role changes

    Args:
        user: The authenticated user
        use_cache: Whether to use caching (default: True)

    Returns:
        RoleAllowedUnits: Container with allowed units
    """
    # Import here to avoid circular import
    from apps.hrm.models import RoleBlockScope, RoleBranchScope, RoleDepartmentScope

    # Superuser gets all access (no caching needed)
    if user.is_superuser:
        return RoleAllowedUnits(has_all=True)

    # Try to get from cache
    if use_cache:
        cache_key = get_role_units_cache_key(user.id)
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            logger.debug("Cache hit for user %s role units", user.id)
            return RoleAllowedUnits.from_cache_dict(cached_data)

    allowed = RoleAllowedUnits()

    # Check if user has a role
    role = user.role
    if not role:
        logger.warning("User %s has no role - returning empty units", user.id)
        return allowed

    # Process based on data scope level
    scope_level = role.data_scope_level

    if scope_level == DataScopeLevel.ROOT:
        allowed.has_all = True
        logger.debug("Role %s has ROOT scope - granting full access", role.id)

    elif scope_level == DataScopeLevel.BRANCH:
        branch_ids = set(RoleBranchScope.objects.filter(role=role).values_list("branch_id", flat=True))
        allowed.branches = branch_ids
        logger.debug("Role %s has BRANCH scope: %s", role.id, branch_ids)

    elif scope_level == DataScopeLevel.BLOCK:
        block_ids = set(RoleBlockScope.objects.filter(role=role).values_list("block_id", flat=True))
        allowed.blocks = block_ids
        logger.debug("Role %s has BLOCK scope: %s", role.id, block_ids)

    elif scope_level == DataScopeLevel.DEPARTMENT:
        dept_ids = set(RoleDepartmentScope.objects.filter(role=role).values_list("department_id", flat=True))
        allowed.departments = dept_ids
        logger.debug("Role %s has DEPARTMENT scope: %s", role.id, dept_ids)

    # Cache the result
    if use_cache:
        cache.set(cache_key, allowed.to_cache_dict(), ROLE_UNITS_CACHE_TIMEOUT)
        logger.debug("Cached role units for user %s", user.id)

    return allowed


def filter_queryset_by_role_data_scope(
    queryset: QuerySet,
    user: UserType,
    config: dict | None = None,
) -> QuerySet:
    """
    Filter queryset based on user's role data scope.

    Args:
        queryset: The queryset to filter
        user: The authenticated user
        config: Dict with field mappings:
            - branch_field: Path to branch (e.g., "branch", "employee__branch")
            - block_field: Path to block
            - department_field: Path to department

    Returns:
        Filtered queryset
    """
    if user.is_superuser:
        return queryset

    allowed = collect_role_allowed_units(user)

    if allowed.has_all:
        return queryset

    if allowed.is_empty:
        logger.warning("User %s has no allowed units - returning empty queryset", user.id)
        return queryset.none()

    config = config or {}
    q_filter = _build_scope_filter(queryset, allowed, config)

    if not q_filter:
        return queryset.none()

    return queryset.filter(q_filter).distinct()


def _build_scope_filter(queryset: QuerySet, allowed, config: dict) -> Q:
    """Build the complete Q filter for data scope"""
    branch_field = config.get("branch_field", "branch")
    block_field = config.get("block_field", "block")
    department_field = config.get("department_field", "department")

    q_filter = Q()

    # Branch scope filters
    if allowed.branches:
        q_filter |= _build_field_filter(queryset, branch_field, allowed.branches)
        if block_field:
            q_filter |= _build_filter(queryset, f"{block_field}__branch_id__in", allowed.branches)
        if department_field:
            q_filter |= _build_filter(queryset, f"{department_field}__branch_id__in", allowed.branches)

    # Block scope filters
    if allowed.blocks:
        q_filter |= _build_field_filter(queryset, block_field, allowed.blocks)
        if department_field:
            q_filter |= _build_filter(queryset, f"{department_field}__block_id__in", allowed.blocks)

    # Department scope filters
    if allowed.departments:
        q_filter |= _build_field_filter(queryset, department_field, allowed.departments)

    return q_filter


def _build_field_filter(queryset: QuerySet, field_path: str, values: set) -> Q:
    """Build Q filter for a field, handling empty field paths (direct pk filter)"""
    if not field_path:
        # Direct filter on model's primary key
        return Q(pk__in=values)
    return _build_filter(queryset, f"{field_path}_id__in", values)


def _build_filter(queryset: QuerySet, field_path: str, values: set) -> Q:
    """Build Q filter, validating field path exists"""
    try:
        q = Q(**{field_path: values})
        # Validate path by building query
        _ = queryset.filter(q).query
        return q
    except Exception:
        return Q()
