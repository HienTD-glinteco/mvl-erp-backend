# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("hrm", "0023_attendancedevice_attendancerecord"),
    ]

    operations = [
        migrations.AddField(
            model_name="attendancedevice",
            name="is_enabled",
            field=models.BooleanField(
                default=True,
                help_text="Whether the device is enabled for automatic synchronization",
                verbose_name="Is enabled",
            ),
        ),
    ]
