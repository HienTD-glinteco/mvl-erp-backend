from django.db import transaction
from django.db.models import Value
from django.db.models.functions import Concat
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.files.api.serializers.mixins import FileConfirmSerializerMixin
from apps.hrm.constants import AttendanceType
from apps.hrm.models import AttendanceRecord


class OtherAttendanceSerializer(FileConfirmSerializerMixin, serializers.ModelSerializer):
    """Serializer for recording 'Other' type attendance."""

    timestamp = serializers.DateTimeField(required=True)
    latitude = serializers.DecimalField(max_digits=20, decimal_places=17, min_value=-90, max_value=90, required=True)
    longitude = serializers.DecimalField(
        max_digits=20, decimal_places=17, min_value=-180, max_value=180, required=True
    )
    description = serializers.CharField(required=True)
    image_id = serializers.IntegerField(required=True)

    file_confirm_fields = ["image_id"]

    class Meta:
        model = AttendanceRecord
        fields = [
            "timestamp",
            "latitude",
            "longitude",
            "description",
            "image_id",
        ]

    def validate(self, attrs):
        request = self.context.get("request")
        employee = request.user.employee
        attrs.update(
            employee=employee,
            attendance_code=employee.attendance_code,
            attendance_type=AttendanceType.OTHER,
            is_pending=True,
            is_valid=None,  # Explicitly None as per requirement
        )
        return attrs


class OtherAttendanceBulkApproveSerializer(serializers.Serializer):
    """Serializer for bulk approving attendance records."""

    ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)
    is_approve = serializers.BooleanField(required=True)
    note = serializers.CharField(required=False, allow_blank=True)

    def validate_ids(self, ids):
        if not AttendanceRecord.objects.filter(id__in=ids, attendance_type=AttendanceType.OTHER).exists():
            raise serializers.ValidationError(_("No valid 'Other' attendance records found for the provided IDs."))
        return ids

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
                "approved_by": approver,
            }

            if note:
                # Use bulk update with Concat to append note
                records.update(notes=Concat("notes", Value(f"\nApproval Note: {note}")), **update_fields)
            else:
                records.update(**update_fields)

        return count
