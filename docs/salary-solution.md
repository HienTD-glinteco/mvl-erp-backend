# Salary Period Management - Solution Document

## 1. Executive Summary

This document outlines the detailed solution for implementing new salary period management features including:
- Lock/Unlock (Complete/Uncomplete) functionality
- Hold/Unhold payroll slip functionality
- Two-table display system (Payment Table & Deferred Table)
- Enhanced business rules for salary period lifecycle

---

## 2. Core Concepts & Definitions

### 2.1 Key Terminology

| Term | Vietnamese | Description |
|------|-----------|-------------|
| **Table 1 (Payment Table)** | Bảng 1 | Payroll slips that are paid or will be paid in this period |
| **Table 2 (Deferred Table)** | Bảng 2 | Payroll slips that belong to a period but were NOT paid in that period (includes PENDING, HOLD, and READY slips if period is COMPLETED) |
| **Lock/Complete** | Khóa/Chuyển kế toán | Mark period as completed, transfer to accounting |
| **Unlock/Uncomplete** | Mở khóa | Reopen a completed period (with restrictions) |
| **Hold** | Tạm giữ lương | Temporarily hold salary payment |
| **Unhold** | Bỏ tạm giữ | Release held salary |
| **Payment Period** | Kỳ chi trả | The period when a payroll slip is actually paid |
| **Salary Period** | Kỳ lương | The period a payroll slip belongs to |

### 2.2 Table Logic by Period Status

#### When Period is ONGOING (Chưa khóa)

| Table | Contains | Status Filter |
|-------|----------|---------------|
| **Table 1** | Slips ready to be paid | `READY` |
| **Table 2** | Slips not ready | `PENDING`, `HOLD` |

#### When Period is COMPLETED (Đã khóa)

| Table | Contains | Status Filter |
|-------|----------|---------------|
| **Table 1** | Slips that WERE paid in this period | `DELIVERED` (where `payment_period` = this period) |
| **Table 2** | Slips that belong to this period but were NOT paid | `PENDING`, `HOLD`, `READY` |

**Important**: When a period is COMPLETED:
- `READY` slips in Table 2 are those that became ready AFTER the period was completed (e.g., after penalty payment)
- These READY slips will appear in **Table 1 of the current ONGOING period** for actual payment
- They stay in Table 2 of their original period for historical tracking

### 2.3 Payroll Slip Status Flow

```
                                    ┌─────────────────────────────────────────────┐
                                    │                                             │
                                    ▼                                             │
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌───────────┐                     │
│ PENDING │────▶│  READY  │────▶│  HOLD   │────▶│ DELIVERED │                     │
└─────────┘     └─────────┘     └─────────┘     └───────────┘                     │
     │               │               │                                             │
     │               │               │                                             │
     │               ▼               │                                             │
     │          ┌─────────────────────┐                                           │
     │          │ When period COMPLETE│                                           │
     │          │ READY → DELIVERED   │                                           │
     │          └─────────────────────┘                                           │
     │                                                                             │
     └─────────────────────────────────────────────────────────────────────────────┘
                        (Unhold triggers recalculation & status update)
```

### 2.4 Salary Period Status Flow

```
┌─────────┐                    ┌───────────┐
│ ONGOING │───── complete() ──▶│ COMPLETED │
└─────────┘                    └───────────┘
     ▲                              │
     │                              │
     └──── uncomplete() ◀───────────┘
           (only if no newer periods exist)
```

---

## 3. Database Schema Changes

### 3.1 SalaryPeriod Model Updates

```python
# File: apps/payroll/models/salary_period.py

class SalaryPeriod(AutoCodeMixin, ColoredValueMixin, BaseModel):
    """Extended with lock tracking fields."""

    # Existing fields remain unchanged

    # New fields for uncomplete tracking
    uncompleted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Uncompleted At"),
        help_text="Timestamp when period was uncompleted/unlocked"
    )

    uncompleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uncompleted_salary_periods",
        verbose_name=_("Uncompleted By"),
        help_text="User who uncompleted the period"
    )

    # Statistics for deferred slips (Table 2)
    deferred_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Deferred Count"),
        help_text="Count of payroll slips deferred to next period"
    )

    deferred_total = models.DecimalField(
        max_digits=20,
        decimal_places=0,
        default=0,
        verbose_name=_("Deferred Total"),
        help_text="Total net salary of deferred payroll slips"
    )
```

### 3.2 PayrollSlip Model Updates

```python
# File: apps/payroll/models/payroll_slip.py

class PayrollSlip(AutoCodeMixin, ColoredValueMixin, BaseModel):
    """Extended with payment period tracking."""

    # Existing fields remain unchanged

    # New field: Payment Period (kỳ chi trả)
    payment_period = models.ForeignKey(
        "SalaryPeriod",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_slips",
        verbose_name=_("Payment Period"),
        help_text="The period when this slip is actually paid (may differ from salary_period)"
    )

    # Hold tracking
    hold_reason = models.CharField(
        max_length=500,
        blank=True,
        default="",
        verbose_name=_("Hold Reason"),
        help_text="Reason for holding the salary"
    )

    held_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Held At"),
        help_text="Timestamp when slip was put on hold"
    )

    held_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="held_payroll_slips",
        verbose_name=_("Held By"),
    )

    # Derived property - no database field needed
    @property
    def is_carried_over(self) -> bool:
        """Check if slip is being paid in a different period than it belongs to.

        Returns True if payment_period differs from salary_period.
        This happens when a slip becomes READY after its period was COMPLETED
        (e.g., after penalty payment) and will be paid in a later period.
        """
        return (
            self.payment_period_id is not None and
            self.payment_period_id != self.salary_period_id
        )
```

### 3.3 Migration Plan

```python
# Migration 1: Add new fields to SalaryPeriod (uncompleted_at, uncompleted_by, deferred_count, deferred_total)
# Migration 2: Add new fields to PayrollSlip (payment_period, hold_reason, held_at, held_by)
# Migration 3: Data migration to set payment_period = salary_period for existing DELIVERED records
```

**Note**: `is_carried_over` is a derived property (not a database field) computed as:
`payment_period_id != salary_period_id`

---

## 4. Business Logic Implementation

### 4.1 Complete (Lock) Salary Period

**File**: `apps/payroll/models/salary_period.py`

```python
def complete(self, user=None):
    """Complete the salary period and transfer to accounting.

    Business Rules:
    1. All READY slips → DELIVERED status
    2. All PENDING/HOLD slips remain (deferred to Table 2)
    3. Update payment_period for READY slips to current period
    4. Update statistics

    Args:
        user: User completing the period
    """
    from django.utils import timezone
    from .payroll_slip import PayrollSlip

    now = timezone.now()

    # Update all READY slips to DELIVERED
    ready_slips = self.payroll_slips.filter(status=PayrollSlip.Status.READY)
    ready_slips.update(
        status=PayrollSlip.Status.DELIVERED,
        delivered_at=now,
        delivered_by=user,
        payment_period=self  # Payment period = this period
    )

    # Mark period as completed
    self.status = self.Status.COMPLETED
    self.completed_at = now
    self.completed_by = user
    self.save(update_fields=["status", "completed_at", "completed_by", "updated_at"])

    # Update statistics (including deferred count)
    self.update_statistics()
```

### 4.2 Uncomplete (Unlock) Salary Period

**File**: `apps/payroll/models/salary_period.py`

```python
def can_uncomplete(self) -> tuple[bool, str]:
    """Check if period can be uncompleted.

    Returns:
        Tuple of (can_uncomplete: bool, reason: str)
    """
    # Rule: Cannot uncomplete if newer periods exist
    newer_periods = SalaryPeriod.objects.filter(month__gt=self.month).exists()
    if newer_periods:
        return False, "Cannot uncomplete: newer salary periods exist"

    return True, ""

def uncomplete(self, user=None):
    """Uncomplete/unlock the salary period.

    Business Rules:
    1. Only allowed if no newer periods exist
    2. Status changes to ONGOING
    3. Payroll slip statuses remain unchanged (DELIVERED stays DELIVERED)
    4. Future CRUD on related objects will trigger recalculation

    Args:
        user: User uncompleting the period

    Raises:
        ValidationError: If uncomplete is not allowed
    """
    from django.core.exceptions import ValidationError
    from django.utils import timezone

    can, reason = self.can_uncomplete()
    if not can:
        raise ValidationError(reason)

    # Change status to ONGOING
    self.status = self.Status.ONGOING
    self.uncompleted_at = timezone.now()
    self.uncompleted_by = user
    # Keep completed_at/completed_by for audit trail
    self.save(update_fields=["status", "uncompleted_at", "uncompleted_by", "updated_at"])
```

### 4.3 Hold Payroll Slip

**File**: `apps/payroll/models/payroll_slip.py`

```python
def hold(self, reason: str, user=None):
    """Put payroll slip on hold.

    Business Rules:
    1. Only PENDING or READY slips can be held
    2. Status changes to HOLD
    3. Reason is required

    Args:
        reason: Reason for holding
        user: User performing the hold

    Raises:
        ValidationError: If hold is not allowed
    """
    from django.core.exceptions import ValidationError
    from django.utils import timezone

    if self.status not in [self.Status.PENDING, self.Status.READY]:
        raise ValidationError(f"Cannot hold slip with status {self.status}")

    if not reason:
        raise ValidationError("Hold reason is required")

    self.status = self.Status.HOLD
    self.hold_reason = reason
    self.status_note = f"Hold: {reason}"
    self.held_at = timezone.now()
    self.held_by = user
    self.save(update_fields=[
        "status", "hold_reason", "status_note",
        "held_at", "held_by", "updated_at"
    ])
```

### 4.4 Unhold Payroll Slip

**File**: `apps/payroll/models/payroll_slip.py`

```python
def unhold(self, user=None):
    """Release held payroll slip.

    Business Rules:
    1. Only HOLD slips can be unholded
    2. Triggers recalculation
    3. Status determined by recalculation (READY or PENDING)
    4. If salary period is ONGOING (current period): slip goes to Table 1
    5. If salary period is COMPLETED (old period):
       - Slip stays in Table 2 of old period
       - AND appears in Table 1 of current ONGOING period

    Args:
        user: User performing the unhold

    Raises:
        ValidationError: If unhold is not allowed
    """
    from django.core.exceptions import ValidationError

    if self.status != self.Status.HOLD:
        raise ValidationError(f"Cannot unhold slip with status {self.status}")

    # Clear hold info
    self.hold_reason = ""
    self.status_note = ""
    self.held_at = None
    self.held_by = None

    # Handle based on whether salary period is ongoing or completed
    if self.salary_period.status == SalaryPeriod.Status.COMPLETED:
        # Old period case: need to move to current period
        self._handle_unhold_from_completed_period(user)
    else:
        # Current period case: just recalculate
        self._recalculate_and_update_status()

    self.save()

def _handle_unhold_from_completed_period(self, user=None):
    """Handle unhold for slip from a completed period.

    Sets payment_period to current ONGOING period so slip appears in Table 1.
    The is_carried_over property will automatically return True since
    payment_period != salary_period.
    """
    # Find current ONGOING period
    current_period = SalaryPeriod.objects.filter(
        status=SalaryPeriod.Status.ONGOING
    ).order_by('-month').first()

    if current_period:
        # Set payment_period to current period (Table 1 of new period)
        # is_carried_over property will automatically be True
        self.payment_period = current_period

    # Recalculate status
    self._recalculate_and_update_status()

def _recalculate_and_update_status(self):
    """Recalculate and determine new status."""
    from apps.payroll.services.payroll_calculation import PayrollCalculationService

    calculator = PayrollCalculationService(self)
    calculator.calculate()
    # Status is determined by calculator._determine_final_status()
```

### 4.5 Salary Period Creation Validation

**File**: `apps/payroll/api/serializers/salary_period.py`

```python
def validate_month(self, value):
    """Validate month for new salary period creation.

    Business Rules:
    1. Cannot create if period already exists
    2. Cannot create if ANY previous period is not COMPLETED
    """
    from datetime import date

    try:
        month, year = value.split("/")
        target_month = date(int(year), int(month), 1)
    except (ValueError, AttributeError):
        raise serializers.ValidationError(
            "Invalid month format. Use n/YYYY (e.g., 1/2025, 12/2025)"
        )

    # Check if period already exists
    if SalaryPeriod.objects.filter(month=target_month).exists():
        raise serializers.ValidationError(
            "Salary period already exists for this month"
        )

    # NEW RULE: ALL previous periods must be completed
    uncompleted_periods = SalaryPeriod.objects.filter(
        month__lt=target_month,
        status=SalaryPeriod.Status.ONGOING
    )

    if uncompleted_periods.exists():
        periods_str = ", ".join([
            p.month.strftime("%-m/%Y") for p in uncompleted_periods
        ])
        raise serializers.ValidationError(
            f"Cannot create new period. The following periods are not completed: {periods_str}"
        )

    return f"{target_month.year}-{target_month.month:02d}"
```

---

## 5. API Endpoints

### 5.1 Salary Period Actions

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/salary-periods/{id}/complete/` | POST | Lock/Complete period |
| `/api/salary-periods/{id}/uncomplete/` | POST | Unlock/Uncomplete period |
| `/api/salary-periods/{id}/payment-table/` | GET | Get Table 1 (payment slips) |
| `/api/salary-periods/{id}/deferred-table/` | GET | Get Table 2 (deferred slips) |

### 5.2 Payroll Slip Actions

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/payroll-slips/{id}/hold/` | POST | Hold payroll slip |
| `/api/payroll-slips/{id}/unhold/` | POST | Unhold payroll slip |

### 5.3 New ViewSets

**File**: `apps/payroll/api/views/salary_period.py`

```python
@extend_schema(
    summary="Uncomplete salary period",
    description="Unlock a completed salary period. Only allowed if no newer periods exist.",
    tags=["10.6: Salary Periods"],
)
@action(detail=True, methods=["post"])
def uncomplete(self, request, pk=None):
    """Uncomplete/unlock the salary period."""
    period = self.get_object()

    can, reason = period.can_uncomplete()
    if not can:
        return Response(
            {"error": reason},
            status=status.HTTP_400_BAD_REQUEST
        )

    period.uncomplete(user=request.user)

    return Response({
        "id": period.id,
        "status": period.status,
        "uncompleted_at": period.uncompleted_at,
        "message": "Period successfully uncompleted"
    })


class SalaryPeriodPaymentTableViewSet(BaseReadOnlyModelViewSet):
    """ViewSet for Table 1 (Payment Table) - slips to be paid in this period.

    Returns:
    - For ONGOING period: READY slips from this period + carried over READY slips
    - For COMPLETED period: DELIVERED slips where payment_period = this period
    """

    def get_queryset(self):
        pk = self.kwargs.get("pk")
        if not pk:
            return PayrollSlip.objects.none()

        try:
            period = SalaryPeriod.objects.get(pk=pk)
        except SalaryPeriod.DoesNotExist:
            return PayrollSlip.objects.none()

        if period.status == SalaryPeriod.Status.ONGOING:
            # Table 1 for ONGOING: READY slips + carried over
            return PayrollSlip.objects.filter(
                Q(salary_period=period, status=PayrollSlip.Status.READY) |
                Q(payment_period=period, status=PayrollSlip.Status.READY)
            ).select_related("employee", "salary_period", "payment_period")
        else:
            # Table 1 for COMPLETED: DELIVERED slips paid in this period
            return PayrollSlip.objects.filter(
                payment_period=period,
                status=PayrollSlip.Status.DELIVERED
            ).select_related("employee", "salary_period", "payment_period")


class SalaryPeriodDeferredTableViewSet(BaseReadOnlyModelViewSet):
    """ViewSet for Table 2 (Deferred Table) - slips not paid in this period.

    Returns:
    - For ONGOING period: PENDING/HOLD slips from this period
    - For COMPLETED period: All non-DELIVERED slips (PENDING/HOLD/READY) that belonged
      to this period but weren't paid in this period. READY slips appear here if they
      became ready AFTER the period was completed (e.g., after penalty payment).
    """

    def get_queryset(self):
        pk = self.kwargs.get("pk")
        if not pk:
            return PayrollSlip.objects.none()

        try:
            period = SalaryPeriod.objects.get(pk=pk)
        except SalaryPeriod.DoesNotExist:
            return PayrollSlip.objects.none()

        if period.status == SalaryPeriod.Status.ONGOING:
            # Table 2 for ONGOING: PENDING/HOLD slips only
            return PayrollSlip.objects.filter(
                salary_period=period,
                status__in=[PayrollSlip.Status.PENDING, PayrollSlip.Status.HOLD]
            ).select_related("employee", "salary_period", "payment_period")
        else:
            # Table 2 for COMPLETED: All non-DELIVERED slips (PENDING/HOLD/READY)
            # READY slips here are those that became ready after period completion
            # (e.g., after paying penalties) - they will be paid in the next period
            return PayrollSlip.objects.filter(
                salary_period=period,
                status__in=[
                    PayrollSlip.Status.PENDING,
                    PayrollSlip.Status.HOLD,
                    PayrollSlip.Status.READY
                ]
            ).select_related("employee", "salary_period", "payment_period")
```

---

## 6. Signal & Trigger Updates

### 6.1 CRUD Protection for Completed Periods

**File**: `apps/payroll/signals/period_protection.py` (new file)

```python
"""Signal handlers to protect completed salary period data."""

from django.core.exceptions import ValidationError
from django.db.models.signals import pre_delete, pre_save
from django.dispatch import receiver

from apps.payroll.models import (
    PayrollSlip,
    PenaltyTicket,
    RecoveryVoucher,
    SalaryPeriod,
    SalesRevenue,
    TravelExpense,
)


def check_period_is_editable(month, model_name, exclude_penalty_payment=False):
    """Check if the salary period for the given month allows edits.

    Args:
        month: Date representing the month
        model_name: Name of the model being edited
        exclude_penalty_payment: If True, allow penalty status changes

    Raises:
        ValidationError: If period is completed and edits not allowed
    """
    from datetime import date

    month_first = date(month.year, month.month, 1)

    try:
        period = SalaryPeriod.objects.get(month=month_first)
    except SalaryPeriod.DoesNotExist:
        return  # No period, allow edit

    if period.status == SalaryPeriod.Status.COMPLETED:
        raise ValidationError(
            f"Cannot modify {model_name} for completed salary period {period.code}"
        )


@receiver(pre_save, sender=TravelExpense)
def protect_travel_expense_save(sender, instance, **kwargs):
    """Prevent TravelExpense modifications for completed periods."""
    check_period_is_editable(instance.month, "Travel Expense")


@receiver(pre_delete, sender=TravelExpense)
def protect_travel_expense_delete(sender, instance, **kwargs):
    """Prevent TravelExpense deletion for completed periods."""
    check_period_is_editable(instance.month, "Travel Expense")


@receiver(pre_save, sender=RecoveryVoucher)
def protect_recovery_voucher_save(sender, instance, **kwargs):
    """Prevent RecoveryVoucher modifications for completed periods."""
    check_period_is_editable(instance.month, "Recovery Voucher")


@receiver(pre_delete, sender=RecoveryVoucher)
def protect_recovery_voucher_delete(sender, instance, **kwargs):
    """Prevent RecoveryVoucher deletion for completed periods."""
    check_period_is_editable(instance.month, "Recovery Voucher")


@receiver(pre_save, sender=SalesRevenue)
def protect_sales_revenue_save(sender, instance, **kwargs):
    """Prevent SalesRevenue modifications for completed periods."""
    check_period_is_editable(instance.month, "Sales Revenue")


@receiver(pre_delete, sender=SalesRevenue)
def protect_sales_revenue_delete(sender, instance, **kwargs):
    """Prevent SalesRevenue deletion for completed periods."""
    check_period_is_editable(instance.month, "Sales Revenue")


# EXCEPTION: PenaltyTicket allows status changes (UNPAID → PAID)
@receiver(pre_save, sender=PenaltyTicket)
def protect_penalty_ticket_save(sender, instance, **kwargs):
    """Prevent PenaltyTicket modifications for completed periods.

    EXCEPTION: Allow status change from UNPAID to PAID (penalty payment)
    """
    if instance.pk:
        # Existing record - check if only status changed
        try:
            old_instance = PenaltyTicket.objects.get(pk=instance.pk)

            # Allow if only status changed from UNPAID to PAID
            if (old_instance.status == PenaltyTicket.Status.UNPAID and
                instance.status == PenaltyTicket.Status.PAID):
                # This is allowed - penalty payment
                return

            # Check if any field other than status/payment_date changed
            for field in ['employee_id', 'amount', 'month', 'violation_type',
                         'violation_count', 'note']:
                if getattr(old_instance, field) != getattr(instance, field):
                    check_period_is_editable(instance.month, "Penalty Ticket")
                    return
        except PenaltyTicket.DoesNotExist:
            pass
    else:
        # New record
        check_period_is_editable(instance.month, "Penalty Ticket")


@receiver(pre_delete, sender=PenaltyTicket)
def protect_penalty_ticket_delete(sender, instance, **kwargs):
    """Prevent PenaltyTicket deletion for completed periods."""
    check_period_is_editable(instance.month, "Penalty Ticket")
```

### 6.2 Auto-Recalculation on Uncompleted Period Changes

**File**: `apps/payroll/signals/model_lifecycle.py` (update)

```python
def should_trigger_recalculation(instance, month):
    """Check if recalculation should be triggered.

    Only triggers if:
    1. Salary period exists for the month
    2. Period is ONGOING (not completed)
    """
    from datetime import date

    month_first = date(month.year, month.month, 1)

    try:
        period = SalaryPeriod.objects.get(month=month_first)
        return period.status == SalaryPeriod.Status.ONGOING
    except SalaryPeriod.DoesNotExist:
        return False


# Update existing signal handlers to use this check
@receiver(post_save, sender=TravelExpense)
def on_travel_expense_saved(sender, instance, created, **kwargs):
    """Handle TravelExpense save - recalculate payroll if period is ONGOING."""
    from apps.payroll.tasks import recalculate_payroll_slip_task, update_period_statistics_task

    if should_trigger_recalculation(instance, instance.month):
        recalculate_payroll_slip_task.delay(
            str(instance.employee_id),
            instance.month.isoformat()
        )

    if created:
        update_period_statistics_task.delay(instance.month.isoformat())
```

---

## 7. Recalculation Logic Updates

### 7.1 PayrollCalculationService Updates

**File**: `apps/payroll/services/payroll_calculation.py`

```python
class PayrollCalculationService:
    """Updated service with hold status preservation."""

    def calculate(self):
        """Perform full payroll calculation.

        Updated Rules:
        - If slip is HOLD, calculate values but DON'T change status
        - If slip is DELIVERED, skip calculation entirely
        """
        # Skip if already delivered
        if self.slip.status == self.slip.Status.DELIVERED:
            return

        # Store original status if HOLD
        was_hold = self.slip.status == self.slip.Status.HOLD

        # ... existing calculation steps ...

        # Step 15: Determine final status (updated)
        if was_hold:
            # Preserve HOLD status - only update values, not status
            pass  # Don't call _determine_final_status
        else:
            self._determine_final_status(contract, timesheet)

        # ... rest of calculation ...

    def _determine_final_status(self, contract, timesheet):
        """Determine final status based on data availability.

        Updated to handle status transitions properly.
        """
        missing_reasons = []

        if not contract:
            missing_reasons.append("contract")
        if not timesheet:
            missing_reasons.append("timesheet")
        if self.slip.has_unpaid_penalty:
            missing_reasons.append(f"unpaid penalties ({self.slip.unpaid_penalty_count})")

        if missing_reasons:
            self.slip.status = self.slip.Status.PENDING
            self.slip.status_note = "Missing/blocking: " + ", ".join(missing_reasons)
        else:
            # Only change to READY if currently PENDING
            # Don't override HOLD or DELIVERED status
            if self.slip.status == self.slip.Status.PENDING:
                self.slip.status = self.slip.Status.READY
                self.slip.status_note = ""
```

### 7.2 Batch Recalculation for Period

**File**: `apps/payroll/tasks.py`

```python
@shared_task(bind=True)
def recalculate_salary_period_task(self, period_id):
    """Recalculate all payroll slips in a salary period.

    Updated Rules:
    - Include HOLD slips in recalculation (values only, not status)
    - Exclude DELIVERED slips
    """
    from apps.payroll.models import PayrollSlip, SalaryPeriod
    from apps.payroll.services.payroll_calculation import PayrollCalculationService

    try:
        salary_period = SalaryPeriod.objects.get(pk=period_id)

        if salary_period.status == SalaryPeriod.Status.COMPLETED:
            return {"error": "Cannot recalculate completed period"}

        # Get all slips except DELIVERED
        payroll_slips = salary_period.payroll_slips.exclude(
            status=PayrollSlip.Status.DELIVERED
        )
        total = payroll_slips.count()
        recalculated_count = 0

        for slip in payroll_slips:
            self.update_state(
                state="PROGRESS",
                meta={
                    "current": recalculated_count,
                    "total": total,
                    "status": "Recalculating payroll slips"
                },
            )

            calculator = PayrollCalculationService(slip)
            calculator.calculate()
            recalculated_count += 1

        # Update statistics
        salary_period.update_statistics()

        return {
            "period_id": salary_period.id,
            "recalculated_count": recalculated_count,
            "status": "completed",
        }
    except Exception as e:
        import sentry_sdk
        sentry_sdk.capture_exception(e)
        return {"error": str(e)}
```

---

## 8. Updated Statistics Calculation

**File**: `apps/payroll/models/salary_period.py`

```python
def update_statistics(self):
    """Update all statistics fields including new deferred counts."""
    from django.db.models import Count, Q, Sum
    from apps.payroll.models import PenaltyTicket, RecoveryVoucher, TravelExpense
    from .payroll_slip import PayrollSlip

    # ... existing statistics code ...

    # NEW: Update deferred statistics (Table 2)
    # For ONGOING: count PENDING/HOLD only
    # For COMPLETED: count PENDING/HOLD/READY (non-DELIVERED slips)
    if self.status == self.Status.ONGOING:
        deferred_statuses = [PayrollSlip.Status.PENDING, PayrollSlip.Status.HOLD]
    else:
        # COMPLETED period: include READY slips that weren't paid in this period
        deferred_statuses = [
            PayrollSlip.Status.PENDING,
            PayrollSlip.Status.HOLD,
            PayrollSlip.Status.READY
        ]

    deferred_stats = self.payroll_slips.filter(
        status__in=deferred_statuses
    ).aggregate(
        count=Count("id"),
        total=Sum("net_salary")
    )

    self.deferred_count = deferred_stats["count"] or 0
    self.deferred_total = deferred_stats["total"] or 0

    # Update payment table statistics (Table 1)
    if self.status == self.Status.ONGOING:
        payment_stats = PayrollSlip.objects.filter(
            Q(salary_period=self, status=PayrollSlip.Status.READY) |
            Q(payment_period=self, status=PayrollSlip.Status.READY)
        ).aggregate(
            count=Count("id"),
            total=Sum("net_salary")
        )
    else:
        payment_stats = PayrollSlip.objects.filter(
            payment_period=self,
            status=PayrollSlip.Status.DELIVERED
        ).aggregate(
            count=Count("id"),
            total=Sum("net_salary")
        )

    self.payment_count = payment_stats["count"] or 0
    self.payment_total = payment_stats["total"] or 0

    self.save(update_fields=[
        "employees_need_recovery",
        "employees_with_penalties",
        "employees_paid_penalties",
        "employees_with_travel",
        "employees_need_email",
        "pending_count",
        "ready_count",
        "hold_count",
        "delivered_count",
        "total_gross_income",
        "total_net_salary",
        "deferred_count",
        "deferred_total",
        "payment_count",
        "payment_total",
    ])
```

---

## 9. Penalty Ticket Flow (Special Case)

### 9.1 Penalty Payment in Completed Period

When a penalty is paid in a completed period:

1. **PenaltyTicket**: UNPAID → PAID (allowed as exception)
2. **PayrollSlip**: Recalculate → status may change from PENDING/HOLD to READY
3. **If slip becomes READY**: It appears in Table 1 of the next ONGOING period

```python
@receiver(post_save, sender=PenaltyTicket)
def on_penalty_ticket_paid(sender, instance, update_fields, **kwargs):
    """Handle penalty payment - may release held/pending slips."""
    if update_fields and "status" in update_fields:
        if instance.status == PenaltyTicket.Status.PAID:
            # Find affected payroll slip
            from apps.payroll.models import PayrollSlip, SalaryPeriod

            month_first = instance.month.replace(day=1)

            try:
                period = SalaryPeriod.objects.get(month=month_first)
                slip = PayrollSlip.objects.filter(
                    salary_period=period,
                    employee=instance.employee
                ).first()

                if slip and slip.status in [PayrollSlip.Status.PENDING,
                                             PayrollSlip.Status.HOLD]:
                    # Recalculate - this may change status
                    from apps.payroll.services.payroll_calculation import (
                        PayrollCalculationService
                    )

                    calculator = PayrollCalculationService(slip)
                    calculator.calculate()

                    # If now READY and period is COMPLETED,
                    # move to current period's Table 1
                    if (slip.status == PayrollSlip.Status.READY and
                        period.status == SalaryPeriod.Status.COMPLETED):

                        current_period = SalaryPeriod.objects.filter(
                            status=SalaryPeriod.Status.ONGOING
                        ).order_by('-month').first()

                        if current_period:
                            # Set payment_period - is_carried_over property
                            # will automatically be True
                            slip.payment_period = current_period
                            slip.save()

            except SalaryPeriod.DoesNotExist:
                pass
```

---

## 10. Frontend Integration Notes

### 10.1 Salary Period List View

```typescript
interface SalaryPeriod {
  id: number;
  code: string;
  month: string;
  status: 'ONGOING' | 'COMPLETED';

  // Statistics
  total_employees: number;
  pending_count: number;
  ready_count: number;
  hold_count: number;
  delivered_count: number;

  // NEW: Table statistics
  payment_count: number;
  payment_total: number;
  deferred_count: number;
  deferred_total: number;

  // Actions available
  can_complete: boolean;
  can_uncomplete: boolean;
}
```

### 10.2 Payroll Slip with Payment Period

```typescript
interface PayrollSlip {
  id: number;
  code: string;
  employee: Employee;

  salary_period: SalaryPeriod;  // Period the slip belongs to (never changes)
  payment_period: SalaryPeriod | null;  // Period when actually paid (may differ)

  status: 'PENDING' | 'READY' | 'HOLD' | 'DELIVERED';

  // Hold tracking
  hold_reason: string;
  held_at: string | null;
  held_by: User | null;

  // Derived (computed from salary_period vs payment_period)
  is_carried_over: boolean;  // True if payment_period != salary_period

  // Financial data
  gross_income: number;
  net_salary: number;
  // ... other fields
}
```

### 10.3 UI Button States

| Period Status | Available Actions |
|--------------|-------------------|
| ONGOING | Complete, Recalculate, Send Emails |
| COMPLETED (latest) | Uncomplete |
| COMPLETED (has newer) | None (locked) |

| Slip Status | Period ONGOING | Period COMPLETED |
|------------|----------------|------------------|
| PENDING | Hold | - |
| READY | Hold, Deliver | - |
| HOLD | Unhold | Unhold (moves to current period) |
| DELIVERED | - | - |

---

## 11. Implementation Phases

### Phase 1: Database & Models (3 days)
- [ ] Add new fields to SalaryPeriod model
- [ ] Add new fields to PayrollSlip model
- [ ] Create migrations
- [ ] Data migration for existing records

### Phase 2: Business Logic (5 days)
- [ ] Implement complete/uncomplete methods
- [ ] Implement hold/unhold methods
- [ ] Update PayrollCalculationService
- [ ] Implement CRUD protection signals

### Phase 3: API Endpoints (3 days)
- [ ] Add uncomplete endpoint
- [ ] Add unhold endpoint
- [ ] Add payment-table endpoint
- [ ] Add deferred-table endpoint
- [ ] Update serializers

### Phase 4: Testing (3 days)
- [ ] Unit tests for new business logic
- [ ] Integration tests for API endpoints
- [ ] Edge case testing (penalty payment, carry over)

### Phase 5: Documentation & Review (2 days)
- [ ] API documentation update
- [ ] Frontend integration guide
- [ ] Code review
- [ ] QA sign-off

**Total Estimated Time: 16 days**

---

## 12. Risk & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Data migration issues | High | Run migration in staging first, backup production |
| Performance on large datasets | Medium | Use async tasks, pagination |
| Signal infinite loops | High | Use update_fields, debouncing |
| Concurrent modification | Medium | Use select_for_update where needed |

---

## 13. Testing Scenarios

### 13.1 Complete/Uncomplete Flow
1. Create period → status = ONGOING
2. Complete → all READY = DELIVERED, status = COMPLETED
3. Uncomplete → status = ONGOING, slips unchanged
4. Create new period → old period cannot uncomplete

### 13.2 Hold/Unhold Flow
1. Hold READY slip → status = HOLD
2. Recalculate period → HOLD slip values updated, status unchanged
3. Unhold in ONGOING period → recalculate, status = READY/PENDING
4. Unhold in COMPLETED period → moves to current period Table 1

### 13.3 Penalty Payment Flow
1. Period COMPLETED with PENDING slip (unpaid penalty)
2. Pay penalty → PenaltyTicket status = PAID
3. Slip recalculates → status = READY
4. Slip appears in current ONGOING period's Table 1
5. Complete current period → slip status = DELIVERED

---

## 14. Appendix: Complete State Diagram

```
                    SALARY PERIOD LIFECYCLE
    ┌──────────────────────────────────────────────────────┐
    │                                                      │
    │  CREATE PERIOD                                       │
    │  (validates all previous COMPLETED)                  │
    │       │                                              │
    │       ▼                                              │
    │  ┌─────────┐                                         │
    │  │ ONGOING │◄────────────────────────┐               │
    │  └────┬────┘                         │               │
    │       │                              │               │
    │       │ complete()                   │ uncomplete()  │
    │       │                              │ (if no newer) │
    │       ▼                              │               │
    │  ┌───────────┐                       │               │
    │  │ COMPLETED │───────────────────────┘               │
    │  └───────────┘                                       │
    │                                                      │
    └──────────────────────────────────────────────────────┘

                    PAYROLL SLIP LIFECYCLE
    ┌──────────────────────────────────────────────────────┐
    │                                                      │
    │  CREATE SLIP                                         │
    │       │                                              │
    │       ▼                                              │
    │  ┌─────────┐      recalc (if data OK)   ┌─────────┐ │
    │  │ PENDING │─────────────────────────▶│  READY  │ │
    │  └────┬────┘                            └────┬────┘ │
    │       │                                      │      │
    │       │ hold()                       hold()  │      │
    │       │                                      │      │
    │       ▼                                      ▼      │
    │       └──────────────▶┌─────────┐◀──────────┘      │
    │                       │  HOLD   │                   │
    │                       └────┬────┘                   │
    │                            │                        │
    │                            │ unhold()               │
    │                            │ (recalc + move if      │
    │                            │  period COMPLETED)     │
    │                            │                        │
    │                            ▼                        │
    │                       ┌─────────┐                   │
    │  period.complete() ──▶│DELIVERED│                   │
    │  (READY→DELIVERED)    └─────────┘                   │
    │                                                      │
    └──────────────────────────────────────────────────────┘
```

---

*Document Version: 1.0*
*Created: 2026-01-10*
*Author: AI Assistant*
