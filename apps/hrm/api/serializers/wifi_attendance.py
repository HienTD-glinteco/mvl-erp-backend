"""Serializer for WiFi-based attendance recording."""

from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.hrm.constants import AttendanceType
from apps.hrm.models import AttendanceRecord, AttendanceWifiDevice


class WiFiAttendanceSerializer(serializers.ModelSerializer):
    """Serializer for WiFi-based attendance recording.

    Validates BSSID against AttendanceWifiDevice and creates attendance record.
    """

    # Write-only field for validation
    bssid = serializers.CharField(
        max_length=17,
        write_only=True,
        help_text=_("WiFi BSSID (MAC address format: XX:XX:XX:XX:XX:XX)"),
    )

    class Meta:
        model = AttendanceRecord
        fields = ["bssid"]

    def validate_bssid(self, value):
        """Validate that the BSSID exists and is in use."""
        try:
            wifi_device = AttendanceWifiDevice.objects.get(bssid=value)
        except AttendanceWifiDevice.DoesNotExist:
            raise serializers.ValidationError(_("WiFi device not found"))

        if wifi_device.state != AttendanceWifiDevice.State.IN_USE:
            raise serializers.ValidationError(_("WiFi device is not in use"))

        # Store the wifi_device in context for use in create()
        self.context["wifi_device"] = wifi_device
        return value

    def create(self, validated_data):
        """Create an attendance record from WiFi data."""
        request = self.context.get("request")
        user = request.user if request else None

        # User must have an employee profile
        employee = user.employee

        # Get WiFi device from context
        wifi_device = self.context.get("wifi_device")

        # Remove bssid from validated_data as it's not a model field
        validated_data.pop("bssid", None)

        # Create attendance record
        attendance_record = AttendanceRecord.objects.create(
            attendance_type=AttendanceType.WIFI,
            employee=employee,
            attendance_code=employee.attendance_code,
            timestamp=timezone.now(),
            attendance_wifi_device=wifi_device,
            is_valid=True,
        )

        return attendance_record
