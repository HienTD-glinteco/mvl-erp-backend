from rest_framework import serializers
from django.db import transaction
from django.db.models import Value
from django.db.models.functions import Concat
from django.utils import timezone

from apps.hrm.models import AttendanceGeolocation, AttendanceRecord


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
        employee = request.user.employee

        # Extract optional image_id if present
        image_id = validated_data.pop("image_id", None)

        from apps.hrm.constants import AttendanceType
        from apps.files.models import FileModel

        # Create record
        record = AttendanceRecord(
            employee=employee,
            attendance_code=employee.attendance_code,
            attendance_type=AttendanceType.OTHER,
            is_pending=True,
            is_valid=None,  # Explicitly None as per requirement
            **validated_data
        )

        if image_id:
             try:
                 record.image = FileModel.objects.get(id=image_id)
             except FileModel.DoesNotExist:
                 pass

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

    def save(self):
        ids = self.validated_data["ids"]
        is_approve = self.validated_data["is_approve"]
        note = self.validated_data.get("note", "")
        request = self.context.get("request")

        # Get employee from user
        try:
            approver = request.user.employee
        except AttributeError:
            # Handle case where user is not linked to an employee (e.g., admin)
            approver = None

        with transaction.atomic():
            records = AttendanceRecord.objects.filter(id__in=ids)
            count = records.count()

            update_fields = {
                "is_valid": is_approve,
                "is_pending": False,
                "approved_at": timezone.now(),
                "approved_by": approver
            }

            if note:
                # Use bulk update with Concat to append note
                records.update(
                    notes=Concat("notes", Value(f"\nApproval Note: {note}")),
                    **update_fields
                )
            else:
                records.update(**update_fields)

        return count
