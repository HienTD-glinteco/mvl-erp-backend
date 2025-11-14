import django_filters

from apps.hrm.models import AttendanceGeolocation


class AttendanceGeolocationFilterSet(django_filters.FilterSet):
    """FilterSet for AttendanceGeolocation model"""

    project = django_filters.NumberFilter(field_name="project__id")
    status = django_filters.CharFilter(field_name="status")

    class Meta:
        model = AttendanceGeolocation
        fields = ["project", "status"]
