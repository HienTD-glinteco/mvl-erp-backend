# Generated migration for KPICriterion model enhancement

from decimal import Decimal

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payroll", "0003_kpicriterion"),
    ]

    operations = [
        # Step 1: Add new fields with nullable/default values first
        migrations.AddField(
            model_name="kpicriterion",
            name="sub_criterion",
            field=models.CharField(
                blank=True,
                null=True,
                max_length=255,
                verbose_name="Sub-criterion",
                help_text="Additional details for the criterion",
            ),
        ),
        migrations.AddField(
            model_name="kpicriterion",
            name="group_number",
            field=models.IntegerField(
                default=1,
                verbose_name="Group number",
                help_text="Group number for displaying criteria in the same block",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="kpicriterion",
            name="order",
            field=models.IntegerField(
                default=0,
                verbose_name="Order",
                help_text="Display order within evaluation type",
            ),
            preserve_default=False,
        ),
        # Step 2: Rename fields
        migrations.RenameField(
            model_name="kpicriterion",
            old_name="name",
            new_name="criterion",
        ),
        # Step 3: Remove old ordering field (will be replaced by order)
        migrations.RemoveField(
            model_name="kpicriterion",
            name="ordering",
        ),
        # Step 4: Update evaluation_type field to use choices
        migrations.AlterField(
            model_name="kpicriterion",
            name="evaluation_type",
            field=models.CharField(
                max_length=50,
                choices=[
                    ("work_performance", "Work Performance"),
                    ("discipline", "Discipline"),
                ],
                verbose_name="Evaluation type",
                help_text="Type of evaluation (work performance or discipline)",
            ),
        ),
        # Step 5: Update criterion field metadata
        migrations.AlterField(
            model_name="kpicriterion",
            name="criterion",
            field=models.CharField(
                max_length=255,
                verbose_name="Criterion",
                help_text="Main evaluation criterion",
            ),
        ),
        # Step 6: Update Meta options
        migrations.AlterUniqueTogether(
            name="kpicriterion",
            unique_together={("target", "evaluation_type", "criterion")},
        ),
        migrations.AlterModelOptions(
            name="kpicriterion",
            options={
                "verbose_name": "KPI Criterion",
                "verbose_name_plural": "KPI Criteria",
                "ordering": ["evaluation_type", "order"],
            },
        ),
    ]
