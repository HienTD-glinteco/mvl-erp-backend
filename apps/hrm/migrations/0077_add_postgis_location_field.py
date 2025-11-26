# Generated migration for PostGIS support

from django.contrib.gis.geos import Point
from django.db import migrations
import django.contrib.gis.db.models.fields


def populate_location_field(apps, schema_editor):
    """Populate the location PointField from existing latitude/longitude."""
    AttendanceGeolocation = apps.get_model('hrm', 'AttendanceGeolocation')
    
    for geolocation in AttendanceGeolocation.objects.all():
        if geolocation.latitude is not None and geolocation.longitude is not None:
            # Create Point with longitude first (PostGIS convention)
            geolocation.location = Point(
                float(geolocation.longitude),
                float(geolocation.latitude),
                srid=4326
            )
            geolocation.save(update_fields=['location'])


class Migration(migrations.Migration):

    dependencies = [
        ('hrm', '0076_rename_device_and_update_attendance_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='attendancegeolocation',
            name='location',
            field=django.contrib.gis.db.models.fields.PointField(
                blank=True,
                geography=True,
                help_text='Geographic point for spatial queries (auto-populated from lat/long)',
                null=True,
                srid=4326,
                verbose_name='Location Point'
            ),
        ),
        migrations.RunPython(populate_location_field, reverse_code=migrations.RunPython.noop),
    ]
