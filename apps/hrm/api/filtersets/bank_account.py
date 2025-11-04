import django_filters

from apps.hrm.models import BankAccount


class BankAccountFilterSet(django_filters.FilterSet):
    """FilterSet for BankAccount model"""

    employee = django_filters.NumberFilter(field_name="employee__id")
    bank = django_filters.NumberFilter(field_name="bank__id")
    account_number = django_filters.CharFilter(lookup_expr="icontains")
    account_name = django_filters.CharFilter(lookup_expr="icontains")
    is_primary = django_filters.BooleanFilter()

    class Meta:
        model = BankAccount
        fields = ["employee", "bank", "account_number", "account_name", "is_primary"]
