"""FilterSet for SalesRevenueReportFlatModel."""

from datetime import date

import django_filters

from apps.payroll.models import SalesRevenueReportFlatModel


class SalesRevenueReportFilterSet(django_filters.FilterSet):
    """FilterSet for sales revenue reports.

    Provides filtering by organizational hierarchy and date range.
    Default: last 6 months if no date range specified.
    """

    branch = django_filters.NumberFilter(field_name="branch__id")
    block = django_filters.NumberFilter(field_name="block__id")
    department = django_filters.NumberFilter(field_name="department__id")
    from_month = django_filters.CharFilter(method="filter_from_month")
    to_month = django_filters.CharFilter(method="filter_to_month")

    class Meta:
        model = SalesRevenueReportFlatModel
        fields = ["branch", "block", "department", "from_month", "to_month"]

    def filter_from_month(self, queryset, name, value):
        """Filter by from_month in MM/YYYY format."""
        if not value:
            return queryset

        try:
            parts = value.split("/")
            if len(parts) != 2:
                return queryset

            month_str, year_str = parts
            month = int(month_str)
            year = int(year_str)

            if month < 1 or month > 12:
                return queryset

            from_date = date(year, month, 1)
            return queryset.filter(report_date__gte=from_date)

        except (ValueError, TypeError):
            return queryset

    def filter_to_month(self, queryset, name, value):
        """Filter by to_month in MM/YYYY format."""
        if not value:
            return queryset

        try:
            parts = value.split("/")
            if len(parts) != 2:
                return queryset

            month_str, year_str = parts
            month = int(month_str)
            year = int(year_str)

            if month < 1 or month > 12:
                return queryset

            to_date = date(year, month, 1)
            return queryset.filter(report_date__lte=to_date)

        except (ValueError, TypeError):
            return queryset
