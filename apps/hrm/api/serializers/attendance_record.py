from rest_framework import serializers

from apps.hrm.models import AttendanceRecord
from libs import FieldFilteringSerializerMixin


class AttendanceDeviceNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested device references in attendance records."""

    class Meta:
        from apps.hrm.models import AttendanceDevice

        model = AttendanceDevice
        fields = ["id", "name", "location"]
        read_only_fields = ["id", "name", "location"]


class AttendanceRecordSerializer(FieldFilteringSerializerMixin, serializers.ModelSerializer):
    """Serializer for AttendanceRecord model.

    Provides read-only access to attendance records with nested device information.
    Attendance records are created automatically via device polling and should not
    be manually created or modified through the API.
    """

    device = AttendanceDeviceNestedSerializer(read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = [
            "id",
            "device",
            "attendance_code",
            "timestamp",
            "raw_data",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "device",
            "attendance_code",
            "timestamp",
            "raw_data",
            "created_at",
            "updated_at",
        ]
