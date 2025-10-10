import django_filters

from apps.hrm.models import Employee


class EmployeeFilterSet(django_filters.FilterSet):
    """FilterSet for Employee model"""

    code = django_filters.CharFilter(lookup_expr="icontains")
    name = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = Employee
        fields = ["code", "name"]
