import django_filters

from apps.hrm.models import RecruitmentSource


class RecruitmentSourceFilterSet(django_filters.FilterSet):
    """FilterSet for RecruitmentSource model"""

    name = django_filters.CharFilter(lookup_expr="icontains")
    code = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = RecruitmentSource
        fields = ["name", "code"]
