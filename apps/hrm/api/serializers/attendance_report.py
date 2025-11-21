from rest_framework import serializers


class AttendanceMethodBreakdownReportSerializer(serializers.Serializer):
    device = serializers.DecimalField(max_digits=20, decimal_places=2, default=0)
    wifi = serializers.DecimalField(max_digits=20, decimal_places=2, default=0)
    geolocation = serializers.DecimalField(max_digits=20, decimal_places=2, default=0)


class AttendanceMethodItemReportSerializer(serializers.Serializer):
    total_employee = serializers.DecimalField(max_digits=20, decimal_places=2, default=0)
    not_attendance = serializers.DecimalField(max_digits=20, decimal_places=2, default=0)
    has_attendance = serializers.DecimalField(max_digits=20, decimal_places=2, default=0)
    method_breakdown = AttendanceMethodBreakdownReportSerializer()


class AttendanceMethodReportSerializer(serializers.Serializer):
    absolute = AttendanceMethodItemReportSerializer()
    percentage = AttendanceMethodItemReportSerializer()


class AttendanceMethodReportParameterSerializer(serializers.Serializer):
    attendance_date = serializers.DateField(required=False)
    branch = serializers.IntegerField(required=False)
    block = serializers.IntegerField(required=False)
    department = serializers.IntegerField(required=False)
