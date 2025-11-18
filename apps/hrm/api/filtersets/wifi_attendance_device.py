import django_filters

from apps.hrm.models import WifiAttendanceDevice


class WifiAttendanceDeviceFilterSet(django_filters.FilterSet):
    """FilterSet for WifiAttendanceDevice model"""

    branch = django_filters.NumberFilter(field_name="branch__id")
    block = django_filters.NumberFilter(field_name="block__id")
    state = django_filters.CharFilter(field_name="state")

    class Meta:
        model = WifiAttendanceDevice
        fields = ["branch", "block", "state"]
