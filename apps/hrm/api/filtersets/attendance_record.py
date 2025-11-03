import django_filters

from apps.hrm.models import AttendanceRecord, Employee


class AttendanceRecordFilterSet(django_filters.FilterSet):
    """FilterSet for AttendanceRecord model."""

    employee = django_filters.NumberFilter(method="filter_employee")
    attendance_code = django_filters.CharFilter(lookup_expr="icontains")
    timestamp_after = django_filters.DateTimeFilter(field_name="timestamp", lookup_expr="gte")
    timestamp_before = django_filters.DateTimeFilter(field_name="timestamp", lookup_expr="lte")
    date = django_filters.DateFilter(field_name="timestamp", lookup_expr="date")

    class Meta:
        model = AttendanceRecord
        fields = [
            "employee",
            "device",
            "attendance_code",
            "timestamp_after",
            "timestamp_before",
            "date",
            "is_valid",
        ]

    def filter_employee(self, queryset, name, value):
        if not value:
            return queryset

        attendance_code = Employee.objects.filter(id=value).values_list("attendance_code", flat=True).first()
        if not attendance_code:
            return queryset.none()

        return queryset.filter(attendance_code=attendance_code)
