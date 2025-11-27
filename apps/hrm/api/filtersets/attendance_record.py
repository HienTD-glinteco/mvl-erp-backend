import django_filters
from django.db import models

from apps.hrm.models import AttendanceRecord


class AttendanceRecordFilterSet(django_filters.FilterSet):
    """FilterSet for AttendanceRecord model."""

    employee = django_filters.NumberFilter(field_name="employee__id")
    attendance_code = django_filters.CharFilter(field_name="attendance_code", lookup_expr="icontains")
    timestamp_after = django_filters.DateTimeFilter(field_name="timestamp", lookup_expr="gte")
    timestamp_before = django_filters.DateTimeFilter(field_name="timestamp", lookup_expr="lte")
    date = django_filters.DateFilter(field_name="timestamp", lookup_expr="date")

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
            "attendance_geolocation",
            "attendance_wifi_device",
        ]
