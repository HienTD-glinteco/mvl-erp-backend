# Generated manually for update models and APIs issue

import django.db.models.deletion
from django.db import migrations, models


def set_default_province_and_administrative_unit(apps, schema_editor):
    """Set default province_id and administrative_unit_id to 1 for all existing Branch records"""
    Branch = apps.get_model("hrm", "Branch")
    Branch.objects.filter(province__isnull=True).update(province_id=1)
    Branch.objects.filter(administrative_unit__isnull=True).update(administrative_unit_id=1)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0011_province_administrativeunit"),
        ("hrm", "0008_alter_recruitmentchannel_belong_to"),
    ]

    operations = [
        # Position model changes - remove level field
        migrations.RemoveField(
            model_name="position",
            name="level",
        ),
        # Position model changes - update ordering
        migrations.AlterModelOptions(
            name="position",
            options={"ordering": ["name"], "verbose_name": "Position", "verbose_name_plural": "Positions"},
        ),
        # Branch model changes - set default values for NULL province and administrative_unit before making them required
        migrations.RunPython(set_default_province_and_administrative_unit, migrations.RunPython.noop),
        # Branch model changes - make province required
        # We'll use PROTECT to ensure referential integrity
        migrations.AlterField(
            model_name="branch",
            name="province",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="branches",
                to="core.province",
                verbose_name="Province",
            ),
        ),
        # Branch model changes - make administrative_unit required
        migrations.AlterField(
            model_name="branch",
            name="administrative_unit",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="branches",
                to="core.administrativeunit",
                verbose_name="Administrative unit",
            ),
        ),
    ]
