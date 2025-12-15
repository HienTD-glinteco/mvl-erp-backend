import django_filters

from apps.payroll.models import KPICriterion


class KPICriterionFilterSet(django_filters.FilterSet):
    """FilterSet for KPICriterion model.

    Provides filtering by:
    - target (exact match)
    - evaluation_type (exact match)
    - active (boolean)
    - criterion (case-insensitive contains)
    - description (case-insensitive contains)
    """

    target = django_filters.CharFilter(field_name="target", lookup_expr="exact")
    evaluation_type = django_filters.CharFilter(field_name="evaluation_type", lookup_expr="exact")
    active = django_filters.BooleanFilter(field_name="active")
    criterion = django_filters.CharFilter(field_name="criterion", lookup_expr="icontains")
    description = django_filters.CharFilter(field_name="description", lookup_expr="icontains")

    class Meta:
        model = KPICriterion
        fields = ["target", "evaluation_type", "active", "criterion", "description"]
