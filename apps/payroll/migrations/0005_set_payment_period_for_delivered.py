"""Data migration to set payment_period for existing DELIVERED records.

For existing DELIVERED payroll slips, payment_period should equal salary_period
since they were paid in the same period they belonged to.
"""

from django.db import migrations, models


def set_payment_period_for_delivered(apps, schema_editor):
    """Set payment_period = salary_period for all DELIVERED PayrollSlips."""
    PayrollSlip = apps.get_model("payroll", "PayrollSlip")

    # Update all DELIVERED slips where payment_period is not set
    PayrollSlip.objects.filter(
        status="DELIVERED",
        payment_period__isnull=True,
    ).update(payment_period_id=models.F("salary_period_id"))


def reverse_payment_period(apps, schema_editor):
    """Reverse: clear payment_period for all PayrollSlips."""
    PayrollSlip = apps.get_model("payroll", "PayrollSlip")
    PayrollSlip.objects.all().update(payment_period=None)


class Migration(migrations.Migration):
    """Data migration for payment_period field."""

    dependencies = [
        ("payroll", "0004_add_period_management_fields"),
    ]

    operations = [
        migrations.RunPython(
            set_payment_period_for_delivered,
            reverse_code=reverse_payment_period,
        ),
    ]
