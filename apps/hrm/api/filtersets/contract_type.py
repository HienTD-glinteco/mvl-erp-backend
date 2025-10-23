import django_filters

from apps.hrm.models import ContractType


class ContractTypeFilterSet(django_filters.FilterSet):
    """FilterSet for ContractType model."""

    name = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = ContractType
        fields = ["name"]
