from decimal import Decimal

from rest_framework import serializers

from apps.hrm.constants import TimesheetStatus
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
    has_complaint = serializers.BooleanField(default=False, required=False, allow_null=True)


class TimeSheetEntryDetailSerializer(serializers.ModelSerializer):
    """Serializer for TimeSheetEntry detail view."""

    employee = EmployeeSerializer(read_only=True)

    class Meta:
        model = TimeSheetEntry
        fields = [
            "id",
            "employee",
            "date",
            "start_time",
            "end_time",
            "morning_hours",
            "afternoon_hours",
            "official_hours",
            "overtime_hours",
            "total_worked_hours",
            "status",
            "absent_reason",
            "is_full_salary",
            "count_for_payroll",
            "note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "employee",
            "official_hours",
            "total_worked_hours",
            "created_at",
            "updated_at",
        ]


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
