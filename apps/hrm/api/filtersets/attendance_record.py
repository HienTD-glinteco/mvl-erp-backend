import django_filters

from apps.hrm.models import AttendanceRecord


class AttendanceRecordFilterSet(django_filters.FilterSet):
    """FilterSet for AttendanceRecord model."""

    attendance_code = django_filters.CharFilter(lookup_expr="icontains")
    timestamp_after = django_filters.DateTimeFilter(field_name="timestamp", lookup_expr="gte")
    timestamp_before = django_filters.DateTimeFilter(field_name="timestamp", lookup_expr="lte")
    date = django_filters.DateFilter(field_name="timestamp", lookup_expr="date")

    class Meta:
        model = AttendanceRecord
        fields = [
            "device",
            "attendance_code",
            "timestamp_after",
            "timestamp_before",
            "date",
        ]
