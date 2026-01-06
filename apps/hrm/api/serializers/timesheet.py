from decimal import Decimal

from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.hrm.constants import TimesheetStatus
from apps.hrm.models import TimeSheetEntry
from libs.constants import ColorVariant

from .employee import EmployeeSerializer


class TimesheetEntryComplain(serializers.Serializer):
    id = serializers.IntegerField()


class TimesheetEntrySerializer(serializers.ModelSerializer):
    """Serializer for timesheet list view.

    Note: SINGLE_PUNCH status is mapped to NOT_ON_TIME for list display
    because the list view has fewer status options.
    """

    has_complaint = serializers.SerializerMethodField()
    colored_status = serializers.SerializerMethodField()

    class Meta:
        model = TimeSheetEntry
        fields = [
            "id",
            "date",
            "colored_status",
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

    def get_colored_status(self, obj) -> dict | None:
        """Get colored status, mapping SINGLE_PUNCH to NOT_ON_TIME for list display."""
        colored = obj.colored_status
        if not colored:
            return None

        # Map SINGLE_PUNCH to NOT_ON_TIME for list display
        if obj.status == TimesheetStatus.SINGLE_PUNCH:
            return {
                "value": TimesheetStatus.NOT_ON_TIME.label,
                "variant": ColorVariant.YELLOW.value,
            }
        return colored


class TimeSheetEntryDetailSerializer(serializers.ModelSerializer):
    """Serializer for TimeSheetEntry detail view."""

    employee = EmployeeSerializer(read_only=True)
    manually_corrected_by = EmployeeSerializer(read_only=True)

    class Meta:
        model = TimeSheetEntry
        fields = read_only_fields = [
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


class TimeSheetEntryUpdateSerializer(serializers.ModelSerializer):
    start_time = serializers.DateTimeField(required=True)
    end_time = serializers.DateTimeField(required=True)
    note = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = TimeSheetEntry
        fields = [
            "start_time",
            "end_time",
            "note",
        ]

    def validate(self, attrs):
        start_time = attrs.get("start_time")
        end_time = attrs.get("end_time")
        note = attrs.get("note") or ""

        if start_time and end_time and start_time >= end_time:
            raise serializers.ValidationError({"end_time": _("End time must be after start time.")})

        note = note.strip()
        if self.instance.note:
            note = self.instance.note + "\n---\n" + note

        attrs["note"] = note
        attrs["is_manually_corrected"] = True
        attrs["manually_corrected_at"] = timezone.now()

        request = self.context.get("request")
        if request and request.user and hasattr(request.user, "employee"):
            attrs["manually_corrected_by"] = request.user.employee

        return attrs


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
