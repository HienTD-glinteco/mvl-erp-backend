import django_filters

from apps.hrm.models import JobDescription


class JobDescriptionFilterSet(django_filters.FilterSet):
    """FilterSet for JobDescription model"""

    title = django_filters.CharFilter(lookup_expr="icontains")
    code = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = JobDescription
        fields = ["title", "code"]
