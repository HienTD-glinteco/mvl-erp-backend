import django_filters

from apps.realestate.models import Project


class ProjectFilterSet(django_filters.FilterSet):
    """FilterSet for Project model"""

    name = django_filters.CharFilter(lookup_expr="icontains")
    code = django_filters.CharFilter(lookup_expr="icontains")
    status = django_filters.CharFilter(field_name="status")

    class Meta:
        model = Project
        fields = ["name", "code", "status", "is_active"]
