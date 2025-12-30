"""Statistics update signals.

This module handles automatic updates of SalaryPeriod statistics when
PayrollSlip or related models change.

Architecture:
============

Central Update Point:
- PayrollSlip.post_save → Updates SalaryPeriod statistics

Triggering Events:
- PayrollSlip creation
- PayrollSlip status changes
- PayrollSlip salary amount changes (gross_income, net_salary)
- PayrollSlip need_resend_email changes
- PayrollSlip deletion
- Direct statistics-affecting changes (PenaltyTicket, TravelExpense, RecoveryVoucher)

This centralized approach prevents duplicate statistics updates because:
1. Data changes (contract, timesheet, KPI, etc.) trigger recalculate_payroll_slip_task
2. Task updates PayrollSlip
3. PayrollSlip.post_save triggers statistics update
4. Only direct creation/deletion of certain models trigger immediate stats update

Statistics Tracked:
- pending_count: PayrollSlips with PENDING status
- ready_count: PayrollSlips with READY status
- hold_count: PayrollSlips with HOLD status
- delivered_count: PayrollSlips with DELIVERED status
- total_gross_income: Sum of all gross_income
- total_net_salary: Sum of all net_salary
- employees_with_penalties_count: Employees with unpaid penalties
- employees_paid_penalties_count: Employees with paid penalties
- employees_need_recovery_count: Employees with recovery vouchers
- employees_with_travel_expense_count: Employees with travel expenses
- employees_need_resend_email_count: Employees needing email resend
"""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.payroll.models import PayrollSlip, PenaltyTicket, RecoveryVoucher, SalaryPeriod, TravelExpense


@receiver(post_save, sender=PayrollSlip)
def update_salary_period_stats_on_payroll_change(sender, instance, **kwargs):
    """Update salary period statistics when payroll slip changes.

    Triggers statistics update when:
    - PayrollSlip is created
    - Status changes
    - Salary amounts change (gross_income, net_salary)
    - need_resend_email changes

    Note: This is the central point for statistics updates. All changes that affect
    payroll (contracts, timesheets, KPI, expenses, etc.) trigger payroll recalculation,
    which saves PayrollSlip and triggers this signal.
    """
    update_fields = kwargs.get("update_fields")

    # Always update on creation
    if kwargs.get("created", False):
        instance.salary_period.update_statistics()
        return

    # Fields that should trigger statistics update
    stats_triggering_fields = {"status", "gross_income", "net_salary", "need_resend_email"}

    # If update_fields is specified, check if any stats-triggering field was updated
    if update_fields is not None:
        updated_fields_set = set(update_fields) if not isinstance(update_fields, set) else update_fields

        if stats_triggering_fields & updated_fields_set:
            instance.salary_period.update_statistics()
    else:
        # If no update_fields specified (full update), always update statistics
        instance.salary_period.update_statistics()


@receiver(post_delete, sender=PayrollSlip)
def update_salary_period_stats_on_payroll_delete(sender, instance, **kwargs):
    """Update salary period statistics when payroll slip is deleted."""
    try:
        instance.salary_period.update_statistics()
    except SalaryPeriod.DoesNotExist:
        pass


# Direct statistics updates for creation/deletion of these models
# (their post_save for updates triggers recalculation which updates stats via PayrollSlip)


@receiver(post_save, sender=PenaltyTicket)
def on_penalty_ticket_created(sender, instance, created, **kwargs):
    """Update statistics when penalty ticket is created.

    Only updates on creation. Status changes trigger recalculation which
    updates statistics via PayrollSlip.post_save.
    """
    if created:
        try:
            period = SalaryPeriod.objects.get(month=instance.month)
            period.update_statistics()
        except SalaryPeriod.DoesNotExist:
            pass


@receiver(post_delete, sender=PenaltyTicket)
def on_penalty_ticket_deleted(sender, instance, **kwargs):
    """Update statistics when penalty ticket is deleted."""
    try:
        period = SalaryPeriod.objects.get(month=instance.month)
        period.update_statistics()
    except SalaryPeriod.DoesNotExist:
        pass


@receiver(post_save, sender=TravelExpense)
def on_travel_expense_created(sender, instance, created, **kwargs):
    """Update statistics when travel expense is created.

    Only updates on creation. Updates trigger recalculation which
    updates statistics via PayrollSlip.post_save.
    """
    if created:
        try:
            period = SalaryPeriod.objects.get(month=instance.month)
            period.update_statistics()
        except SalaryPeriod.DoesNotExist:
            pass


@receiver(post_delete, sender=TravelExpense)
def on_travel_expense_deleted_stats(sender, instance, **kwargs):
    """Update statistics when travel expense is deleted."""
    try:
        period = SalaryPeriod.objects.get(month=instance.month)
        period.update_statistics()
    except SalaryPeriod.DoesNotExist:
        pass


@receiver(post_save, sender=RecoveryVoucher)
def on_recovery_voucher_created(sender, instance, created, **kwargs):
    """Update statistics when recovery voucher is created.

    Only updates on creation. Updates trigger recalculation which
    updates statistics via PayrollSlip.post_save.
    """
    if created:
        try:
            period = SalaryPeriod.objects.get(month=instance.month)
            period.update_statistics()
        except SalaryPeriod.DoesNotExist:
            pass


@receiver(post_delete, sender=RecoveryVoucher)
def on_recovery_voucher_deleted_stats(sender, instance, **kwargs):
    """Update statistics when recovery voucher is deleted."""
    try:
        period = SalaryPeriod.objects.get(month=instance.month)
        period.update_statistics()
    except SalaryPeriod.DoesNotExist:
        pass
