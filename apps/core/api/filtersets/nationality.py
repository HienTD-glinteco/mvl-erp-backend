import django_filters

from apps.core.models import Nationality


class NationalityFilterSet(django_filters.FilterSet):
    """FilterSet for Nationality model"""

    name = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = Nationality
        fields = ["name"]
