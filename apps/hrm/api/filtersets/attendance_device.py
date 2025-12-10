import django_filters

from apps.hrm.models import AttendanceDevice


class AttendanceDeviceFilterSet(django_filters.FilterSet):
    """FilterSet for AttendanceDevice model."""

    name = django_filters.CharFilter(lookup_expr="icontains")
    block = django_filters.NumberFilter(field_name="block")

    class Meta:
        model = AttendanceDevice
        fields = [
            "name",
            "block",
            "is_enabled",
            "is_connected",
        ]
