# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payroll", "0005_set_payment_period_for_delivered"),
    ]

    operations = [
        migrations.AddField(
            model_name="payrollslip",
            name="total_family_deduction",
            field=models.DecimalField(
                decimal_places=0, default=0, max_digits=20, verbose_name="Total Family Deduction"
            ),
        ),
        migrations.AddField(
            model_name="payrollslip",
            name="non_taxable_allowance",
            field=models.DecimalField(
                decimal_places=0, default=0, max_digits=20, verbose_name="Non-Taxable Allowance"
            ),
        ),
    ]
