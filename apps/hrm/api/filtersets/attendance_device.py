import django_filters

from apps.hrm.models import AttendanceDevice


class AttendanceDeviceFilterSet(django_filters.FilterSet):
    """FilterSet for AttendanceDevice model."""

    name = django_filters.CharFilter(lookup_expr="icontains")
    location = django_filters.CharFilter(lookup_expr="icontains")
    ip_address = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = AttendanceDevice
        fields = [
            "name",
            "location",
            "ip_address",
            "is_enabled",
            "is_connected",
        ]
