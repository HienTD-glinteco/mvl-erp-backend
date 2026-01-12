# Salary Period Management - Implementation Documentation

This document describes the implementation of the Salary Period Management features based on the SRS document at [salary-solution.md](salary-solution.md).

## Overview

The implementation adds functionality for:
1. **Lock/Unlock Salary Periods** - Complete and uncomplete salary periods
2. **Hold/Unhold Payroll Slips** - Defer payment of specific slips to next period
3. **Two-Table Display System** - Separate views for payment vs deferred slips
4. **CRUD Protection** - Block modifications to completed periods
5. **Penalty Payment Handling** - Handle penalty payments in completed periods

## Files Modified

### Models

#### [apps/payroll/models/salary_period.py](../apps/payroll/models/salary_period.py)

**New Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `uncompleted_at` | `DateTimeField` | Timestamp when period was last uncompleted |
| `uncompleted_by` | `ForeignKey(User)` | User who uncompleted the period |
| `payment_count` | `PositiveIntegerField` | Count of slips to be paid this period |
| `payment_total` | `DecimalField` | Total amount of slips to be paid |
| `deferred_count` | `PositiveIntegerField` | Count of deferred slips |
| `deferred_total` | `DecimalField` | Total amount of deferred slips |

**New Methods:**
```python
def can_uncomplete(self) -> bool:
    """Check if period can be uncompleted."""
    # Returns True if:
    # - Period is COMPLETED
    # - No newer period exists, OR newer period is ONGOING
    # - No DELIVERED slips with payment_period = this period

def uncomplete(self, user: User) -> None:
    """Revert period from COMPLETED to ONGOING."""
    # - Checks can_uncomplete()
    # - Sets status = ONGOING
    # - Records uncompleted_at and uncompleted_by
    # - Clears payment_period for all slips
```

**Updated Methods:**
- `complete()` - Now sets `payment_period = self` for READY slips
- `update_statistics()` - Now calculates payment/deferred counts and totals

#### [apps/payroll/models/payroll_slip.py](../apps/payroll/models/payroll_slip.py)

**New Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `payment_period` | `ForeignKey(SalaryPeriod)` | Period where slip will be paid |
| `hold_reason` | `SafeTextField` | Reason for holding the slip |
| `held_at` | `DateTimeField` | Timestamp when slip was held |
| `held_by` | `ForeignKey(User)` | User who held the slip |

**New Property:**
```python
@property
def is_carried_over(self) -> bool:
    """Check if slip is carried over from previous period."""
    return self.payment_period_id != self.salary_period_id
```

**New Methods:**
```python
def hold(self, user: User, reason: str = "") -> None:
    """Hold the slip for later payment."""

def unhold(self, user: User) -> None:
    """Release the slip from HOLD status."""
    # If period is COMPLETED, recalculates and updates status
```

### Migrations

#### [apps/payroll/migrations/0004_add_period_management_fields.py](../apps/payroll/migrations/0004_add_period_management_fields.py)
- Adds all new fields to `SalaryPeriod` and `PayrollSlip` models

#### [apps/payroll/migrations/0005_set_payment_period_for_delivered.py](../apps/payroll/migrations/0005_set_payment_period_for_delivered.py)
- Data migration to set `payment_period = salary_period` for all existing DELIVERED slips

### Signals

#### [apps/payroll/signals/period_protection.py](../apps/payroll/signals/period_protection.py) (NEW)

Implements CRUD protection for completed salary periods:
- Blocks create/update/delete of `TravelExpense`, `RecoveryVoucher`, `SalesRevenue`, `PenaltyTicket`
- **Exception**: Allows `PenaltyTicket` status change from UNPAID → PAID
- Raises `PermissionDenied` with descriptive error message

#### [apps/payroll/signals/model_lifecycle.py](../apps/payroll/signals/model_lifecycle.py)

**New Functions:**
```python
def should_trigger_recalculation(instance, period_field: str = "salary_period") -> bool:
    """Check if recalculation should be triggered based on period status."""
    # Returns False if period is COMPLETED

def _handle_penalty_payment_in_completed_period(instance) -> None:
    """Handle penalty payment when period is completed."""
    # When penalty changes UNPAID → PAID:
    # 1. Recalculates the payroll slip
    # 2. If slip was DELIVERED, sets status back to READY
```

### Services

#### [apps/payroll/services/payroll_calculation.py](../apps/payroll/services/payroll_calculation.py)

**Updated `calculate()` method:**
- Skips calculation for DELIVERED slips (already paid)
- Preserves HOLD status during recalculation:
  - Calculates values but doesn't change status to READY/PENDING
  - Maintains HOLD status until explicit unhold

### API Views

#### [apps/payroll/api/views/salary_period.py](../apps/payroll/api/views/salary_period.py)

**New Actions:**
```python
@action(detail=True, methods=["post"])
def uncomplete(self, request, pk=None):
    """Uncomplete a salary period (revert to ONGOING)."""
```

**Updated ViewSets:**
- `SalaryPeriodReadySlipsViewSet` (Table 1: Payment Table)
  - ONGOING: READY slips + DELIVERED from current period
  - COMPLETED: DELIVERED slips with `payment_period = current`

- `SalaryPeriodNotReadySlipsViewSet` (Table 2: Deferred Table)
  - ONGOING: PENDING + HOLD + carried-over DELIVERED
  - COMPLETED: Empty (deferred slips moved to next period)

#### [apps/payroll/api/views/payroll_slip.py](../apps/payroll/api/views/payroll_slip.py)

**Updated `hold` action:** Now uses model method
**New `unhold` action:**
```python
@action(detail=True, methods=["post"])
def unhold(self, request, pk=None):
    """Release a slip from HOLD status."""
```

### Serializers

#### [apps/payroll/api/serializers/salary_period.py](../apps/payroll/api/serializers/salary_period.py)

**New Fields in `SalaryPeriodListSerializer` and `SalaryPeriodSerializer`:**
- `payment_count`, `payment_total`
- `deferred_count`, `deferred_total`
- `uncompleted_at`, `uncompleted_by`
- `can_uncomplete` (computed)

**Updated Validation in `SalaryPeriodCreateAsyncSerializer`:**
- All previous periods must be COMPLETED before creating new period

#### [apps/payroll/api/serializers/payroll_slip.py](../apps/payroll/api/serializers/payroll_slip.py)

**New Fields in `PayrollSlipSerializer`:**
- `payment_period`, `is_carried_over`
- `hold_reason`, `held_at`, `held_by`

### Tests

#### [apps/payroll/tests/test_salary_period_management.py](../apps/payroll/tests/test_salary_period_management.py) (NEW)

Comprehensive test coverage (~500 lines, 28 test methods):

| Test Class | Coverage |
|------------|----------|
| `TestSalaryPeriodComplete` | Complete flow, payment_period assignment |
| `TestSalaryPeriodUncomplete` | Uncomplete flow, validation |
| `TestPayrollSlipHold` | Hold functionality |
| `TestPayrollSlipUnhold` | Unhold and recalculation |
| `TestIsCarriedOverProperty` | is_carried_over property |
| `TestPaymentTableLogic` | Table 1 queryset |
| `TestDeferredTableLogic` | Table 2 queryset |
| `TestCRUDProtection` | Period protection signals |
| `TestStatisticsUpdate` | Statistics calculation |
| `TestPayrollCalculationServiceUpdates` | Service behavior |

## Usage Guide

### Complete a Salary Period

```python
# Via model method
period.complete(user=request.user)

# Via API
POST /api/v1/payroll/salary-periods/{id}/complete/
```

**Effects:**
1. Status changes to COMPLETED
2. All READY slips marked as DELIVERED
3. `payment_period` set for DELIVERED slips
4. Statistics updated

### Uncomplete a Salary Period

```python
# Via model method
if period.can_uncomplete():
    period.uncomplete(user=request.user)

# Via API
POST /api/v1/payroll/salary-periods/{id}/uncomplete/
```

**Requirements:**
- Period must be COMPLETED
- No newer COMPLETED period exists
- No DELIVERED slips in this payment period

### Hold a Payroll Slip

```python
# Via model method
slip.hold(user=request.user, reason="Waiting for document verification")

# Via API
POST /api/v1/payroll/payroll-slips/{id}/hold/
{
    "reason": "Waiting for document verification"
}
```

**Effects:**
1. Status changes to HOLD
2. Slip excluded from complete() operation
3. Records held_at, held_by, hold_reason

### Unhold a Payroll Slip

```python
# Via model method
slip.unhold(user=request.user)

# Via API
POST /api/v1/payroll/payroll-slips/{id}/unhold/
```

**Effects (depends on period status):**
- **ONGOING period:** Recalculates and sets READY/PENDING
- **COMPLETED period:** Recalculates and sets READY (carried over to next period)

### View Payment Table (Table 1)

```
GET /api/v1/payroll/salary-periods/{id}/ready-slips/
```

Returns slips to be paid in this period:
- ONGOING: READY + DELIVERED from current period
- COMPLETED: DELIVERED with payment_period = current

### View Deferred Table (Table 2)

```
GET /api/v1/payroll/salary-periods/{id}/not-ready-slips/
```

Returns slips NOT paid in this period:
- ONGOING: PENDING + HOLD + carried-over DELIVERED
- COMPLETED: Empty

## Business Rules Summary

1. **Period Protection:** No CRUD operations on completed period data (except penalty payment)
2. **Payment Period:** Once DELIVERED, slip tracks which period it was paid in
3. **Carried Over:** Slips with `payment_period != salary_period` are carried over
4. **HOLD Preservation:** HOLD status preserved during recalculation
5. **Penalty Payment:** Only exception to CRUD protection - allows status UNPAID→PAID
6. **Statistics:** Automatically updated with payment/deferred counts and totals

## API Response Examples

### Salary Period Response

```json
{
    "success": true,
    "data": {
        "id": 1,
        "name": "T01/2025",
        "status": "COMPLETED",
        "completed_at": "2025-01-31T23:59:59Z",
        "completed_by": 1,
        "payment_count": 45,
        "payment_total": "450000000.00",
        "deferred_count": 3,
        "deferred_total": "30000000.00",
        "can_uncomplete": true
    }
}
```

### Payroll Slip Response

```json
{
    "success": true,
    "data": {
        "id": 1,
        "employee": {...},
        "salary_period": 1,
        "payment_period": 2,
        "status": "DELIVERED",
        "is_carried_over": true,
        "hold_reason": null,
        "held_at": null,
        "held_by": null,
        "net_salary": "10000000.00"
    }
}
```

## Running Tests

```bash
# Run all salary period management tests
ENVIRONMENT=test poetry run pytest apps/payroll/tests/test_salary_period_management.py -v

# Run specific test class
ENVIRONMENT=test poetry run pytest apps/payroll/tests/test_salary_period_management.py::TestSalaryPeriodComplete -v
```

## Migration Notes

After deployment, run migrations:

```bash
poetry run python manage.py migrate payroll
```

The data migration (0005) will automatically:
- Set `payment_period = salary_period` for all existing DELIVERED slips
- This ensures backward compatibility with existing data
