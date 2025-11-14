import django_filters

from apps.hrm.models import ProjectGeolocation


class ProjectGeolocationFilterSet(django_filters.FilterSet):
    """FilterSet for ProjectGeolocation model"""

    project = django_filters.NumberFilter(field_name="project__id")
    status = django_filters.CharFilter(field_name="status")

    class Meta:
        model = ProjectGeolocation
        fields = ["project", "status"]
