from rest_framework import serializers

from apps.hrm.models import AttendanceGeolocation
from libs.drf.fields import CurrentEmployeeDefault


class OtherAttendanceSerializer(serializers.Serializer):
    """Serializer for recording 'Other' type attendance."""

    timestamp = serializers.DateTimeField(required=True)
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    # Optional location data
    latitude = serializers.DecimalField(
        max_digits=20,
        decimal_places=17,
        min_value=-90,
        max_value=90,
        required=False,
        allow_null=True
    )
    longitude = serializers.DecimalField(
        max_digits=20,
        decimal_places=17,
        min_value=-180,
        max_value=180,
        required=False,
        allow_null=True
    )
    attendance_geolocation_id = serializers.PrimaryKeyRelatedField(
        queryset=AttendanceGeolocation.objects.all(),
        required=False,
        allow_null=True,
        source="attendance_geolocation"
    )
    image_id = serializers.IntegerField(required=False, allow_null=True)

    def create(self, validated_data):
        request = self.context.get("request")
        employee = CurrentEmployeeDefault()(self)

        # Extract optional image_id if present (handle manually since it's an ID, not a model instance yet in validation if just IntegerField)
        image_id = validated_data.pop("image_id", None)

        from apps.hrm.constants import AttendanceType
        from apps.hrm.models import AttendanceRecord
        from apps.files.models import FileModel

        # Create record
        record = AttendanceRecord(
            employee=employee,
            attendance_code=employee.attendance_code if employee else "",
            attendance_type=AttendanceType.OTHER,
            is_pending=True,
            is_valid=None,  # Explicitly None as per requirement
            **validated_data
        )

        if image_id:
             try:
                 record.image = FileModel.objects.get(id=image_id)
             except FileModel.DoesNotExist:
                 pass # Or raise error, but requirement said optional

        record.save()
        return record


class AttendanceBulkApproveSerializer(serializers.Serializer):
    """Serializer for bulk approving attendance records."""

    ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )
    is_approve = serializers.BooleanField(required=True)
    note = serializers.CharField(required=False, allow_blank=True)
