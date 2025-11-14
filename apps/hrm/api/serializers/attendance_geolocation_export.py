from rest_framework import serializers

from apps.hrm.models import AttendanceGeolocation


class AttendanceGeolocationExportSerializer(serializers.ModelSerializer):
    """Serializer for exporting AttendanceGeolocation data to Excel.

    This serializer flattens related objects (project) to include their names
    directly in the export.
    """

    project__name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = AttendanceGeolocation
        fields = [
            "code",
            "name",
            "project__name",
            "address",
            "latitude",
            "longitude",
            "radius_m",
            "status",
            "notes",
            "created_at",
            "updated_at",
        ]
