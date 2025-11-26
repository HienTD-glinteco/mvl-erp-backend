"""Serializers for GPS and WiFi-based attendance recording."""

from decimal import Decimal

from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.files.models import FileModel
from apps.hrm.models import AttendanceGeolocation, AttendanceRecord, AttendanceWifiDevice
from apps.hrm.utils.geolocation import is_within_radius


class GPSAttendanceSerializer(serializers.Serializer):
    """Serializer for GPS-based attendance recording.

    Validates GPS coordinates against AttendanceGeolocation and creates attendance record.
    """

    latitude = serializers.DecimalField(
        max_digits=20,
        decimal_places=17,
        min_value=Decimal("-90"),
        max_value=Decimal("90"),
        help_text=_("GPS latitude coordinate"),
    )
    longitude = serializers.DecimalField(
        max_digits=20,
        decimal_places=17,
        min_value=Decimal("-180"),
        max_value=Decimal("180"),
        help_text=_("GPS longitude coordinate"),
    )
    attendance_geolocation_id = serializers.IntegerField(
        help_text=_("ID of the attendance geolocation to check against")
    )
    image_id = serializers.IntegerField(help_text=_("ID of the uploaded attendance photo"))

    def validate_attendance_geolocation_id(self, value):
        """Validate that the attendance geolocation exists and is active."""
        try:
            geolocation = AttendanceGeolocation.objects.get(id=value, deleted=False)
        except AttendanceGeolocation.DoesNotExist:
            raise serializers.ValidationError(_("Attendance geolocation not found"))

        if geolocation.status != AttendanceGeolocation.Status.ACTIVE:
            raise serializers.ValidationError(_("Attendance geolocation is not active"))

        return value

    def validate_image_id(self, value):
        """Validate that the image file exists and is confirmed."""
        try:
            file = FileModel.objects.get(id=value)
        except FileModel.DoesNotExist:
            raise serializers.ValidationError(_("Image file not found"))

        if not file.is_confirmed:
            raise serializers.ValidationError(_("Image file must be confirmed before use"))

        return value

    def validate(self, attrs):
        """Validate that GPS coordinates are within the geolocation radius."""
        latitude = attrs.get("latitude")
        longitude = attrs.get("longitude")
        geolocation_id = attrs.get("attendance_geolocation_id")

        # Get geolocation
        geolocation = AttendanceGeolocation.objects.get(id=geolocation_id, deleted=False)

        # Check if coordinates are within radius
        if not is_within_radius(latitude, longitude, geolocation.latitude, geolocation.longitude, geolocation.radius_m):
            raise serializers.ValidationError(
                {
                    "location": _(
                        "Your location is outside the allowed radius ({radius}m) of the geolocation"
                    ).format(radius=geolocation.radius_m)
                }
            )

        return attrs

    def create(self, validated_data):
        """Create an attendance record from GPS data."""
        request = self.context.get("request")
        user = request.user if request else None

        # Get related objects
        geolocation = AttendanceGeolocation.objects.get(
            id=validated_data["attendance_geolocation_id"], deleted=False
        )
        image = FileModel.objects.get(id=validated_data["image_id"])

        # Try to get employee from user
        employee = None
        if user and hasattr(user, "employee"):
            employee = user.employee

        # Create attendance record
        attendance_record = AttendanceRecord.objects.create(
            attendance_type="gps",
            employee=employee,
            attendance_code=employee.attendance_code if employee else "",
            timestamp=timezone.now(),
            latitude=validated_data["latitude"],
            longitude=validated_data["longitude"],
            attendance_geolocation=geolocation,
            image=image,
            is_valid=True,
        )

        return attendance_record


class WiFiAttendanceSerializer(serializers.Serializer):
    """Serializer for WiFi-based attendance recording.

    Validates BSSID against AttendanceWifiDevice and creates attendance record.
    """

    bssid = serializers.CharField(
        max_length=17, help_text=_("WiFi BSSID (MAC address format: XX:XX:XX:XX:XX:XX)")
    )

    def validate_bssid(self, value):
        """Validate that the BSSID exists and is in use."""
        try:
            wifi_device = AttendanceWifiDevice.objects.get(bssid=value)
        except AttendanceWifiDevice.DoesNotExist:
            raise serializers.ValidationError(_("WiFi device not found"))

        if wifi_device.state != AttendanceWifiDevice.State.IN_USE:
            raise serializers.ValidationError(_("WiFi device is not in use"))

        return value

    def create(self, validated_data):
        """Create an attendance record from WiFi data."""
        request = self.context.get("request")
        user = request.user if request else None

        # Get WiFi device
        wifi_device = AttendanceWifiDevice.objects.get(bssid=validated_data["bssid"])

        # Try to get employee from user
        employee = None
        if user and hasattr(user, "employee"):
            employee = user.employee

        # Create attendance record
        attendance_record = AttendanceRecord.objects.create(
            attendance_type="wifi",
            employee=employee,
            attendance_code=employee.attendance_code if employee else "",
            timestamp=timezone.now(),
            attendance_wifi_device=wifi_device,
            is_valid=True,
        )

        return attendance_record
