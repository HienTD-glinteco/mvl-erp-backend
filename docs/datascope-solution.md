# Data Scope Permission System - Software Requirements Specification (SRS)

## Document Information

| Item | Description |
|------|-------------|
| Version | 2.0 |
| Date | January 8, 2026 |
| Status | Draft |
| Project | MaiVietLand ERP Backend |

---

## 1. Executive Summary

### 1.1 Purpose

This document specifies the technical requirements for implementing **Role-Based Data Scope Permission** in the MaiVietLand ERP system. The goal is to extend the current role-based permission system to support fine-grained data access control at organizational unit levels (Branch, Block, Department).

### 1.2 Problem Statement

**Current State:**
- The system uses **Role-Based Permission** where each `Role` contains a set of `Permission` codes
- A `User` is assigned one `Role`, which determines their **actions** (list, create, update, delete, etc.)
- **No data scope filtering** - Roles cannot restrict which organizational data a user can access

**Gap/Tech Debt:**
- **Roles cannot restrict data scope** - A "Recruitment Manager for Quang Ninh" role grants recruitment permissions but **cannot limit data to only Quang Ninh branch**
- **No multi-unit support** - Cannot assign a role that spans multiple specific branches/blocks/departments

**Desired State:**
- Roles should define both **actions** (permissions) AND **data scope** (which organizational units)
- Example: "Recruitment Manager - Quang Ninh Branch" role should:
  - Have recruitment-related permissions (actions)
  - Only see data from Quang Ninh branch (data scope)
- Support for multiple organizational units per role (e.g., manage 2 branches)

### 1.3 Scope

This specification covers:
- Database schema changes for Role Data Scope
- API/Business logic for data scope filtering
- Migration strategy for existing data
- ViewSets that require data scope integration

---

## 2. Current System Analysis

### 2.1 Existing Permission Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CURRENT SYSTEM                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│    User (1) ──FK──> Role (N) ──M2M──> Permission (N)                │
│                                                                      │
│    • User.role: Single role per user                                │
│    • Role.permissions: Set of permission codes                      │
│    • Permission.code: e.g., "employee.list", "employee.create"     │
│                                                                      │
│    ⚠️ NO DATA SCOPE FILTERING - User sees ALL data                  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Key Models

#### 2.2.1 Role Model (`apps/core/models/role.py`)

```python
class Role(AutoCodeMixin, BaseModel):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=255, blank=True)
    is_system_role = models.BooleanField(default=False)
    is_default_role = models.BooleanField(default=False)
    permissions = models.ManyToManyField("Permission", related_name="roles", blank=True)
```

#### 2.2.2 User Model (`apps/core/models/user.py`)

```python
class User(BaseModel, AbstractBaseUser, PermissionsMixin):
    role = models.ForeignKey("Role", on_delete=models.SET_NULL, null=True, blank=True)

    def has_permission(self, permission_code: str) -> bool:
        if self.is_superuser:
            return True
        if self.role is None:
            return False
        return self.role.permissions.filter(code=permission_code).exists()
```

### 2.3 Organizational Hierarchy

```
Branch (Chi nhánh)
   └── Block (Khối)
         └── Department (Phòng ban)
               └── Employee (Nhân viên)
```

---

## 3. Proposed Solution

### 3.1 Solution Overview

**Extend the Role model** to include data scope configuration:
1. Add **data_scope_level** field to Role (ROOT/BRANCH/BLOCK/DEPARTMENT)
2. Create **intermediate M2M models in `hrm` app** for organizational unit assignments

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PROPOSED SYSTEM                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│    User (1) ──FK──> Role (N) ──M2M──> Permission (N)                │
│                       │                                              │
│                       ├── data_scope_level: "branch"                │
│                       │                                              │
│                       └──> RoleBranchScope ──> [Branch1, Branch2]   │
│                       └──> RoleBlockScope ──> [Block1, Block2]      │
│                       └──> RoleDepartmentScope ──> [Dept1, Dept2]   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 Data Scope Levels

| Level | Code | Description | Data Access |
|-------|------|-------------|-------------|
| Root | `root` | Full access to all data | All organizational units |
| Branch | `branch` | Access limited to specified branches | Only assigned branches + their blocks/departments |
| Block | `block` | Access limited to specified blocks | Only assigned blocks + their departments |
| Department | `department` | Access limited to specified departments | Only assigned departments |

### 3.3 Architecture: Intermediate Models in `hrm` App

**Problem:** Creating M2M relations from `Role` (in `core` app) to `Branch`, `Block`, `Department` (in `hrm` app) would cause:
- Circular dependency between apps
- Migration dependencies from `core` to `hrm`

**Solution:**
1. Add `data_scope_level` field directly to `Role` model in `core` app
2. Create **intermediate M2M models in `hrm` app** to store organizational unit assignments

```
┌──────────────────────────────────────────────────────────────────────┐
│                    APP DEPENDENCY STRUCTURE                          │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│    ┌─────────────────────┐        ┌──────────────────────────────┐  │
│    │      core app       │        │          hrm app              │  │
│    ├─────────────────────┤        ├──────────────────────────────┤  │
│    │                     │        │                               │  │
│    │  Role               │◄───────│  RoleBranchScope             │  │
│    │  • code             │  FK    │  • role_id (FK to core.Role) │  │
│    │  • name             │        │  • branch_id (FK)            │  │
│    │  • permissions      │        │                               │  │
│    │  • data_scope_level │        │  RoleBlockScope              │  │
│    │                     │        │  • role_id (FK)              │  │
│    │                     │        │  • block_id (FK)             │  │
│    │                     │        │                               │  │
│    │                     │        │  RoleDepartmentScope         │  │
│    │                     │        │  • role_id (FK)              │  │
│    │                     │        │  • department_id (FK)        │  │
│    │                     │        │                               │  │
│    └─────────────────────┘        └──────────────────────────────┘  │
│              ▲                                  │                     │
│              │                                  │                     │
│              └──────────────────────────────────┘                     │
│                 hrm app depends on core (OK!)                        │
│                 core app has NO dependency on hrm (OK!)              │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 4. Database Schema Design

### 4.1 Role Model Changes (`core` app)

Add `data_scope_level` field to existing Role model:

```python
# apps/core/models/role.py

class DataScopeLevel(models.TextChoices):
    """Data scope level for role-based access control"""
    ROOT = "root", _("Root - Full access")
    BRANCH = "branch", _("Branch level")
    BLOCK = "block", _("Block level")
    DEPARTMENT = "department", _("Department level")


@audit_logging_register
class Role(AutoCodeMixin, BaseModel):
    """Model representing a role that groups permissions"""

    CODE_PREFIX = "VT"
    TEMP_CODE_PREFIX = "TEMP_"

    code = models.CharField(max_length=50, unique=True, verbose_name="Role code")
    name = models.CharField(max_length=100, unique=True, verbose_name="Role name")
    description = models.CharField(max_length=255, blank=True, verbose_name="Description")
    is_system_role = models.BooleanField(default=False, verbose_name="System role")
    is_default_role = models.BooleanField(default=False, verbose_name="Default role")
    permissions = models.ManyToManyField(
        "Permission",
        related_name="roles",
        verbose_name="Permissions",
        blank=True,
    )

    # NEW FIELD: Data scope level
    data_scope_level = models.CharField(
        max_length=20,
        choices=DataScopeLevel.choices,
        default=DataScopeLevel.ROOT,  # Default is ROOT (full access)
        verbose_name="Data scope level",
        help_text="Determines the organizational level this role can access",
    )

    class Meta:
        verbose_name = "Role"
        verbose_name_plural = "Roles"
        db_table = "core_role"
        ordering = ["code"]
```

### 4.2 New Models in `hrm` App

```python
# apps/hrm/models/role_data_scope.py

from django.db import models
from django.utils.translation import gettext_lazy as _

from libs.models import BaseModel


class RoleBranchScope(BaseModel):
    """
    Links a Role to allowed Branches.
    Only applies when Role.data_scope_level = 'branch'
    """

    role = models.ForeignKey(
        "core.Role",
        on_delete=models.CASCADE,
        related_name="branch_scopes",
        verbose_name=_("Role"),
    )
    branch = models.ForeignKey(
        "hrm.Branch",
        on_delete=models.CASCADE,
        related_name="role_scopes",
        verbose_name=_("Branch"),
    )

    class Meta:
        verbose_name = _("Role Branch Scope")
        verbose_name_plural = _("Role Branch Scopes")
        db_table = "hrm_role_branch_scope"
        unique_together = [["role", "branch"]]

    def __str__(self):
        return f"{self.role.name} -> {self.branch.name}"


class RoleBlockScope(BaseModel):
    """
    Links a Role to allowed Blocks.
    Only applies when Role.data_scope_level = 'block'
    """

    role = models.ForeignKey(
        "core.Role",
        on_delete=models.CASCADE,
        related_name="block_scopes",
        verbose_name=_("Role"),
    )
    block = models.ForeignKey(
        "hrm.Block",
        on_delete=models.CASCADE,
        related_name="role_scopes",
        verbose_name=_("Block"),
    )

    class Meta:
        verbose_name = _("Role Block Scope")
        verbose_name_plural = _("Role Block Scopes")
        db_table = "hrm_role_block_scope"
        unique_together = [["role", "block"]]

    def __str__(self):
        return f"{self.role.name} -> {self.block.name}"


class RoleDepartmentScope(BaseModel):
    """
    Links a Role to allowed Departments.
    Only applies when Role.data_scope_level = 'department'
    """

    role = models.ForeignKey(
        "core.Role",
        on_delete=models.CASCADE,
        related_name="department_scopes",
        verbose_name=_("Role"),
    )
    department = models.ForeignKey(
        "hrm.Department",
        on_delete=models.CASCADE,
        related_name="role_scopes",
        verbose_name=_("Department"),
    )

    class Meta:
        verbose_name = _("Role Department Scope")
        verbose_name_plural = _("Role Department Scopes")
        db_table = "hrm_role_department_scope"
        unique_together = [["role", "department"]]

    def __str__(self):
        return f"{self.role.name} -> {self.department.name}"
```

### 4.3 Entity Relationship Diagram

```
                              ┌─────────────────────┐
                              │      core.Role      │
                              ├─────────────────────┤
                              │ PK: id              │
                              │ code                │
                              │ name                │
                              │ data_scope_level    │ ◄── NEW FIELD
                              │ permissions (M2M)   │
                              └─────────┬───────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    │                   │                   │
                    ▼                   ▼                   ▼
        ┌───────────────────┐ ┌─────────────────┐ ┌──────────────────────┐
        │hrm.RoleBranchScope│ │hrm.RoleBlockScope│ │hrm.RoleDepartmentScope│
        ├───────────────────┤ ├─────────────────┤ ├──────────────────────┤
        │ FK: role_id ──────┼─┼─ FK: role_id ───┼─┼─ FK: role_id         │
        │ FK: branch_id     │ │ FK: block_id    │ │ FK: department_id    │
        └────────┬──────────┘ └────────┬────────┘ └─────────┬────────────┘
                 │                     │                    │
                 ▼                     ▼                    ▼
        ┌───────────────┐     ┌───────────────┐    ┌──────────────────┐
        │  hrm.Branch   │     │  hrm.Block    │    │ hrm.Department   │
        └───────────────┘     └───────────────┘    └──────────────────┘
```

### 4.4 Database Tables Summary

| Table | App | Purpose | Key Columns |
|-------|-----|---------|-------------|
| `core_role` | core | Role with data scope level | `data_scope_level` (new) |
| `hrm_role_branch_scope` | hrm | Role ↔ Branch assignments | `role_id`, `branch_id` |
| `hrm_role_block_scope` | hrm | Role ↔ Block assignments | `role_id`, `block_id` |
| `hrm_role_department_scope` | hrm | Role ↔ Department assignments | `role_id`, `department_id` |

---

## 5. Business Logic Implementation

### 5.1 Core Utility: `collect_role_allowed_units`

This function collects all organizational units a user can access based on their role's data scope configuration.

```python
# apps/hrm/utils/role_data_scope.py

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
        return not self.has_all and not any([
            self.branches, self.blocks, self.departments
        ])

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
    from apps.hrm.models import RoleBranchScope, RoleBlockScope, RoleDepartmentScope

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
        branch_ids = set(
            RoleBranchScope.objects
            .filter(role=role)
            .values_list("branch_id", flat=True)
        )
        allowed.branches = branch_ids
        logger.debug("Role %s has BRANCH scope: %s", role.id, branch_ids)

    elif scope_level == DataScopeLevel.BLOCK:
        block_ids = set(
            RoleBlockScope.objects
            .filter(role=role)
            .values_list("block_id", flat=True)
        )
        allowed.blocks = block_ids
        logger.debug("Role %s has BLOCK scope: %s", role.id, block_ids)

    elif scope_level == DataScopeLevel.DEPARTMENT:
        dept_ids = set(
            RoleDepartmentScope.objects
            .filter(role=role)
            .values_list("department_id", flat=True)
        )
        allowed.departments = dept_ids
        logger.debug("Role %s has DEPARTMENT scope: %s", role.id, dept_ids)

    # Cache the result
    if use_cache:
        cache.set(cache_key, allowed.to_cache_dict(), ROLE_UNITS_CACHE_TIMEOUT)
        logger.debug("Cached role units for user %s", user.id)

    return allowed
```

### 5.2 Filter Backend: `RoleDataScopeFilterBackend`

A DRF filter backend that applies role-based data scope filtering.

```python
# apps/hrm/utils/filters.py (add to existing file)

from rest_framework.filters import BaseFilterBackend
from apps.hrm.utils.role_data_scope import collect_role_allowed_units, RoleAllowedUnits


class RoleDataScopeFilterBackend(BaseFilterBackend):
    """
    Filter backend that applies role-based data scope filtering.

    Usage in ViewSet:
        class MyViewSet(viewsets.ModelViewSet):
            filter_backends = [RoleDataScopeFilterBackend, ...]

            # Configure which field maps to organizational units
            data_scope_config = {
                "branch_field": "branch",           # or "employee__branch"
                "block_field": "block",             # or "employee__block"
                "department_field": "department",   # or "employee__department"
            }
    """

    def filter_queryset(self, request, queryset, view):
        """Apply role-based data scope filtering"""
        if not request.user or not request.user.is_authenticated:
            return queryset.none()

        # Get config from view
        config = getattr(view, "data_scope_config", {})

        return filter_queryset_by_role_data_scope(queryset, request.user, config)


def filter_queryset_by_role_data_scope(
    queryset: QuerySet,
    user: UserType,
    config: dict = None
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
    branch_field = config.get("branch_field", "branch")
    block_field = config.get("block_field", "block")
    department_field = config.get("department_field", "department")

    # Build filter query
    q_filter = Q()

    if allowed.branches:
        q_filter |= _build_filter(queryset, f"{branch_field}__in", allowed.branches)
        q_filter |= _build_filter(queryset, f"{branch_field}_id__in", allowed.branches)

    if allowed.blocks:
        q_filter |= _build_filter(queryset, f"{block_field}__in", allowed.blocks)
        q_filter |= _build_filter(queryset, f"{block_field}_id__in", allowed.blocks)
        # Also include if parent branch is allowed
        if allowed.branches:
            q_filter |= _build_filter(queryset, f"{block_field}__branch__in", allowed.branches)

    if allowed.departments:
        q_filter |= _build_filter(queryset, f"{department_field}__in", allowed.departments)
        q_filter |= _build_filter(queryset, f"{department_field}_id__in", allowed.departments)
        # Also include if parent block/branch is allowed
        if allowed.blocks:
            q_filter |= _build_filter(queryset, f"{department_field}__block__in", allowed.blocks)
        if allowed.branches:
            q_filter |= _build_filter(queryset, f"{department_field}__branch__in", allowed.branches)

    if not q_filter:
        return queryset.none()

    return queryset.filter(q_filter).distinct()


def _build_filter(queryset, field_path, values):
    """Build Q filter, validating field path exists"""
    try:
        q = Q(**{field_path: values})
        # Validate path by building query
        queryset.filter(q).query
        return q
    except Exception:
        return Q()
```

### 5.3 Object-Level Permission: `DataScopePermission`

**Critical:** The filter backend only applies to list views. For object-level access (retrieve, update, delete), we need a DRF Permission class that returns **403 Forbidden** when accessing objects outside the user's data scope.

```python
# apps/core/api/permissions.py (add to existing file)

from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied
from django.utils.translation import gettext as _


class DataScopePermission(BasePermission):
    """
    Object-level permission that checks if user has access to the object's
    organizational unit based on their role's data scope.

    This permission class should be used together with RoleDataScopeFilterBackend.
    - FilterBackend: Filters list views
    - Permission: Blocks access to individual objects (retrieve, update, delete)

    Usage in ViewSet:
        class EmployeeViewSet(viewsets.ModelViewSet):
            permission_classes = [IsAuthenticated, RoleBasedPermission, DataScopePermission]
            filter_backends = [RoleDataScopeFilterBackend, ...]

            data_scope_config = {
                "branch_field": "branch",
                "block_field": "block",
                "department_field": "department",
            }

    Returns:
        - True: User has access to the object
        - PermissionDenied (403): User does not have access to the object
    """

    message = _("You do not have permission to access this data.")

    def has_permission(self, request, view):
        """
        List-level permission check.
        Always returns True because filtering is handled by RoleDataScopeFilterBackend.
        """
        return True

    def has_object_permission(self, request, view, obj):
        """
        Object-level permission check.
        Verifies user has access to the object's organizational unit.
        """
        user = request.user

        # Unauthenticated users are handled by IsAuthenticated
        if not user or not user.is_authenticated:
            return False

        # Superusers have full access
        if user.is_superuser:
            return True

        # Get allowed units for user
        from apps.hrm.utils.role_data_scope import collect_role_allowed_units
        allowed = collect_role_allowed_units(user)

        # ROOT scope has full access
        if allowed.has_all:
            return True

        # No allowed units = no access
        if allowed.is_empty:
            raise PermissionDenied(self.message)

        # Get config from view
        config = getattr(view, "data_scope_config", {})

        # Check if object is within allowed scope
        if not self._check_object_scope(obj, allowed, config):
            raise PermissionDenied(self.message)

        return True

    def _check_object_scope(self, obj, allowed, config):
        """
        Check if object is within user's allowed organizational scope.

        Performance optimized: Uses select_related data when available,
        falls back to DB query only when necessary.

        Args:
            obj: The model instance being accessed
            allowed: RoleAllowedUnits with user's allowed units
            config: Dict with field mappings from view

        Returns:
            bool: True if object is within scope
        """
        branch_field = config.get("branch_field", "branch")
        block_field = config.get("block_field", "block")
        department_field = config.get("department_field", "department")

        # Get organizational unit IDs from object (use _id suffix to avoid extra queries)
        branch_id = self._get_field_id(obj, branch_field)
        block_id = self._get_field_id(obj, block_field)
        department_id = self._get_field_id(obj, department_field)

        # Check branch scope
        if allowed.branches:
            if branch_id and branch_id in allowed.branches:
                return True
            # Check if block's branch is allowed (try to get from object first)
            if block_id:
                block_branch_id = self._get_parent_branch_id(obj, block_field)
                if block_branch_id and block_branch_id in allowed.branches:
                    return True
            # Check if department's branch is allowed
            if department_id:
                dept_branch_id = self._get_parent_branch_id(obj, department_field)
                if dept_branch_id and dept_branch_id in allowed.branches:
                    return True

        # Check block scope
        if allowed.blocks:
            if block_id and block_id in allowed.blocks:
                return True
            # Check if department's block is allowed
            if department_id:
                dept_block_id = self._get_parent_block_id(obj, department_field)
                if dept_block_id and dept_block_id in allowed.blocks:
                    return True

        # Check department scope
        if allowed.departments:
            if department_id and department_id in allowed.departments:
                return True

        return False

    def _get_field_id(self, obj, field_path):
        """
        Get field ID from object, preferring _id attribute to avoid extra queries.

        Args:
            obj: The model instance
            field_path: Path like "branch" or "employee__branch"

        Returns:
            The field ID or None
        """
        parts = field_path.split("__")
        value = obj

        for i, part in enumerate(parts):
            if value is None:
                return None
            # For the last part, try to get _id directly
            if i == len(parts) - 1:
                id_attr = f"{part}_id"
                if hasattr(value, id_attr):
                    return getattr(value, id_attr)
            value = getattr(value, part, None)

        # Return ID if it's a model instance
        if value is not None and hasattr(value, "id"):
            return value.id
        return value

    def _get_parent_branch_id(self, obj, field_path):
        """Get branch_id from a block or department field"""
        value = self._traverse_path(obj, field_path)
        if value is None:
            return None
        # Try to get branch_id directly (avoids extra query)
        if hasattr(value, "branch_id"):
            return value.branch_id
        if hasattr(value, "branch") and value.branch:
            return value.branch.id
        return None

    def _get_parent_block_id(self, obj, field_path):
        """Get block_id from a department field"""
        value = self._traverse_path(obj, field_path)
        if value is None:
            return None
        if hasattr(value, "block_id"):
            return value.block_id
        if hasattr(value, "block") and value.block:
            return value.block.id
        return None

    def _traverse_path(self, obj, field_path):
        """Traverse object path without getting IDs"""
        parts = field_path.split("__")
        value = obj
        for part in parts:
            if value is None:
                return None
            value = getattr(value, part, None)
        return value
```

### 5.4 Signals for Cache Invalidation

To ensure cache consistency, we use Django signals to invalidate caches when scope assignments change.

```python
# apps/hrm/signals/role_data_scope.py

from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver

from apps.hrm.models import RoleBranchScope, RoleBlockScope, RoleDepartmentScope
from apps.hrm.utils.role_data_scope import invalidate_role_units_cache_for_role


@receiver([post_save, post_delete], sender=RoleBranchScope)
@receiver([post_save, post_delete], sender=RoleBlockScope)
@receiver([post_save, post_delete], sender=RoleDepartmentScope)
def invalidate_cache_on_scope_change(sender, instance, **kwargs):
    """Invalidate cache when role scope assignments change"""
    invalidate_role_units_cache_for_role(instance.role_id)


# Also invalidate when user's role changes
@receiver(pre_save, sender="core.User")
def invalidate_cache_on_user_role_change(sender, instance, **kwargs):
    """Invalidate cache when user's role is changed"""
    from apps.hrm.utils.role_data_scope import invalidate_role_units_cache

    if instance.pk:
        try:
            old_instance = sender.objects.get(pk=instance.pk)
            if old_instance.role_id != instance.role_id:
                invalidate_role_units_cache(instance.pk)
        except sender.DoesNotExist:
            pass
```

Register signals in `apps/hrm/apps.py`:

```python
# apps/hrm/apps.py

class HrmConfig(AppConfig):
    name = "apps.hrm"

    def ready(self):
        # Import signals to register them
        from apps.hrm.signals import role_data_scope  # noqa: F401
```

### 5.5 Combined Permission Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     DATA SCOPE PERMISSION FLOW                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  REQUEST                                                                 │
│     │                                                                    │
│     ▼                                                                    │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    IsAuthenticated                                │   │
│  │                    (401 if not logged in)                        │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│     │                                                                    │
│     ▼                                                                    │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                   RoleBasedPermission                             │   │
│  │              (403 if no action permission)                        │   │
│  │         e.g., user needs "employee.retrieve" permission           │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│     │                                                                    │
│     ▼                                                                    │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                   DataScopePermission                             │   │
│  │              (403 if no data scope access)                        │   │
│  │     e.g., user can't access employee from other branch           │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│     │                                                                    │
│     ▼                                                                    │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │              RoleDataScopeFilterBackend                           │   │
│  │              (Filters list queryset)                              │   │
│  │         Only shows data within user's scope                       │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│     │                                                                    │
│     ▼                                                                    │
│  SUCCESS - Return data                                                   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.6 Error Response Examples

**403 - No Data Scope Access:**
```json
{
    "success": false,
    "error": {
        "code": "permission_denied",
        "message": "You do not have permission to access this data."
    }
}
```

**Example Scenario:**
- User has role "Recruitment Manager - Quang Ninh" with `data_scope_level = "branch"` and `branch_scopes = [Quang Ninh]`
- User tries to access `GET /api/v1/employees/123/` where employee 123 belongs to Ha Noi branch
- Response: `403 Forbidden` with message above

### 5.6 User Model Extension

Add helper methods to the `User` model for easy data scope access.

```python
# apps/core/models/user.py (add methods)

def get_allowed_units(self) -> "RoleAllowedUnits":
    """
    Get allowed organizational units based on role data scope.

    Returns:
        RoleAllowedUnits: Container with branches, blocks, departments
    """
    from apps.hrm.utils.role_data_scope import collect_role_allowed_units
    return collect_role_allowed_units(self)

def has_access_to_branch(self, branch_id: int) -> bool:
    """Check if user has access to a specific branch"""
    allowed = self.get_allowed_units()
    if allowed.has_all:
        return True
    return branch_id in allowed.branches

def has_access_to_block(self, block_id: int) -> bool:
    """Check if user has access to a specific block"""
    allowed = self.get_allowed_units()
    if allowed.has_all:
        return True
    if block_id in allowed.blocks:
        return True
    # Check if block's branch is allowed
    from apps.hrm.models import Block
    try:
        block = Block.objects.get(id=block_id)
        return block.branch_id in allowed.branches
    except Block.DoesNotExist:
        return False

def has_access_to_department(self, department_id: int) -> bool:
    """Check if user has access to a specific department"""
    allowed = self.get_allowed_units()
    if allowed.has_all:
        return True
    if department_id in allowed.departments:
        return True
    # Check if department's block or branch is allowed
    from apps.hrm.models import Department
    try:
        dept = Department.objects.get(id=department_id)
        if dept.block_id in allowed.blocks:
            return True
        return dept.branch_id in allowed.branches
    except Department.DoesNotExist:
        return False
```

---

## 6. API Design

### 6.1 Role Data Scope Management APIs

#### 6.1.1 Update Role with Data Scope

**Endpoint:** `PATCH /api/v1/roles/{role_id}/`

**Request Body:**
```json
{
    "name": "Recruitment Manager - North Region",
    "data_scope_level": "branch",
    "branch_scope_ids": [1, 2],
    "block_scope_ids": [],
    "department_scope_ids": []
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "id": 5,
        "code": "VT00005",
        "name": "Recruitment Manager - North Region",
        "data_scope_level": "branch",
        "data_scope_level_display": "Branch level",
        "branch_scopes": [
            {"id": 1, "code": "CN01", "name": "Ha Noi Branch"},
            {"id": 2, "code": "CN02", "name": "Quang Ninh Branch"}
        ],
        "block_scopes": [],
        "department_scopes": [],
        "permissions": [...]
    }
}
```

#### 6.1.2 Get Role Detail with Data Scope

**Endpoint:** `GET /api/v1/roles/{role_id}/`

**Response:** Same as above

### 6.2 Role Serializer Extension

```python
# apps/core/api/serializers/role.py (extend existing)

from apps.hrm.models import RoleBranchScope, RoleBlockScope, RoleDepartmentScope, Branch, Block, Department


class RoleBranchScopeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ["id", "code", "name"]


class RoleBlockScopeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Block
        fields = ["id", "code", "name"]


class RoleDepartmentScopeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "code", "name"]


class RoleDetailSerializer(serializers.ModelSerializer):
    """Extended role serializer with data scope info"""

    data_scope_level_display = serializers.CharField(
        source="get_data_scope_level_display",
        read_only=True
    )
    branch_scopes = serializers.SerializerMethodField()
    block_scopes = serializers.SerializerMethodField()
    department_scopes = serializers.SerializerMethodField()

    # For write operations
    branch_scope_ids = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.all(),
        many=True,
        write_only=True,
        required=False,
    )
    block_scope_ids = serializers.PrimaryKeyRelatedField(
        queryset=Block.objects.all(),
        many=True,
        write_only=True,
        required=False,
    )
    department_scope_ids = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        many=True,
        write_only=True,
        required=False,
    )

    class Meta:
        model = Role
        fields = [
            "id", "code", "name", "description",
            "is_system_role", "is_default_role",
            "data_scope_level", "data_scope_level_display",
            "branch_scopes", "block_scopes", "department_scopes",
            "branch_scope_ids", "block_scope_ids", "department_scope_ids",
            "permissions",
        ]

    def validate(self, attrs):
        """Validate scope level consistency with assigned scopes"""
        attrs = super().validate(attrs)

        data_scope_level = attrs.get("data_scope_level") or (
            self.instance.data_scope_level if self.instance else DataScopeLevel.ROOT
        )
        branch_scope_ids = attrs.get("branch_scope_ids")
        block_scope_ids = attrs.get("block_scope_ids")
        department_scope_ids = attrs.get("department_scope_ids")

        # Validate: ROOT level should not have any scopes
        if data_scope_level == DataScopeLevel.ROOT:
            if branch_scope_ids or block_scope_ids or department_scope_ids:
                raise serializers.ValidationError({
                    "data_scope_level": "ROOT level should not have any scope assignments."
                })

        # Validate: BRANCH level should only have branch scopes
        elif data_scope_level == DataScopeLevel.BRANCH:
            if block_scope_ids:
                raise serializers.ValidationError({
                    "block_scope_ids": "Cannot assign block scopes for branch-level role."
                })
            if department_scope_ids:
                raise serializers.ValidationError({
                    "department_scope_ids": "Cannot assign department scopes for branch-level role."
                })

        # Validate: BLOCK level should only have block scopes
        elif data_scope_level == DataScopeLevel.BLOCK:
            if branch_scope_ids:
                raise serializers.ValidationError({
                    "branch_scope_ids": "Cannot assign branch scopes for block-level role."
                })
            if department_scope_ids:
                raise serializers.ValidationError({
                    "department_scope_ids": "Cannot assign department scopes for block-level role."
                })

        # Validate: DEPARTMENT level should only have department scopes
        elif data_scope_level == DataScopeLevel.DEPARTMENT:
            if branch_scope_ids:
                raise serializers.ValidationError({
                    "branch_scope_ids": "Cannot assign branch scopes for department-level role."
                })
            if block_scope_ids:
                raise serializers.ValidationError({
                    "block_scope_ids": "Cannot assign block scopes for department-level role."
                })

        return attrs

    def get_branch_scopes(self, obj):
        branches = Branch.objects.filter(role_scopes__role=obj)
        return RoleBranchScopeSerializer(branches, many=True).data

    def get_block_scopes(self, obj):
        blocks = Block.objects.filter(role_scopes__role=obj)
        return RoleBlockScopeSerializer(blocks, many=True).data

    def get_department_scopes(self, obj):
        departments = Department.objects.filter(role_scopes__role=obj)
        return RoleDepartmentScopeSerializer(departments, many=True).data

    def update(self, instance, validated_data):
        # Handle scope updates
        branch_ids = validated_data.pop("branch_scope_ids", None)
        block_ids = validated_data.pop("block_scope_ids", None)
        dept_ids = validated_data.pop("department_scope_ids", None)

        instance = super().update(instance, validated_data)

        # Update branch scopes
        if branch_ids is not None:
            RoleBranchScope.objects.filter(role=instance).delete()
            for branch in branch_ids:
                RoleBranchScope.objects.create(role=instance, branch=branch)

        # Update block scopes
        if block_ids is not None:
            RoleBlockScope.objects.filter(role=instance).delete()
            for block in block_ids:
                RoleBlockScope.objects.create(role=instance, block=block)

        # Update department scopes
        if dept_ids is not None:
            RoleDepartmentScope.objects.filter(role=instance).delete()
            for dept in dept_ids:
                RoleDepartmentScope.objects.create(role=instance, department=dept)

        return instance
```

### 6.3 API Documentation with OpenAPI Schema

All Role APIs must include `@extend_schema` decorators per project standards:

```python
# apps/core/api/views/role.py

from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiParameter
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.core.api.permissions import RoleBasedPermission
from apps.core.api.serializers import RoleDetailSerializer
from apps.core.models import Role


class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleDetailSerializer
    permission_classes = [IsAuthenticated, RoleBasedPermission]

    @extend_schema(
        summary="List all roles",
        tags=["Roles"],
        responses={200: RoleDetailSerializer(many=True)},
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "count": 1,
                        "results": [{
                            "id": 5,
                            "code": "VT00005",
                            "name": "Recruitment Manager - North Region",
                            "data_scope_level": "branch",
                            "data_scope_level_display": "Branch level",
                            "branch_scopes": [
                                {"id": 1, "code": "CN01", "name": "Ha Noi Branch"}
                            ],
                            "block_scopes": [],
                            "department_scopes": [],
                        }]
                    }
                },
                response_only=True,
            ),
        ],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Retrieve role detail",
        tags=["Roles"],
        responses={200: RoleDetailSerializer},
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 5,
                        "code": "VT00005",
                        "name": "Recruitment Manager - North Region",
                        "data_scope_level": "branch",
                        "data_scope_level_display": "Branch level",
                        "branch_scopes": [
                            {"id": 1, "code": "CN01", "name": "Ha Noi Branch"},
                            {"id": 2, "code": "CN02", "name": "Quang Ninh Branch"}
                        ],
                        "block_scopes": [],
                        "department_scopes": [],
                        "permissions": ["employee.list", "employee.retrieve"]
                    }
                },
                response_only=True,
            ),
        ],
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="Update role with data scope",
        tags=["Roles"],
        request=RoleDetailSerializer,
        responses={200: RoleDetailSerializer},
        examples=[
            OpenApiExample(
                "Request - Update to branch scope",
                value={
                    "name": "Recruitment Manager - North Region",
                    "data_scope_level": "branch",
                    "branch_scope_ids": [1, 2],
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 5,
                        "code": "VT00005",
                        "name": "Recruitment Manager - North Region",
                        "data_scope_level": "branch",
                        "branch_scopes": [
                            {"id": 1, "code": "CN01", "name": "Ha Noi Branch"},
                            {"id": 2, "code": "CN02", "name": "Quang Ninh Branch"}
                        ],
                    }
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error - Invalid scope assignment",
                value={
                    "success": False,
                    "error": {
                        "code": "validation_error",
                        "message": "Cannot assign block scopes for branch-level role.",
                        "details": {
                            "block_scope_ids": ["Cannot assign block scopes for branch-level role."]
                        }
                    }
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)
```

### 6.4 Create Action Validation (Data Scope Check)

For create actions, we need to validate that the new object is within the user's allowed scope:

```python
# apps/hrm/api/mixins.py

from rest_framework.exceptions import PermissionDenied
from django.utils.translation import gettext as _

from apps.hrm.utils.role_data_scope import collect_role_allowed_units


class DataScopeCreateValidationMixin:
    """
    Mixin to validate create operations against user's data scope.

    Must be used with ViewSets that have `data_scope_config` attribute.
    """

    def perform_create(self, serializer):
        """Validate new object is within user's allowed scope before saving"""
        user = self.request.user

        # Superusers bypass validation
        if user.is_superuser:
            return super().perform_create(serializer)

        allowed = collect_role_allowed_units(user)

        # ROOT scope allows creating anywhere
        if allowed.has_all:
            return super().perform_create(serializer)

        # Get config
        config = getattr(self, "data_scope_config", {})

        # Validate the object being created
        validated_data = serializer.validated_data

        if not self._validate_create_scope(validated_data, allowed, config):
            raise PermissionDenied(
                _("You cannot create objects outside your assigned organizational scope.")
            )

        return super().perform_create(serializer)

    def _validate_create_scope(self, validated_data, allowed, config):
        """
        Validate that the object being created is within user's scope.

        Returns:
            bool: True if creation is allowed
        """
        branch_field = config.get("branch_field", "branch")
        block_field = config.get("block_field", "block")
        department_field = config.get("department_field", "department")

        # Get values from validated data
        branch = self._get_nested_value(validated_data, branch_field)
        block = self._get_nested_value(validated_data, block_field)
        department = self._get_nested_value(validated_data, department_field)

        # Get IDs
        branch_id = branch.id if branch else None
        block_id = block.id if block else None
        department_id = department.id if department else None

        # Check against allowed units
        if allowed.branches:
            if branch_id and branch_id in allowed.branches:
                return True
            if block_id:
                from apps.hrm.models import Block
                try:
                    b = Block.objects.get(id=block_id)
                    if b.branch_id in allowed.branches:
                        return True
                except Block.DoesNotExist:
                    pass
            if department_id:
                from apps.hrm.models import Department
                try:
                    d = Department.objects.get(id=department_id)
                    if d.branch_id in allowed.branches:
                        return True
                except Department.DoesNotExist:
                    pass

        if allowed.blocks:
            if block_id and block_id in allowed.blocks:
                return True
            if department_id:
                from apps.hrm.models import Department
                try:
                    d = Department.objects.get(id=department_id)
                    if d.block_id in allowed.blocks:
                        return True
                except Department.DoesNotExist:
                    pass

        if allowed.departments:
            if department_id and department_id in allowed.departments:
                return True

        return False

    def _get_nested_value(self, data, field_path):
        """Get value from nested dict/object using field path"""
        parts = field_path.split("__")
        value = data
        for part in parts:
            if value is None:
                return None
            if isinstance(value, dict):
                value = value.get(part)
            else:
                value = getattr(value, part, None)
        return value
```

Usage in ViewSet:

```python
# apps/hrm/api/views/employee.py

from apps.hrm.api.mixins import DataScopeCreateValidationMixin

class EmployeeViewSet(DataScopeCreateValidationMixin, AuditLoggingMixin, BaseModelViewSet):
    queryset = Employee.objects.all()
    permission_classes = [IsAuthenticated, RoleBasedPermission, DataScopePermission]
    filter_backends = [RoleDataScopeFilterBackend, DjangoFilterBackend, PhraseSearchFilter]

    data_scope_config = {
        "branch_field": "branch",
        "block_field": "block",
        "department_field": "department",
    }
```

---

## 7. ViewSets Requiring Data Scope Integration

### 7.1 ViewSet Analysis

After reviewing all ViewSets in the project, here is the categorization:

#### 7.1.1 Phase 1: High Priority (Employee-Related Data)

| ViewSet | App | Model | Data Scope Field | Priority |
|---------|-----|-------|------------------|----------|
| `EmployeeViewSet` | hrm | Employee | `department` | **Critical** |
| `EmployeeTimesheetViewSet` | hrm | Timesheet | `employee__department` | **Critical** |
| `BankAccountViewSet` | hrm | BankAccount | `employee__department` | High |
| `EmployeeDependentViewSet` | hrm | EmployeeDependent | `employee__department` | High |
| `ContractViewSet` | hrm | Contract | `employee__department` | High |
| `ContractAppendixViewSet` | hrm | ContractAppendix | `contract__employee__department` | High |
| `DecisionViewSet` | hrm | Decision | `employee__department` | High |
| `AttendanceRecordViewSet` | hrm | AttendanceRecord | `employee__department` | High |
| `AttendanceExemptionViewSet` | hrm | AttendanceExemption | `employee__department` | High |

#### 7.1.2 Phase 2: Medium Priority (Payroll & KPI)

| ViewSet | App | Model | Data Scope Field | Priority |
|---------|-----|-------|------------------|----------|
| `PayrollSlipViewSet` | payroll | PayrollSlip | `employee__department` | **Critical** |
| `SalaryPeriodViewSet` | payroll | SalaryPeriod | Complex* | High |
| `SalaryPeriodReadySlipsViewSet` | payroll | PayrollSlip | `employee__department` | High |
| `SalaryPeriodNotReadySlipsViewSet` | payroll | PayrollSlip | `employee__department` | High |
| `EmployeeKPIAssessmentViewSet` | payroll | EmployeeKPIAssessment | `employee__department` | **Critical** |
| `DepartmentKPIAssessmentViewSet` | payroll | DepartmentKPIAssessment | `department` | High |
| `KPIAssessmentPeriodViewSet` | payroll | KPIAssessmentPeriod | Complex* | Medium |
| `PenaltyTicketViewSet` | payroll | PenaltyTicket | `employee__department` | High |
| `RecoveryVoucherViewSet` | payroll | RecoveryVoucher | `employee__department` | High |
| `SalesRevenueViewSet` | payroll | SalesRevenue | `employee__department` | High |
| `TravelExpenseViewSet` | payroll | TravelExpense | `employee__department` | Medium |

#### 7.1.3 Phase 3: Recruitment Module

| ViewSet | App | Model | Data Scope Field | Priority |
|---------|-----|-------|------------------|----------|
| `RecruitmentRequestViewSet` | hrm | RecruitmentRequest | `department` | High |
| `RecruitmentCandidateViewSet` | hrm | RecruitmentCandidate | `recruitment_request__department` | High |
| `InterviewCandidateViewSet` | hrm | InterviewCandidate | `candidate__recruitment_request__department` | Medium |
| `InterviewScheduleViewSet` | hrm | InterviewSchedule | `candidate__recruitment_request__department` | Medium |
| `RecruitmentExpenseViewSet` | hrm | RecruitmentExpense | `recruitment_request__department` | Medium |
| `RecruitmentCandidateContactLogViewSet` | hrm | ContactLog | `candidate__recruitment_request__department` | Low |
| `JobDescriptionViewSet` | hrm | JobDescription | `department` | Medium |

#### 7.1.4 Phase 4: Proposals & Misc

| ViewSet | App | Model | Data Scope Field | Priority |
|---------|-----|-------|------------------|----------|
| `ProposalViewSet` | hrm | Proposal | `employee__department` | High |
| `ProposalTimesheetEntryComplaintViewSet` | hrm | Proposal | `employee__department` | High |
| `ProposalPostMaternityBenefitsViewSet` | hrm | Proposal | `employee__department` | Medium |
| `ProposalLateExemptionViewSet` | hrm | Proposal | `employee__department` | Medium |
| `ProposalOvertimeWorkViewSet` | hrm | Proposal | `employee__department` | Medium |
| `ProposalPaidLeaveViewSet` | hrm | Proposal | `employee__department` | Medium |
| `ProposalUnpaidLeaveViewSet` | hrm | Proposal | `employee__department` | Medium |
| `ProposalMaternityLeaveViewSet` | hrm | Proposal | `employee__department` | Medium |
| `ProposalJobTransferViewSet` | hrm | Proposal | `employee__department` | Medium |
| `ProposalAssetAllocationViewSet` | hrm | Proposal | `employee__department` | Low |
| `ProposalDeviceChangeViewSet` | hrm | Proposal | `employee__department` | Low |
| `ProposalVerifierViewSet` | hrm | ProposalVerifier | `proposal__employee__department` | Medium |

#### 7.1.5 Organization Data (Special Handling)

| ViewSet | App | Model | Data Scope Field | Notes |
|---------|-----|-------|------------------|-------|
| `BranchViewSet` | hrm | Branch | Self-referencing | Filter by allowed branches |
| `BlockViewSet` | hrm | Block | `branch` | Filter by allowed blocks/branches |
| `DepartmentViewSet` | hrm | Department | `branch` / `block` | Filter by allowed units |
| `PositionViewSet` | hrm | Position | None | **No data scope** (master data) |

#### 7.1.6 No Data Scope Required (Master Data / Global)

| ViewSet | App | Reason |
|---------|-----|--------|
| `RoleViewSet` | core | System configuration |
| `PermissionViewSet` | core | System configuration |
| `ProvinceViewSet` | core | Master data |
| `NationalityViewSet` | core | Master data |
| `AdministrativeUnitViewSet` | core | Master data |
| `BankViewSet` | hrm | Master data |
| `HolidayViewSet` | hrm | Company-wide |
| `CompensatoryWorkdayViewSet` | hrm | Company-wide |
| `WorkScheduleViewSet` | hrm | Company-wide |
| `RecruitmentChannelViewSet` | hrm | Master data |
| `ContractTypeViewSet` | hrm | Master data |
| `KPICriterionViewSet` | payroll | Master data |

#### 7.1.7 Mobile APIs (User-Specific)

| ViewSet | App | Model | Notes |
|---------|-----|-------|-------|
| `MyAttendanceRecordViewSet` | hrm | AttendanceRecord | Already filtered by current user |
| `MyProposalViewSet` | hrm | Proposal | Already filtered by current user |
| `MyKPIAssessmentViewSet` | payroll | KPIAssessment | Already filtered by current user |
| `MyPenaltyTicketViewSet` | payroll | PenaltyTicket | Already filtered by current user |
| `MyTeamKPIAssessmentViewSet` | payroll | KPIAssessment | **Needs data scope** |

### 7.2 Complex Cases (Deferred)

Some ViewSets require special handling due to complex data relationships:

| ViewSet | Complexity | Reason | Suggested Approach |
|---------|------------|--------|-------------------|
| `SalaryPeriodViewSet` | High | Contains aggregated data across employees | Filter underlying employee data, not period itself |
| `KPIAssessmentPeriodViewSet` | High | Period-based, contains many employees | Filter by employee access in nested queries |
| `AttendanceReportViewSet` | High | Aggregated report data | Apply filter to report generation |
| `EmployeeReportsViewSet` | High | Multiple report types | Apply filter per report type |
| `HRMDashboardViewSet` | High | Dashboard with multiple metrics | Filter each metric separately |
| `ManagerDashboardViewSet` | High | Manager-specific dashboard | Combine with leadership filtering |

### 7.3 Example Integration

```python
# apps/hrm/api/views/employee.py

from rest_framework.permissions import IsAuthenticated
from apps.core.api.permissions import RoleBasedPermission, DataScopePermission
from apps.hrm.utils.filters import RoleDataScopeFilterBackend

class EmployeeViewSet(AuditLoggingMixin, BaseModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer

    # Permission classes - order matters!
    permission_classes = [
        IsAuthenticated,           # 401 if not logged in
        RoleBasedPermission,       # 403 if no action permission (e.g., employee.retrieve)
        DataScopePermission,       # 403 if accessing data outside scope
    ]

    # Filter backends - for list view filtering
    filter_backends = [
        RoleDataScopeFilterBackend,  # <-- Add as FIRST filter
        DjangoFilterBackend,
        PhraseSearchFilter,
        OrderingFilter,
    ]

    # Configure data scope field mappings (used by both Permission and FilterBackend)
    data_scope_config = {
        "branch_field": "branch",
        "block_field": "block",
        "department_field": "department",
    }
```

```python
# apps/payroll/api/views/employee_kpi_assessment.py

from rest_framework.permissions import IsAuthenticated
from apps.core.api.permissions import RoleBasedPermission, DataScopePermission
from apps.hrm.utils.filters import RoleDataScopeFilterBackend

class EmployeeKPIAssessmentViewSet(ExportXLSXMixin, AuditLoggingMixin, BaseModelViewSet):
    queryset = EmployeeKPIAssessment.objects.all()
    serializer_class = EmployeeKPIAssessmentSerializer

    permission_classes = [
        IsAuthenticated,
        RoleBasedPermission,
        DataScopePermission,
    ]

    filter_backends = [
        RoleDataScopeFilterBackend,
        DjangoFilterBackend,
        OrderingFilter,
    ]

    data_scope_config = {
        "branch_field": "employee__branch",
        "block_field": "employee__block",
        "department_field": "employee__department",
    }
```

### 7.4 Permission vs Filter Backend Summary

| Component | Purpose | Actions Affected | Response |
|-----------|---------|------------------|----------|
| `DataScopePermission` | Object-level access control | `retrieve`, `update`, `partial_update`, `destroy` | **403 Forbidden** |
| `RoleDataScopeFilterBackend` | List filtering | `list` | Returns filtered queryset (no error) |

**Why both are needed:**
- **FilterBackend alone**: User can't see employee #123 in list, but can still access `GET /employees/123/` directly → **Data leak!**
- **Permission alone**: User gets 403 on direct access, but list would show ALL employees → **Data leak!**
- **Both together**: List is filtered AND direct access is blocked → **Secure!**
```

---

## 8. Migration Strategy

### 8.1 Migration Steps

1. **Phase 1: Database Schema**
   - Add `data_scope_level` field to `Role` model (default: `ROOT`)
   - Create new models in `hrm` app
   - Run migrations

2. **Phase 2: Business Logic**
   - Implement `collect_role_allowed_units` function
   - Create `RoleDataScopeFilterBackend` (for list filtering)
   - Create `DataScopePermission` (for object-level access control)
   - Add helper methods to `User` model

3. **Phase 3: API Layer**
   - Extend role serializers
   - Update role API endpoints
   - Add admin interface for data scope management

4. **Phase 4: ViewSet Integration**
   - Update high-priority ViewSets with both `DataScopePermission` and `RoleDataScopeFilterBackend`
   - Test thoroughly (list filtering + direct object access)
   - Roll out to remaining ViewSets

### 8.2 Default Behavior

| Scenario | Behavior |
|----------|----------|
| Existing roles | `data_scope_level = ROOT` (full access) - no breaking change |
| New roles | `data_scope_level = ROOT` by default |
| Role with no scope units | Returns empty queryset / 403 on direct access |
| Superuser | Always full access |
| User without role | Returns empty queryset / 403 on direct access |

---

## 9. Testing Requirements

### 9.1 Unit Tests

```python
# apps/hrm/tests/test_role_data_scope.py

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory
from rest_framework.exceptions import PermissionDenied
from apps.core.models import Role
from apps.core.models.role import DataScopeLevel
from apps.core.api.permissions import DataScopePermission
from apps.hrm.models import Branch, Block, Department, Employee
from apps.hrm.models import RoleBranchScope, RoleBlockScope, RoleDepartmentScope

User = get_user_model()


@pytest.mark.django_db
class TestRoleDataScopeFiltering:
    """Test role-based data scope filtering (list views)"""

    def test_root_scope_returns_all_data(self):
        """User with ROOT scope should see all data"""
        pass

    def test_branch_scope_filters_by_branches(self):
        """User with BRANCH scope should only see data from assigned branches"""
        pass

    def test_block_scope_filters_by_blocks(self):
        """User with BLOCK scope should only see data from assigned blocks"""
        pass

    def test_department_scope_filters_by_departments(self):
        """User with DEPARTMENT scope should only see data from assigned departments"""
        pass

    def test_no_role_returns_empty(self):
        """User without role should see no data"""
        pass

    def test_role_with_no_scopes_returns_empty(self):
        """Role with non-ROOT level but no assigned units returns empty"""
        pass

    def test_cascading_access_branch_to_department(self):
        """Branch scope should include all blocks/departments within"""
        pass


@pytest.mark.django_db
class TestDataScopeObjectPermission:
    """Test object-level data scope permission (retrieve, update, delete)"""

    def test_root_scope_allows_any_object_access(self):
        """User with ROOT scope should access any object"""
        pass

    def test_branch_scope_allows_same_branch_object(self):
        """User with BRANCH scope should access objects in their branch"""
        pass

    def test_branch_scope_denies_other_branch_object(self):
        """User with BRANCH scope should get 403 for objects in other branches"""
        pass

    def test_block_scope_denies_other_block_object(self):
        """User with BLOCK scope should get 403 for objects in other blocks"""
        pass

    def test_department_scope_denies_other_department_object(self):
        """User with DEPARTMENT scope should get 403 for objects in other departments"""
        pass

    def test_superuser_bypasses_data_scope(self):
        """Superuser should access any object regardless of scope"""
        pass

    def test_no_role_denies_object_access(self):
        """User without role should get 403 on any object"""
        pass

    def test_direct_id_access_blocked(self):
        """User cannot access object by ID if outside their scope"""
        # This is the key test for data leak prevention
        pass
```

### 9.2 Integration Tests

```python
@pytest.mark.django_db
class TestDataScopeAPIIntegration:
    """Integration tests for data scope with real API calls"""

    def test_list_filtered_and_retrieve_blocked(self, api_client):
        """
        Scenario: User with BRANCH scope for Branch A
        - GET /employees/ -> Only shows Branch A employees (filtered)
        - GET /employees/{id_from_branch_b}/ -> 403 Forbidden (blocked)
        """
        pass

    def test_update_blocked_for_out_of_scope(self, api_client):
        """
        Scenario: User tries to update employee from other branch
        - PATCH /employees/{id_from_other_branch}/ -> 403 Forbidden
        """
        pass

    def test_delete_blocked_for_out_of_scope(self, api_client):
        """
        Scenario: User tries to delete employee from other branch
        - DELETE /employees/{id_from_other_branch}/ -> 403 Forbidden
        """
        pass

    def test_create_blocked_for_out_of_scope(self, api_client):
        """
        Scenario: User tries to create employee in other branch
        - POST /employees/ with branch_id from other branch -> 403 Forbidden
        """
        pass
```

---

## 10. Security Considerations

### 10.1 Data Scope Validation

- **List filtering**: `RoleDataScopeFilterBackend` filters queryset for list views
- **Object-level permission**: `DataScopePermission` returns 403 for retrieve/update/delete outside scope
- **Create validation**: Validate new objects are within user's allowed scope in serializer/view
- **Update validation**: Prevent moving objects outside user's scope

### 10.2 Security Checklist

| Action | Protection | Component |
|--------|------------|-----------|
| `list` | Filter queryset | `RoleDataScopeFilterBackend` |
| `retrieve` | 403 if out of scope | `DataScopePermission` |
| `update` | 403 if out of scope | `DataScopePermission` |
| `partial_update` | 403 if out of scope | `DataScopePermission` |
| `destroy` | 403 if out of scope | `DataScopePermission` |
| `create` | Validate scope in serializer | Custom validation |

### 10.3 Admin Access

- Superusers bypass all data scope checks
- System roles should have explicit ROOT scope

---

## 11. Implementation Checklist

### Phase 1: Database Schema (Week 1)
- [ ] Add `DataScopeLevel` enum to `apps/core/models/role.py`
- [ ] Add `data_scope_level` field to `Role` model
- [ ] Create migration for `core` app
- [ ] Create `RoleBranchScope` model in `hrm` app
- [ ] Create `RoleBlockScope` model in `hrm` app
- [ ] Create `RoleDepartmentScope` model in `hrm` app
- [ ] Create migration for `hrm` app
- [ ] Add models to admin

### Phase 2: Business Logic (Week 2)
- [ ] Create `apps/hrm/utils/role_data_scope.py`
- [ ] Implement `RoleAllowedUnits` dataclass
- [ ] Implement `collect_role_allowed_units` function
- [ ] Implement `filter_queryset_by_role_data_scope` function
- [ ] Create `RoleDataScopeFilterBackend` class (list filtering)
- [ ] Create `DataScopePermission` class (object-level 403)
- [ ] Add helper methods to `User` model
- [ ] Write unit tests for filtering
- [ ] Write unit tests for object-level permission

### Phase 3: API Layer (Week 3)
- [ ] Extend `RoleSerializer` with data scope fields
- [ ] Create `RoleBranchScopeSerializer`
- [ ] Create `RoleBlockScopeSerializer`
- [ ] Create `RoleDepartmentScopeSerializer`
- [ ] Update `RoleViewSet` to handle scope updates
- [ ] Document APIs with OpenAPI examples
- [ ] Write integration tests (list + direct access)

### Phase 4: ViewSet Integration (Week 4-5)
- [ ] Update `EmployeeViewSet` (add `DataScopePermission` + `RoleDataScopeFilterBackend`)
- [ ] Update `EmployeeTimesheetViewSet`
- [ ] Update `PayrollSlipViewSet`
- [ ] Update `EmployeeKPIAssessmentViewSet`
- [ ] Update remaining high-priority ViewSets
- [ ] Update medium-priority ViewSets
- [ ] Performance testing
- [ ] Security testing (verify 403 on direct ID access)
- [ ] User acceptance testing

### Phase 5: Deferred Items (Future)
- [ ] Handle `SalaryPeriodViewSet` complex filtering
- [ ] Handle `KPIAssessmentPeriodViewSet` complex filtering
- [ ] Handle dashboard ViewSets
- [ ] Handle report ViewSets

---

## 12. Appendix

### A. Glossary

| Term | Definition |
|------|------------|
| Data Scope | The organizational boundary within which a user can access data |
| Data Scope Level | The type of organizational unit used for filtering (ROOT/BRANCH/BLOCK/DEPARTMENT) |
| Role | A named collection of permissions and data scope configuration |
| Permission | An action a user is allowed to perform (e.g., `employee.create`) |
| Organizational Unit | Branch, Block, or Department in the company hierarchy |
| Object-Level Permission | Permission check when accessing a specific object (not list) |

### B. Related Documentation

- [PERMISSIONS_SYSTEM.md](./PERMISSIONS_SYSTEM.md) - Current permission architecture
- [PERMISSIONS_USAGE.md](./PERMISSIONS_USAGE.md) - Permission implementation guide

### C. Project Standards Notes

**SafeTextField Consideration:**
The new models (`RoleBranchScope`, `RoleBlockScope`, `RoleDepartmentScope`) only contain foreign keys and inherit from `BaseModel`. No `TextField` fields are added, so `SafeTextField` is not required.

If any future additions require text fields for user-generated content, use `SafeTextField` instead of `models.TextField` per project XSS prevention standards.

**Translation (i18n) Standards:**
- `Meta.verbose_name` and `Meta.verbose_name_plural` are NOT translated (admin-facing)
- Only user-facing strings in API responses use `gettext()`

### D. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-08 | AI Assistant | Initial draft |
| 2.0 | 2026-01-08 | AI Assistant | Simplified design: removed RoleDataScope model, added field to Role; removed position fallback; added comprehensive ViewSet analysis |
| 2.1 | 2026-01-08 | AI Assistant | Added `DataScopePermission` for object-level access control (403 on direct ID access); added security flow diagram; updated tests and checklist |
| 2.2 | 2026-01-08 | AI Assistant | Added caching with invalidation signals; fixed N+1 queries in permission check; added scope level validation; added create action validation mixin; added `@extend_schema` API documentation; fixed i18n usage per project standards |
