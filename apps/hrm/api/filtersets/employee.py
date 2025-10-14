import django_filters

from apps.hrm.models import Employee


class EmployeeFilterSet(django_filters.FilterSet):
    """FilterSet for Employee model"""

    code = django_filters.CharFilter(lookup_expr="icontains")
    fullname = django_filters.CharFilter(lookup_expr="icontains")
    username = django_filters.CharFilter(lookup_expr="icontains")
    email = django_filters.CharFilter(lookup_expr="icontains")
    phone = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = Employee
        fields = ["code", "fullname", "username", "email", "phone", "branch", "block", "department"]
