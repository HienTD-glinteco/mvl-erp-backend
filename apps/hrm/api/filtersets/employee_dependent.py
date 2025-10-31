import django_filters
from django.db.models import Q

from apps.hrm.models import EmployeeDependent


class EmployeeDependentFilterSet(django_filters.FilterSet):
    """FilterSet for EmployeeDependent model."""

    search = django_filters.CharFilter(method="filter_search")
    employee = django_filters.NumberFilter(field_name="employee__id")
    relationship = django_filters.CharFilter(field_name="relationship", lookup_expr="iexact")
    is_active = django_filters.BooleanFilter(field_name="is_active")

    class Meta:
        model = EmployeeDependent
        fields = ["employee", "relationship", "is_active", "search"]

    def filter_search(self, queryset, name, value):
        """Search across employee code, employee name, dependent name, and relationship."""
        if not value:
            return queryset

        return queryset.filter(
            Q(employee__code__icontains=value)
            | Q(employee__fullname__icontains=value)
            | Q(dependent_name__icontains=value)
            | Q(relationship__icontains=value)
        )
