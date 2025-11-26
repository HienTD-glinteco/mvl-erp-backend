import django_filters
from django.db import models

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
            "attendance_type",
            "attendance_code",
            "timestamp_after",
            "timestamp_before",
            "date",
            "is_valid",
            "attendance_geolocation",
            "attendance_wifi_device",
        ]

    def filter_employee(self, queryset, name, value):
        """Filter by employee ID - checks both employee field and attendance_code match."""
        if not value:
            return queryset

        # Filter by direct employee FK or by matching attendance_code
        attendance_code = Employee.objects.filter(id=value).values_list("attendance_code", flat=True).first()
        if not attendance_code:
            return queryset.none()

        return queryset.filter(
            models.Q(employee_id=value) | models.Q(attendance_code=attendance_code)
        )
