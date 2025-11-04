import django_filters
from django.db.models import Q

from apps.hrm.models import EmployeeWorkHistory


class EmployeeWorkHistoryFilterSet(django_filters.FilterSet):
    """FilterSet for EmployeeWorkHistory model."""

    search = django_filters.CharFilter(method="filter_search")
    employee = django_filters.NumberFilter(field_name="employee__id")
    branch = django_filters.NumberFilter(field_name="branch__id")
    block = django_filters.NumberFilter(field_name="block__id")
    department = django_filters.NumberFilter(field_name="department__id")
    position = django_filters.NumberFilter(field_name="position__id")
    date_from = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="date", lookup_expr="lte")

    class Meta:
        model = EmployeeWorkHistory
        fields = [
            "employee",
            "branch",
            "block",
            "department",
            "position",
            "date_from",
            "date_to",
            "search",
        ]

    def filter_search(self, queryset, name, value):
        """Search across employee code, employee name, event name, and details."""
        if not value:
            return queryset

        return queryset.filter(
            Q(employee__code__icontains=value)
            | Q(employee__fullname__icontains=value)
            | Q(name__icontains=value)
            | Q(detail__icontains=value)
        )
