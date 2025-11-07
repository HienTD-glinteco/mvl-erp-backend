# Generated manually on 2025-11-07 05:33

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("hrm", "0049_employee_work_history_enhancements"),
    ]

    operations = [
        # Remove indexes first
        migrations.RemoveIndex(
            model_name="organizationchart",
            name="hrm_organiz_block_i_4bbe76_idx",
        ),
        migrations.RemoveIndex(
            model_name="organizationchart",
            name="hrm_organiz_branch__54e20b_idx",
        ),
        # Delete the model (this will drop the table and all constraints)
        migrations.DeleteModel(
            name="OrganizationChart",
        ),
    ]
