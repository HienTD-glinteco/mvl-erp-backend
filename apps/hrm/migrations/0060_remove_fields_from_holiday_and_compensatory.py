# Generated migration to remove status, soft-delete, and audit fields

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("hrm", "0058_holiday_compensatoryworkday_and_more"),
    ]

    operations = [
        # Remove fields from Holiday model
        migrations.RemoveField(
            model_name="holiday",
            name="status",
        ),
        migrations.RemoveField(
            model_name="holiday",
            name="created_by",
        ),
        migrations.RemoveField(
            model_name="holiday",
            name="updated_by",
        ),
        migrations.RemoveField(
            model_name="holiday",
            name="deleted",
        ),
        migrations.RemoveField(
            model_name="holiday",
            name="deleted_at",
        ),
        # Remove fields from CompensatoryWorkday model
        migrations.RemoveField(
            model_name="compensatoryworkday",
            name="status",
        ),
        migrations.RemoveField(
            model_name="compensatoryworkday",
            name="created_by",
        ),
        migrations.RemoveField(
            model_name="compensatoryworkday",
            name="updated_by",
        ),
        migrations.RemoveField(
            model_name="compensatoryworkday",
            name="deleted",
        ),
        migrations.RemoveField(
            model_name="compensatoryworkday",
            name="deleted_at",
        ),
    ]
