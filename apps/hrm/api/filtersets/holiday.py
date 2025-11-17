import django_filters

from apps.hrm.models import Holiday


class HolidayFilterSet(django_filters.FilterSet):
    """FilterSet for Holiday model with date range overlap filtering."""

    name = django_filters.CharFilter(lookup_expr="icontains")
    start = django_filters.DateFilter(field_name="end_date", lookup_expr="gte")
    end = django_filters.DateFilter(field_name="start_date", lookup_expr="lte")

    class Meta:
        model = Holiday
        fields = ["name", "start", "end"]
