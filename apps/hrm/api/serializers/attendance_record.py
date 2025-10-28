from rest_framework import serializers

from apps.hrm.models import AttendanceDevice, AttendanceRecord
from libs import FieldFilteringSerializerMixin


class AttendanceDeviceNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested device references in attendance records."""

    class Meta:
        model = AttendanceDevice
        fields = ["id", "name"]
        read_only_fields = ["id", "name"]


class AttendanceRecordSerializer(FieldFilteringSerializerMixin, serializers.ModelSerializer):
    """Serializer for AttendanceRecord model.

    Provides access to attendance records with nested device information.
    Allows editing of timestamp, is_valid status, and notes.
    """

    device = AttendanceDeviceNestedSerializer(read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = [
            "id",
            "device",
            "attendance_code",
            "timestamp",
            "is_valid",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "device",
            "attendance_code",
            "created_at",
            "updated_at",
        ]
