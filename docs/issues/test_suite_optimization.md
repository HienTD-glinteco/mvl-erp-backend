# Test Suite Performance Optimization

**Created**: 2026-01-01
**Status**: In Progress (Phase 1 Complete)
**Impact**: CI runtime 99.41s → 75.97s (24% improvement)

## Results

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Local runtime (single) | 99.41s | 92.98s | **-6.4%** |
| CI runtime (8 workers) | 99.41s | 75.97s | **-24%** |
| Tests Passing | 3077 | 3077 | - |

### Files Migrated: 15+
- Created shared fixtures in HRM and Core apps
- Eliminated `TransactionTestCase` from ~15 test files
- ~50 test classes remain to migrate

---

## Problem

Test suite takes **5-6 minutes on CI** (2 processes), **~100 seconds locally**.

### Root Causes

| Issue | Impact |
|-------|--------|
| `TransactionTestCase` with manual `setUp()` | High - deletes/recreates data per test |
| No shared HRM fixtures | High - each class duplicates Province, Branch, Block, etc. |
| `Model.objects.all().delete()` in setUp | Medium - expensive with SQLite locks |

### Current Stats
- **3091 tests** across 105+ files
- **HRM app**: 110 test files (most impacted)
- Individual tests fast (0.05-0.4s) - **setup/teardown is the bottleneck**

---

## Solution: Complete Migration to Pytest Fixtures

### Phase 1: Create Shared HRM Fixtures

**[NEW]** `apps/hrm/tests/conftest.py`:

```python
"""Shared pytest fixtures for HRM tests."""
import pytest
from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import Block, Branch, Department, Position, Employee


@pytest.fixture
def province(db):
    """Create a test province."""
    return Province.objects.create(code="01", name="Test Province")


@pytest.fixture
def admin_unit(db, province):
    """Create a test administrative unit."""
    return AdministrativeUnit.objects.create(
        parent_province=province,
        name="Test Admin Unit",
        code="AU01",
        level=AdministrativeUnit.UnitLevel.DISTRICT,
    )


@pytest.fixture
def branch(db, province, admin_unit):
    """Create a test branch."""
    return Branch.objects.create(
        name="Test Branch",
        code="CN001",
        province=province,
        administrative_unit=admin_unit,
    )


@pytest.fixture
def block(db, branch):
    """Create a test block."""
    return Block.objects.create(
        name="Test Block",
        code="KH001",
        branch=branch,
        block_type=Block.BlockType.BUSINESS,
    )


@pytest.fixture
def department(db, branch, block):
    """Create a test department."""
    return Department.objects.create(
        name="Test Department",
        code="PB001",
        branch=branch,
        block=block,
    )


@pytest.fixture
def position(db):
    """Create a test position."""
    return Position.objects.create(name="Test Position", code="CV001")


@pytest.fixture
def employee(db, branch, block, department, position):
    """Create a test employee with all required relationships."""
    return Employee.objects.create(
        code="MV000001",
        fullname="Test Employee",
        username="testemployee",
        email="test@example.com",
        phone="0123456789",
        attendance_code="12345",
        start_date="2024-01-01",
        branch=branch,
        block=block,
        department=department,
        position=position,
        citizen_id="123456789012",
    )
```

---

### Phase 2: Migrate All Test Files

**Pattern Change**:

```diff
- from django.test import TransactionTestCase
-
- class BranchAPITest(TransactionTestCase):
-     def setUp(self):
-         Branch.objects.all().delete()
-         self.user = User.objects.create_superuser(...)
-         self.province = Province.objects.create(...)
-         # ... more manual setup

+ import pytest
+
+ @pytest.mark.django_db
+ class TestBranchAPI:
+     def test_create_branch(self, api_client, province, admin_unit):
+         # Uses shared fixtures from conftest.py
+         response = api_client.post(...)
+         assert response.status_code == 201
```

---

### Files to Migrate (All)

**HRM Tests** (110 files):
- `test_api.py`, `test_employee.py` (largest)
- All `test_*_api.py` files
- All model tests

**Core Tests** (~15 files):
- `test_auth.py`, `test_permissions.py`, etc.

**Other Apps**:
- Files, Audit Logging, Notifications

---

## Verification

```bash
# Run full suite and compare timing
ENVIRONMENT=test poetry run pytest --durations=0 -q

# Verify no regressions
ENVIRONMENT=test poetry run pytest -v
```

---

## Expected Outcome

| Metric | Before | After |
|--------|--------|-------|
| Local runtime | ~100s | ~60-70s |
| CI runtime (2 workers) | 5-6min | 3-4min |
| Fixture duplication | High | None |
