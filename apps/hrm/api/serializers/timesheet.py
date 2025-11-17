from rest_framework import serializers

from apps.hrm.constants import TimesheetStatus

from .employee import EmployeeSerializer


class TimesheetEntryComplain(serializers.Serializer):
    id = serializers.IntegerField()


class TimesheetEntrySerializer(serializers.Serializer):
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
    complaint = TimesheetEntryComplain(required=False, allow_null=True, help_text="Complain of this timsheet entry")


class EmployeeTimesheetSerializer(serializers.Serializer):
    employee = EmployeeSerializer()
    dates = TimesheetEntrySerializer(many=True)
    probation_days = serializers.IntegerField(default=0, help_text="Probation working days / Công thử việc")
    official_work_days = serializers.IntegerField(default=0, help_text="Official working days / Công chính thức")
    total_work_days = serializers.IntegerField(default=0, help_text="Total working days / Tổng công")
    unexcused_absence_days = serializers.IntegerField(default=0, help_text="Unexcused absence days / Nghỉ không lý do")
    holiday_days = serializers.IntegerField(default=0, help_text="Holiday days / Nghỉ lễ")
    unpaid_leave_days = serializers.IntegerField(default=0, help_text="Unpaid leave days / Nghỉ không lương")
    maternity_leave_days = serializers.IntegerField(default=0, help_text="Maternity leave days / Nghỉ thai sản")
    annual_leave_days = serializers.IntegerField(default=0, help_text="Annual leave days / Nghỉ phép")
    initial_leave_balance = serializers.IntegerField(
        default=0, help_text="Leave balance at period start / Phép đầu kỳ"
    )
    remaining_leave_balance = serializers.IntegerField(default=0, help_text="Remaining leave balance / Phép tồn")
