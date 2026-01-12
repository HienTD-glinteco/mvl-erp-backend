"""Signal handlers to protect completed salary period data.

This module provides CRUD protection for payroll-related models when their
associated salary period is COMPLETED. Modifications are blocked to maintain
data integrity for completed periods.

Exceptions:
- PenaltyTicket: Status change from UNPAID to PAID is allowed (penalty payment)
"""

from datetime import date

from django.core.exceptions import ValidationError
from django.db.models.signals import pre_delete, pre_save
from django.dispatch import receiver

from apps.payroll.models import PenaltyTicket, RecoveryVoucher, SalaryPeriod, SalesRevenue, TravelExpense


def check_period_is_editable(month: date, model_name: str) -> None:
    """Check if the salary period for the given month allows edits.

    Args:
        month: Date representing the month
        model_name: Name of the model being edited

    Raises:
        ValidationError: If period is completed and edits not allowed
    """
    month_first = date(month.year, month.month, 1)

    try:
        period = SalaryPeriod.objects.get(month=month_first)
    except SalaryPeriod.DoesNotExist:
        return  # No period, allow edit

    if period.status == SalaryPeriod.Status.COMPLETED:
        raise ValidationError(f"Cannot modify {model_name} for completed salary period {period.code}")


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


@receiver(pre_save, sender=PenaltyTicket)
def protect_penalty_ticket_save(sender, instance, **kwargs):
    """Prevent PenaltyTicket modifications for completed periods.

    EXCEPTION: Allow status change from UNPAID to PAID (penalty payment).
    This is a special case where users can pay penalties even after the
    period is completed, which may trigger the payroll slip to become READY.
    """
    if instance.pk:
        # Existing record - check if only status changed
        try:
            old_instance = PenaltyTicket.objects.get(pk=instance.pk)

            # Allow if only status changed from UNPAID to PAID
            if old_instance.status == PenaltyTicket.Status.UNPAID and instance.status == PenaltyTicket.Status.PAID:
                # This is allowed - penalty payment
                return

            # Check if any field other than status/payment_date changed
            for field in ["employee_id", "amount", "month", "violation_type", "violation_count", "note"]:
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
