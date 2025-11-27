import django_filters

from apps.hrm.models import AttendanceGeolocation


class AttendanceGeolocationFilterSet(django_filters.FilterSet):
    """FilterSet for AttendanceGeolocation model"""

    project = django_filters.NumberFilter(field_name="project__id")
    status = django_filters.CharFilter(field_name="status")
    user_latitude = django_filters.NumberFilter(
        method="filter_dummy", help_text="User's current latitude for distance-based sorting"
    )
    user_longitude = django_filters.NumberFilter(
        method="filter_dummy", help_text="User's current longitude for distance-based sorting"
    )

    class Meta:
        model = AttendanceGeolocation
        fields = ["project", "status", "user_latitude", "user_longitude"]

    def filter_dummy(self, queryset, name, value):
        """Dummy filter method - actual filtering is done by DistanceOrderingFilterBackend"""
        return queryset
