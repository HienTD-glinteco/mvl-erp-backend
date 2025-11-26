from rest_framework import serializers

from apps.files.api.serializers import FileSerializer
from apps.hrm.models import AttendanceDevice, AttendanceGeolocation, AttendanceRecord, AttendanceWifiDevice, Employee
from libs import FieldFilteringSerializerMixin


class AttendanceDeviceNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested device references in attendance records."""

    class Meta:
        model = AttendanceDevice
        fields = ["id", "name"]
        read_only_fields = ["id", "name"]


class SimpleEmployeeSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested employee references in attendance records."""

    class Meta:
        model = Employee
        fields = ["id", "code", "fullname", "attendance_code"]
        read_only_fields = ["id", "code", "fullname", "attendance_code"]


class AttendanceGeolocationNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested geolocation references in attendance records."""

    class Meta:
        model = AttendanceGeolocation
        fields = ["id", "code", "name"]
        read_only_fields = ["id", "code", "name"]


class AttendanceWifiDeviceNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested wifi device references in attendance records."""

    class Meta:
        model = AttendanceWifiDevice
        fields = ["id", "code", "name"]
        read_only_fields = ["id", "code", "name"]


class AttendanceRecordSerializer(FieldFilteringSerializerMixin, serializers.ModelSerializer):
    """Serializer for AttendanceRecord model.

    Provides access to attendance records with nested references for device, employee,
    geolocation, image, and wifi device. Allows editing of timestamp, is_valid status, and notes.
    """

    device = AttendanceDeviceNestedSerializer(read_only=True)
    employee = SimpleEmployeeSerializer(read_only=True)
    attendance_geolocation = AttendanceGeolocationNestedSerializer(read_only=True)
    image = FileSerializer(read_only=True)
    attendance_wifi_device = AttendanceWifiDeviceNestedSerializer(read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = [
            "id",
            "code",
            "attendance_type",
            "device",
            "employee",
            "attendance_code",
            "timestamp",
            "latitude",
            "longitude",
            "attendance_geolocation",
            "image",
            "attendance_wifi_device",
            "is_valid",
            "notes",
            "raw_data",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "code",
            "attendance_type",
            "device",
            "employee",
            "attendance_code",
            "latitude",
            "longitude",
            "attendance_geolocation",
            "image",
            "attendance_wifi_device",
            "raw_data",
            "created_at",
            "updated_at",
        ]
