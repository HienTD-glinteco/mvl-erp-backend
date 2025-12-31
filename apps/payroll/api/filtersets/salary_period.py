import django_filters

from apps.payroll.models import SalaryPeriod


class SalaryPeriodFilterSet(django_filters.FilterSet):
    """FilterSet for SalaryPeriod model.

    Provides filtering by:
    - status (exact match by status value)
    - month (exact match, gte, lte for date range)
    - month_year (year-month format n/YYYY via month field)
    - code (exact match, icontains for partial match)
    - proposal_deadline (date range filtering)
    - kpi_assessment_deadline (date range filtering)
    - created_at (date range filtering)
    - updated_at (date range filtering)
    """

    status = django_filters.CharFilter(field_name="status", lookup_expr="exact")
    month = django_filters.DateFilter(field_name="month", lookup_expr="exact")
    month__gte = django_filters.DateFilter(field_name="month", lookup_expr="gte")
    month__lte = django_filters.DateFilter(field_name="month", lookup_expr="lte")
    month_year = django_filters.CharFilter(method="filter_month_year")
    code = django_filters.CharFilter(field_name="code", lookup_expr="exact")
    code__icontains = django_filters.CharFilter(field_name="code", lookup_expr="icontains")
    proposal_deadline__gte = django_filters.DateFilter(field_name="proposal_deadline", lookup_expr="gte")
    proposal_deadline__lte = django_filters.DateFilter(field_name="proposal_deadline", lookup_expr="lte")
    kpi_assessment_deadline__gte = django_filters.DateFilter(field_name="kpi_assessment_deadline", lookup_expr="gte")
    kpi_assessment_deadline__lte = django_filters.DateFilter(field_name="kpi_assessment_deadline", lookup_expr="lte")
    created_at__gte = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_at__lte = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")
    updated_at__gte = django_filters.DateTimeFilter(field_name="updated_at", lookup_expr="gte")
    updated_at__lte = django_filters.DateTimeFilter(field_name="updated_at", lookup_expr="lte")

    class Meta:
        model = SalaryPeriod
        fields = [
            "status",
            "month",
            "month__gte",
            "month__lte",
            "month_year",
            "code",
            "code__icontains",
            "proposal_deadline__gte",
            "proposal_deadline__lte",
            "kpi_assessment_deadline__gte",
            "kpi_assessment_deadline__lte",
            "created_at__gte",
            "created_at__lte",
            "updated_at__gte",
            "updated_at__lte",
        ]

    def filter_month_year(self, queryset, name, value):
        """Filter by month in n/YYYY format (e.g., 1/2025, 12/2025)."""
        if not value:
            return queryset

        try:
            # Parse n/YYYY format
            parts = value.split("/")
            if len(parts) == 2:
                month_num = int(parts[0])
                year = int(parts[1])
                return queryset.filter(month__year=year, month__month=month_num)
        except (ValueError, IndexError):
            pass

        return queryset
