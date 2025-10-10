import django_filters

from apps.hrm.models import RecruitmentChannel


class RecruitmentChannelFilterSet(django_filters.FilterSet):
    """FilterSet for RecruitmentChannel model"""

    name = django_filters.CharFilter(lookup_expr="icontains")
    code = django_filters.CharFilter(lookup_expr="icontains")
    belong_to = django_filters.ChoiceFilter(choices=RecruitmentChannel.BelongTo.choices)
    is_active = django_filters.BooleanFilter()

    class Meta:
        model = RecruitmentChannel
        fields = ["name", "code", "belong_to", "is_active"]
