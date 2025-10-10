import django_filters

from apps.hrm.models import RecruitmentChannel


class RecruitmentChannelFilterSet(django_filters.FilterSet):
    """FilterSet for RecruitmentChannel model"""

    name = django_filters.CharFilter(lookup_expr="icontains")
    code = django_filters.CharFilter(lookup_expr="icontains")
    is_active = django_filters.BooleanFilter()

    class Meta:
        model = RecruitmentChannel
        fields = ["name", "code", "is_active"]
