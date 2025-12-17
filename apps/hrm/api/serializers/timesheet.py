from decimal import Decimal

from rest_framework import serializers

from apps.hrm.constants import TimesheetDayType, TimesheetStatus
from apps.hrm.models import TimeSheetEntry

from .employee import EmployeeSerializer


class TimesheetEntryComplain(serializers.Serializer):
    id = serializers.IntegerField()


class TimesheetEntrySerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True, required=False)
    date = serializers.DateField(required=True)
    status = serializers.ChoiceField(
        choices=TimesheetStatus,
        allow_null=True,
        help_text="Status",
    )
    start_time = serializers.DateTimeField(
        allow_null=True,
        required=False,
        help_text="Start time",
    )
    end_time = serializers.DateTimeField(
        allow_null=True,
        required=False,
        help_text="End time",
    )
    working_days = serializers.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"), required=False, help_text="Working days"
    )
    has_complaint = serializers.BooleanField(default=False, required=False, allow_null=True)
    day_type = serializers.ChoiceField(
        choices=TimesheetDayType.choices, allow_null=True, required=False, help_text="Day type"
    )
    # Computed fields
    is_holiday = serializers.BooleanField(read_only=True, required=False)
    payroll_status = serializers.CharField(read_only=True, required=False)
    # New fields
    check_in_record = serializers.DateTimeField(required=False, allow_null=True)
    check_out_record = serializers.DateTimeField(required=False, allow_null=True)
    ot_hours_calculated = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)


class TimeSheetEntryDetailSerializer(serializers.ModelSerializer):
    """Serializer for TimeSheetEntry detail view."""

    employee = EmployeeSerializer(read_only=True)
    is_holiday = serializers.SerializerMethodField()
    payroll_status = serializers.SerializerMethodField()
    manually_corrected_by = EmployeeSerializer(read_only=True)

    class Meta:
        model = TimeSheetEntry
        fields = [
            "id",
            "employee",
            "date",
            "start_time",
            "end_time",
            "check_in_record",
            "check_out_record",
            "manually_corrected_by",
            "manually_corrected_at",
            "ot_hours_calculated",
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
            "check_in_record",
            "check_out_record",
            "manually_corrected_by",
            "manually_corrected_at",
            "ot_hours_calculated",
            "working_days",
            "day_type",
            "official_hours",
            "total_worked_hours",
            "created_at",
            "updated_at",
            "is_holiday",
            "payroll_status",
        ]

    def get_is_holiday(self, obj) -> bool:
        return obj.day_type == TimesheetDayType.HOLIDAY

    def get_payroll_status(self, obj) -> str:
        from apps.hrm.constants import EmployeeType
        from django.utils.translation import gettext as _

        # Check employee type for unpaid status
        # Since employee is a ForeignKey, we should check if it's prefetched or access it
        # Safely access employee type
        emp_type = None
        if obj.employee_id:
            # Try to get from loaded object or query
            if hasattr(obj, "employee") and obj.employee:
                emp_type = obj.employee.employee_type
            else:
                # This might cause N+1 query if not optimizing queryset, but safe for detail view
                emp_type = obj.employee.employee_type

        if emp_type in [EmployeeType.UNPAID_OFFICIAL, EmployeeType.UNPAID_PROBATION]:
            return _("Không lương")
        return _("Có lương")

    def update(self, instance, validated_data):
        from django.utils import timezone
        from django.utils.translation import gettext as _
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
