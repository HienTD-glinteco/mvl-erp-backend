"""Serializer for GeoLocation-based attendance recording."""

from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.files.api.serializers.mixins import FileConfirmSerializerMixin
from apps.hrm.constants import AttendanceType
from apps.hrm.models import AttendanceGeolocation, AttendanceRecord
from apps.hrm.utils.geolocation import is_within_radius


class GeoLocationAttendanceSerializer(FileConfirmSerializerMixin, serializers.ModelSerializer):
    """Serializer for GeoLocation-based attendance recording.

    Validates GeoLocation coordinates against AttendanceGeolocation and creates attendance record.
    Uses FileConfirmSerializerMixin to handle image confirmation.
    """

    file_confirm_fields = ["image"]

    # Write-only fields for validation
    attendance_geolocation_id = serializers.PrimaryKeyRelatedField(
        queryset=AttendanceGeolocation.objects.filter(deleted=False, status=AttendanceGeolocation.Status.ACTIVE),
        source="attendance_geolocation",
        write_only=True,
        help_text=_("ID of the attendance geolocation to check against"),
    )

    class Meta:
        model = AttendanceRecord
        fields = [
            "latitude",
            "longitude",
            "attendance_geolocation_id",
            "image",
        ]

    def validate(self, attrs):
        """Validate that GeoLocation coordinates are within the geolocation radius."""
        latitude = attrs.get("latitude")
        longitude = attrs.get("longitude")
        geolocation = attrs.get("attendance_geolocation")

        if not latitude or not longitude or not geolocation:
            raise serializers.ValidationError(_("Latitude, longitude, and geolocation are required"))

        # Check if coordinates are within radius
        if not is_within_radius(
            latitude, longitude, geolocation.latitude, geolocation.longitude, geolocation.radius_m
        ):
            raise serializers.ValidationError(
                {
                    "location": _("Your location is outside the allowed radius ({radius}m) of the geolocation").format(
                        radius=geolocation.radius_m
                    )
                }
            )

        return attrs

    def create(self, validated_data):
        """Create an attendance record from GeoLocation data."""
        request = self.context.get("request")
        user = request.user if request else None

        # User must have an employee profile
        employee = user.employee

        # Set attendance record fields
        validated_data["attendance_type"] = AttendanceType.GEOLOCATION
        validated_data["employee"] = employee
        validated_data["attendance_code"] = employee.attendance_code
        validated_data["timestamp"] = timezone.now()
        validated_data["is_valid"] = True

        return super().create(validated_data)
