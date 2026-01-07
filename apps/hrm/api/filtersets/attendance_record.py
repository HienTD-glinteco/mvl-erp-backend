import django_filters

from apps.hrm.models import AttendanceRecord


class AttendanceRecordFilterSet(django_filters.FilterSet):
    """FilterSet for AttendanceRecord model."""

    employee = django_filters.NumberFilter(field_name="employee__id")
    attendance_code = django_filters.CharFilter(field_name="attendance_code", lookup_expr="icontains")
    timestamp_after = django_filters.DateTimeFilter(field_name="timestamp", lookup_expr="gte")
    timestamp_before = django_filters.DateTimeFilter(field_name="timestamp", lookup_expr="lte")
    date = django_filters.DateFilter(field_name="timestamp", lookup_expr="date")
    approve_status = django_filters.MultipleChoiceFilter(
        choices=AttendanceRecord.ApproveStatus.choices,
        help_text="Filter by approve status (supports multiple values)",
    )

    class Meta:
        model = AttendanceRecord
        fields = [
            "employee",
            "biometric_device",
            "attendance_type",
            "attendance_code",
            "timestamp_after",
            "timestamp_before",
            "date",
            "is_valid",
            "approve_status",
            "attendance_geolocation",
            "attendance_wifi_device",
            "is_pending",
        ]
