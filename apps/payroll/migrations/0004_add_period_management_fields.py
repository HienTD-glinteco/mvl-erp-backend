"""Migration to add salary period management fields.

This migration adds:
- SalaryPeriod: uncompleted_at, uncompleted_by, payment_count, payment_total, deferred_count, deferred_total
- PayrollSlip: payment_period, hold_reason, held_at, held_by
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """Add salary period management fields."""

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("payroll", "0003_add_manager_grade_distribution"),
    ]

    operations = [
        # Add new fields to SalaryPeriod
        migrations.AddField(
            model_name="salaryperiod",
            name="uncompleted_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Timestamp when period was uncompleted/unlocked",
                null=True,
                verbose_name="Uncompleted At",
            ),
        ),
        migrations.AddField(
            model_name="salaryperiod",
            name="uncompleted_by",
            field=models.ForeignKey(
                blank=True,
                help_text="User who uncompleted the period",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="uncompleted_salary_periods",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Uncompleted By",
            ),
        ),
        migrations.AddField(
            model_name="salaryperiod",
            name="payment_count",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Count of payroll slips in payment table",
                verbose_name="Payment Count",
            ),
        ),
        migrations.AddField(
            model_name="salaryperiod",
            name="payment_total",
            field=models.DecimalField(
                decimal_places=0,
                default=0,
                help_text="Total net salary of payroll slips in payment table",
                max_digits=20,
                verbose_name="Payment Total",
            ),
        ),
        migrations.AddField(
            model_name="salaryperiod",
            name="deferred_count",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Count of payroll slips deferred to next period",
                verbose_name="Deferred Count",
            ),
        ),
        migrations.AddField(
            model_name="salaryperiod",
            name="deferred_total",
            field=models.DecimalField(
                decimal_places=0,
                default=0,
                help_text="Total net salary of deferred payroll slips",
                max_digits=20,
                verbose_name="Deferred Total",
            ),
        ),
        # Add new fields to PayrollSlip
        migrations.AddField(
            model_name="payrollslip",
            name="payment_period",
            field=models.ForeignKey(
                blank=True,
                help_text="The period when this slip is actually paid (may differ from salary_period)",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="payment_slips",
                to="payroll.salaryperiod",
                verbose_name="Payment Period",
            ),
        ),
        migrations.AddField(
            model_name="payrollslip",
            name="hold_reason",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Reason for holding the salary",
                max_length=500,
                verbose_name="Hold Reason",
            ),
        ),
        migrations.AddField(
            model_name="payrollslip",
            name="held_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Timestamp when slip was put on hold",
                null=True,
                verbose_name="Held At",
            ),
        ),
        migrations.AddField(
            model_name="payrollslip",
            name="held_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="held_payroll_slips",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Held By",
            ),
        ),
    ]
