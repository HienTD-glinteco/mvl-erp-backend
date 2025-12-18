from rest_framework import serializers

from apps.files.api.serializers import FileSerializer
from apps.hrm.api.serializers.attendance_geolocation import AttendanceGeolocationSerializer
from apps.hrm.api.serializers.attendance_wifi_device import AttendanceWifiDeviceSerializer
from apps.hrm.api.serializers.employee import EmployeeSerializer
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

    Provides access to attendance records with nested references for biometric_device, employee,
    geolocation, image, and wifi device. Allows editing of timestamp, is_valid status, and notes.
    """

    biometric_device = AttendanceDeviceNestedSerializer(read_only=True)
    employee = EmployeeSerializer(read_only=True)
    attendance_geolocation = AttendanceGeolocationSerializer(read_only=True)
    image = FileSerializer(read_only=True)
    attendance_wifi_device = AttendanceWifiDeviceSerializer(read_only=True)
    approved_by = EmployeeSerializer(read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = [
            "id",
            "code",
            "attendance_type",
            "biometric_device",
            "employee",
            "attendance_code",
            "timestamp",
            "latitude",
            "longitude",
            "attendance_geolocation",
            "image",
            "attendance_wifi_device",
            "description",
            "is_valid",
            "is_pending",
            "approved_at",
            "approved_by",
            "notes",
            "raw_data",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "code",
            "attendance_type",
            "biometric_device",
            "employee",
            "attendance_code",
            "latitude",
            "longitude",
            "attendance_geolocation",
            "image",
            "attendance_wifi_device",
            "is_pending",
            "approved_at",
            "approved_by",
            "raw_data",
            "created_at",
            "updated_at",
        ]
