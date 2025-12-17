from decimal import Decimal

from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.hrm.models import TimeSheetEntry

from .employee import EmployeeSerializer


class TimesheetEntryComplain(serializers.Serializer):
    id = serializers.IntegerField()


class TimesheetEntrySerializer(serializers.ModelSerializer):
    has_complaint = serializers.SerializerMethodField()

    class Meta:
        model = TimeSheetEntry
        fields = [
            "id",
            "date",
            "status",
            "check_in_time",
            "check_out_time",
            "start_time",
            "end_time",
            "working_days",
            "has_complaint",
            "day_type",
            "is_holiday",
            "payroll_status",
        ]

    def get_has_complaint(self, obj) -> bool:
        complaint_entry_ids = self.context.get("complaint_entry_ids", set())
        return obj.id in complaint_entry_ids if obj.id else False


class TimeSheetEntryDetailSerializer(serializers.ModelSerializer):
    """Serializer for TimeSheetEntry detail view."""

    employee = EmployeeSerializer(read_only=True)
    manually_corrected_by = EmployeeSerializer(read_only=True)

    class Meta:
        model = TimeSheetEntry
        fields = [
            "id",
            "employee",
            "date",
            "start_time",
            "end_time",
            "check_in_time",
            "check_out_time",
            "manually_corrected_by",
            "manually_corrected_at",
            "day_type",
            "morning_hours",
            "afternoon_hours",
            "working_days",
            "official_hours",
            "overtime_hours",
            "total_worked_hours",
            "status",
            "absent_reason",
            "is_full_salary",
            "count_for_payroll",
            "note",
            "is_holiday",
            "payroll_status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "employee",
            "check_in_time",
            "check_out_time",
            "manually_corrected_by",
            "manually_corrected_at",
            "working_days",
            "day_type",
            "official_hours",
            "total_worked_hours",
            "created_at",
            "updated_at",
            "is_holiday",
            "payroll_status",
        ]

    def update(self, instance, validated_data):
        request = self.context.get("request")

        # Check if start_time or end_time is being updated
        if "start_time" in validated_data or "end_time" in validated_data:
            # Requirement: Note is required when updating start/end time
            note = validated_data.get("note", instance.note)
            if not note:
                raise serializers.ValidationError({"note": _("Note is required when manually correcting timesheet.")})

            instance.is_manually_corrected = True
            instance.manually_corrected_at = timezone.now()
            if request and request.user and hasattr(request.user, "employee"):
                instance.manually_corrected_by = request.user.employee

        return super().update(instance, validated_data)


class EmployeeTimesheetSerializer(serializers.Serializer):
    employee = EmployeeSerializer()
    dates = TimesheetEntrySerializer(many=True)
    probation_days = serializers.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0.00"), help_text="Probation working days"
    )
    official_work_days = serializers.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0.00"), help_text="Official working days"
    )
    total_work_days = serializers.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0.00"), help_text="Total working days"
    )
    unexcused_absence_days = serializers.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0.00"), help_text="Unexcused absence days"
    )
    holiday_days = serializers.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0.00"), help_text="Holiday days"
    )
    unpaid_leave_days = serializers.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0.00"), help_text="Unpaid leave days"
    )
    maternity_leave_days = serializers.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0.00"), help_text="Maternity leave days"
    )
    annual_leave_days = serializers.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0.00"), help_text="Paid leave days"
    )
    initial_leave_balance = serializers.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0.00"), help_text="Leave balance at period start"
    )
    remaining_leave_balance = serializers.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0.00"), help_text="Remaining leave balance"
    )
