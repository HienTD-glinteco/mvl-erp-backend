import django_filters

from apps.core.models import AdministrativeUnit


class AdministrativeUnitFilterSet(django_filters.FilterSet):
    """FilterSet for AdministrativeUnit model"""

    enabled = django_filters.BooleanFilter()
    parent_province = django_filters.NumberFilter(field_name="parent_province__id")
    level = django_filters.ChoiceFilter(choices=AdministrativeUnit.UnitLevel.choices)
    name = django_filters.CharFilter(lookup_expr="icontains")
    code = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = AdministrativeUnit
        fields = ["enabled", "parent_province", "level", "name", "code"]
