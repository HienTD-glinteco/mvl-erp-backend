import django_filters

from apps.hrm.models import Bank


class BankFilterSet(django_filters.FilterSet):
    """FilterSet for Bank model"""

    name = django_filters.CharFilter(lookup_expr="icontains")
    code = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = Bank
        fields = ["name", "code"]
