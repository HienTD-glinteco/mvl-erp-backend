# Generated migration

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("hrm", "0024_add_is_enabled_to_attendance_device"),
    ]

    operations = [
        # Add new fields to AttendanceDevice
        migrations.AddField(
            model_name="attendancedevice",
            name="block",
            field=models.ForeignKey(
                blank=True,
                help_text="Block where device is installed",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="attendance_devices",
                to="hrm.block",
                verbose_name="Block",
            ),
        ),
        migrations.AddField(
            model_name="attendancedevice",
            name="realtime_enabled",
            field=models.BooleanField(
                default=True,
                help_text="Whether realtime listener is enabled for this device",
                verbose_name="Realtime enabled",
            ),
        ),
        migrations.AddField(
            model_name="attendancedevice",
            name="realtime_disabled_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Timestamp when realtime was disabled due to connection failures",
                null=True,
                verbose_name="Realtime disabled at",
            ),
        ),
        # Add new fields to AttendanceRecord
        migrations.AddField(
            model_name="attendancerecord",
            name="is_valid",
            field=models.BooleanField(
                default=True, help_text="Whether this attendance record is valid", verbose_name="Is valid"
            ),
        ),
        migrations.AddField(
            model_name="attendancerecord",
            name="notes",
            field=models.TextField(
                blank=True, help_text="Additional notes or comments about this attendance record", verbose_name="Notes"
            ),
        ),
        # Remove old location field from AttendanceDevice
        migrations.RemoveField(
            model_name="attendancedevice",
            name="location",
        ),
    ]
