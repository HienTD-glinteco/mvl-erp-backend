# Payroll Signals Documentation

This document provides a comprehensive overview of all signals in the payroll app, organized by purpose.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Signal Categories](#signal-categories)
3. [Code Generation Signals](#code-generation-signals)
4. [KPI Assessment Signals](#kpi-assessment-signals)
5. [Payroll Recalculation Signals](#payroll-recalculation-signals)
6. [Statistics Update Signals](#statistics-update-signals)
7. [Deadline Validation Signals](#deadline-validation-signals)
8. [Signal Flow Diagrams](#signal-flow-diagrams)
9. [Best Practices](#best-practices)

---

## Architecture Overview

The payroll signals are organized into 5 logical modules to improve maintainability and prevent duplicate processing:

```
apps/payroll/signals/
├── __init__.py                    # Imports all signal modules
├── code_generation.py             # Auto-code generation for models
├── kpi_assessment.py              # KPI assessment status and notifications
├── payroll_recalculation.py       # Triggers for payroll recalculation
├── statistics_update.py           # SalaryPeriod statistics updates
└── deadline_validation.py         # Business deadline enforcement
```

### Key Design Principles

1. **Single Responsibility**: Each signal file handles one specific concern
2. **No Duplicate Updates**: Centralized statistics updates prevent redundant calculations
3. **Async Processing**: Heavy calculations use Celery tasks
4. **Clear Trigger Points**: Well-defined events trigger specific actions

---

## Signal Categories

### 1. Code Generation (`code_generation.py`)

**Purpose**: Automatically generate unique codes for payroll models after creation.

**Models Covered**:
- `SalaryPeriod`: `SP_{YYYYMM}` (e.g., `SP_202401`)
- `PayrollSlip`: `PS_{YYYYMM}_{seq}` (e.g., `PS_202401_0001`)
- `SalesRevenue`: `SR-{YYYYMM}-{seq}` (e.g., `SR-202401-0001`)
- `RecoveryVoucher`: `RV-{YYYYMM}-{seq}` (e.g., `RV-202401-0001`)
- `PenaltyTicket`: `RVF-{YYYYMM}-{seq}` (e.g., `RVF-202401-0001`)

**Mechanism**: Uses `libs.code_generation.register_auto_code_signal()` with custom code generators.

---

### 2. KPI Assessment (`kpi_assessment.py`)

**Purpose**: Manage KPI assessment lifecycle, status updates, and notifications.

#### Signals

##### `handle_employee_kpi_assessment_post_save`
- **Sender**: `EmployeeKPIAssessment`
- **Trigger**: `post_save`
- **Actions**:
  1. Update department assessment status
  2. Update assessment status (NEW → WAITING_MANAGER → COMPLETED)
  3. Send notification to employee on creation
  4. Trigger payroll recalculation

**Status Flow**:
```
NEW (created)
  ↓ (employee completes self-assessment)
WAITING_MANAGER (total_employee_score set)
  ↓ (manager completes assessment)
COMPLETED (total_manager_score set)
```

##### `create_kpi_assessment_for_new_employee`
- **Sender**: `hrm.Employee`
- **Trigger**: `post_save` (created=True)
- **Actions**:
  1. Check if KPI period exists for employee's start_date month
  2. Determine target (sales/backoffice) based on department function
  3. Create assessment with criteria items
  4. Calculate initial scores

---

### 3. Payroll Recalculation (`payroll_recalculation.py`)

**Purpose**: Queue async tasks to recalculate payroll slips when source data changes.

#### Signal Flow

```
Data Change (Contract, Timesheet, etc.)
  ↓
Signal Triggered
  ↓
recalculate_payroll_slip_task.delay()  [Async Celery Task]
  ↓
Task Updates PayrollSlip
  ↓
PayrollSlip.post_save Signal
  ↓
SalaryPeriod.update_statistics()
```

#### Signals

| Signal | Sender | Trigger | Affected Payroll Fields |
|--------|--------|---------|------------------------|
| `on_contract_saved` | `Contract` | `post_save` (status=ACTIVE) | Base salary, allowances |
| `on_timesheet_saved` | `EmployeeMonthlyTimesheet` | `post_save` | Attendance-based calculations |
| `on_sales_revenue_saved` | `SalesRevenue` | `post_save` | Business progressive salary |
| `on_travel_expense_saved` | `TravelExpense` | `post_save` | Travel allowances |
| `on_travel_expense_deleted` | `TravelExpense` | `post_delete` | Travel allowances |
| `on_recovery_voucher_saved` | `RecoveryVoucher` | `post_save` | Recovery deductions |
| `on_recovery_voucher_deleted` | `RecoveryVoucher` | `post_delete` | Recovery deductions |
| `on_penalty_ticket_saved` | `PenaltyTicket` | `post_save` (status changed) | Blocking status |
| `on_dependent_changed` | `EmployeeDependent` | `post_save`, `post_delete` | Tax calculations |

**Note**: These signals only trigger recalculation. Statistics updates happen automatically in `statistics_update.py`.

---

### 4. Statistics Update (`statistics_update.py`)

**Purpose**: Maintain accurate real-time statistics on `SalaryPeriod` model.

#### Architecture - Central Update Point

All statistics updates are centralized through `PayrollSlip` signals to prevent duplicates:

```
[Data Changes] → [Recalculation Task] → [PayrollSlip Saved] → [Statistics Updated]
     OR
[Direct Create/Delete] → [Statistics Updated]
```

#### Statistics Tracked

| Field | Description |
|-------|-------------|
| `pending_count` | PayrollSlips with PENDING status |
| `ready_count` | PayrollSlips with READY status |
| `hold_count` | PayrollSlips with HOLD status |
| `delivered_count` | PayrollSlips with DELIVERED status |
| `total_gross_income` | Sum of all gross_income |
| `total_net_salary` | Sum of all net_salary |
| `employees_with_penalties_count` | Employees with unpaid penalties |
| `employees_paid_penalties_count` | Employees with paid penalties |
| `employees_need_recovery_count` | Employees with recovery vouchers |
| `employees_with_travel_expense_count` | Employees with travel expenses |
| `employees_need_resend_email_count` | Employees needing email resend |

#### Signals

##### `update_salary_period_stats_on_payroll_change`
- **Sender**: `PayrollSlip`
- **Trigger**: `post_save`
- **Conditions**:
  - Always on creation
  - On update if `status`, `gross_income`, `net_salary`, or `need_resend_email` changed

##### `update_salary_period_stats_on_payroll_delete`
- **Sender**: `PayrollSlip`
- **Trigger**: `post_delete`

##### Direct Statistics Updates (Creation/Deletion Only)
- `on_penalty_ticket_created` / `on_penalty_ticket_deleted`
- `on_travel_expense_created` / `on_travel_expense_deleted_stats`
- `on_recovery_voucher_created` / `on_recovery_voucher_deleted_stats`

**Why separate?** Creation/deletion need immediate stats update. Updates trigger recalculation which updates stats via PayrollSlip, preventing duplicates.

---

### 5. Deadline Validation (`deadline_validation.py`)

**Purpose**: Enforce business rules for proposal and KPI assessment deadlines.

#### Signals

##### `validate_proposal_salary_deadline`
- **Sender**: `hrm.Proposal`
- **Trigger**: `pre_save`
- **Validation**: Blocks creation of salary-affecting proposals after `SalaryPeriod.proposal_deadline`
- **Applies to**:
  - `POST_MATERNITY_BENEFITS`
  - `OVERTIME_WORK` (proposal creation only, entries validated separately)
  - `PAID_LEAVE`
  - `UNPAID_LEAVE`
  - `MATERNITY_LEAVE`
  - `TIMESHEET_ENTRY_COMPLAINT`

**Logic**:
1. Only validates on creation (not updates/approvals)
2. Determines affected month from proposal date fields
3. For `OVERTIME_WORK`: Skips validation as entries are added after proposal creation
4. Checks if salary period exists and has deadline
5. Raises `ValidationError` if today > deadline

##### `validate_overtime_entry_deadline`
- **Sender**: `hrm.ProposalOvertimeEntry`
- **Trigger**: `pre_save`
- **Validation**: Blocks creation of overtime entries after `SalaryPeriod.proposal_deadline`

**Logic**:
1. Validates on both creation and update
2. Determines affected month from `entry.date`
3. Checks if salary period exists and has deadline
4. Raises `ValidationError` if today > deadline

**Note**: This complements `validate_proposal_salary_deadline` which skips overtime proposals during creation (since entries are added after proposal is saved).

##### `validate_kpi_assessment_deadline`
- **Sender**: `EmployeeKPIAssessment`
- **Trigger**: `pre_save`
- **Validation**: Blocks employee/manager scoring after `SalaryPeriod.kpi_assessment_deadline`
- **Exemption**: HRM can always edit (hrm_assessed=True)

**Logic**:
1. Only validates on update (not creation)
2. Detects manager scoring by checking `manager_assessment_date` or `total_manager_score` changes
3. Allows HRM edits (`hrm_assessed` or `grade_hrm` changed)
4. Raises `ValidationError` if today > deadline

---

## Signal Flow Diagrams

### Complete Data Change Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ DATA CHANGE EVENT                                                │
├─────────────────────────────────────────────────────────────────┤
│ Contract, Timesheet, KPI, SalesRevenue, TravelExpense, etc.    │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ RECALCULATION SIGNAL (payroll_recalculation.py)                 │
├─────────────────────────────────────────────────────────────────┤
│ recalculate_payroll_slip_task.delay(employee_id, month)        │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ CELERY TASK (Async)                                             │
├─────────────────────────────────────────────────────────────────┤
│ PayrollCalculationService.calculate()                           │
│ PayrollSlip.save(update_fields=[...])                           │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ PAYROLL SAVE SIGNAL (statistics_update.py)                      │
├─────────────────────────────────────────────────────────────────┤
│ Check if stats-triggering fields changed                        │
│ SalaryPeriod.update_statistics()                                │
└─────────────────────────────────────────────────────────────────┘
```

### Direct Statistics Update Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ DIRECT CREATE/DELETE                                             │
├─────────────────────────────────────────────────────────────────┤
│ PenaltyTicket, TravelExpense, RecoveryVoucher (create/delete)   │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ STATISTICS SIGNAL (statistics_update.py)                         │
├─────────────────────────────────────────────────────────────────┤
│ SalaryPeriod.update_statistics() (immediate)                    │
└─────────────────────────────────────────────────────────────────┘
```

### KPI Assessment Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ KPI ASSESSMENT SAVED                                             │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ KPI SIGNAL (kpi_assessment.py)                                   │
├─────────────────────────────────────────────────────────────────┤
│ 1. Update department assessment status                           │
│ 2. Update assessment status (NEW/WAITING_MANAGER/COMPLETED)     │
│ 3. Send notification (if created)                                │
│ 4. Trigger recalculate_payroll_slip_task                        │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ↓
              (Continues with recalculation flow above)
```

---

## Best Practices

### 1. Avoid Recursive Signals

**Problem**: Signal triggers save which triggers same signal infinitely.

**Solution**: Use `update_fields` parameter or update via QuerySet:

```python
# ❌ Bad - Can cause infinite loop
instance.status = new_status
instance.save()

# ✅ Good - Avoids triggering signal
Model.objects.filter(pk=instance.pk).update(status=new_status)
```

### 2. Check `update_fields` to Prevent Duplicate Work

```python
@receiver(post_save, sender=PayrollSlip)
def my_signal(sender, instance, **kwargs):
    update_fields = kwargs.get("update_fields")

    # Only trigger if specific fields changed
    if update_fields is None or "status" in update_fields:
        do_something()
```

### 3. Handle DoesNotExist Gracefully

```python
try:
    period = SalaryPeriod.objects.get(month=instance.month)
    period.update_statistics()
except SalaryPeriod.DoesNotExist:
    pass  # Period might not exist yet
```

### 4. Use Async Tasks for Heavy Operations

```python
# ❌ Bad - Blocks request
PayrollCalculationService.calculate(...)

# ✅ Good - Async processing
recalculate_payroll_slip_task.delay(employee_id, month)
```

### 5. Document Signal Dependencies

Always document what other signals might be triggered:

```python
def on_contract_saved(sender, instance, **kwargs):
    """Recalculate payroll when contract changes.

    Chain: Contract.save → recalculate_task → PayrollSlip.save
           → statistics update
    """
```

### 6. Avoid Duplicate Statistics Updates

**Architecture**:
- Data changes → Trigger recalculation task
- Task saves PayrollSlip
- PayrollSlip signal updates statistics

**Don't**:
```python
# ❌ Bad - Updates stats twice
@receiver(post_save, sender=Contract)
def on_contract_saved(sender, instance, **kwargs):
    recalculate_payroll_slip_task.delay(...)  # Will update stats
    period.update_statistics()  # Duplicate!
```

**Do**:
```python
# ✅ Good - Stats updated once via PayrollSlip signal
@receiver(post_save, sender=Contract)
def on_contract_saved(sender, instance, **kwargs):
    recalculate_payroll_slip_task.delay(...)
```

---

## Debugging Signals

### Enable Signal Logging

Add to your signal handlers:

```python
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=MyModel)
def my_signal(sender, instance, **kwargs):
    logger.info(f"Signal triggered for {instance}, created={kwargs.get('created')}")
```

### Check Signal Registration

```python
from django.db.models import signals
from apps.payroll.models import PayrollSlip

# List all signals connected to a model
print(signals.post_save.receivers)
```

### Test Signals in Isolation

```python
from unittest.mock import patch

@patch('apps.payroll.tasks.recalculate_payroll_slip_task.delay')
def test_contract_triggers_recalculation(mock_task):
    contract = Contract.objects.create(...)
    mock_task.assert_called_once()
```

---

## Migration Guide

If you need to add new signals:

1. **Identify the category**: Code generation, KPI, recalculation, statistics, or validation?
2. **Add to appropriate file**: Place in the correct module
3. **Update `__init__.py`**: If creating a new category, import it
4. **Document**: Add to this file's relevant section
5. **Test**: Ensure no duplicate processing occurs
6. **Review dependencies**: Check if it affects other signals

---

## FAQ

**Q: Why are statistics updated multiple times for some operations?**

A: Only creation/deletion of PenaltyTicket, TravelExpense, and RecoveryVoucher trigger immediate stats updates. Their updates trigger recalculation which updates stats via PayrollSlip. This is by design for user experience (immediate feedback on creation).

**Q: How do I prevent a signal from running in tests?**

A: Use Django's `@override_settings` or mock the signal:

```python
from unittest.mock import patch

@patch('apps.payroll.signals.payroll_recalculation.on_contract_saved')
def test_something(mock_signal):
    # Signal won't run
    Contract.objects.create(...)
```

**Q: Can signals cause performance issues?**

A: Yes, if not designed carefully. Our architecture uses:
- Async tasks for heavy operations
- Conditional execution (`update_fields` checks)
- Centralized statistics updates to avoid duplicates

**Q: What happens if a Celery task fails?**

A: Tasks should be idempotent and retryable. Check Celery logs and retry failed tasks manually if needed.

---

## Summary

The payroll signals architecture is designed for:
- **Clarity**: Each file has a single, well-defined purpose
- **Performance**: Heavy operations are async
- **Reliability**: No duplicate processing
- **Maintainability**: Easy to understand and modify

When modifying signals, always consider the entire flow and ensure you're not creating duplicates or missing critical updates.
