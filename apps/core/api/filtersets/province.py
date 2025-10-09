import django_filters

from apps.core.models import Province


class ProvinceFilterSet(django_filters.FilterSet):
    """FilterSet for Province model"""

    enabled = django_filters.BooleanFilter()
    level = django_filters.ChoiceFilter(choices=Province.ProvinceLevel.choices)
    name = django_filters.CharFilter(lookup_expr="icontains")
    code = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = Province
        fields = ["enabled", "level", "name", "code"]
