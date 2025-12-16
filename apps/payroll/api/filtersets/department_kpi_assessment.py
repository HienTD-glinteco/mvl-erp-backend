import django_filters

from apps.payroll.models import DepartmentKPIAssessment


class DepartmentKPIAssessmentFilterSet(django_filters.FilterSet):
    """FilterSet for DepartmentKPIAssessment model.

    Provides filtering by:
    - department (exact match by ID)
    - department_code (exact match)
    - period (exact match by period ID)
    - month (exact match by date via period)
    - month_year (year-month format YYYY-MM via period)
    - grade (exact match)
    - finalized (boolean)
    - auto_assigned_to_employees (boolean)
    """

    department = django_filters.NumberFilter(field_name="department__id", lookup_expr="exact")
    department_code = django_filters.CharFilter(field_name="department__code", lookup_expr="exact")
    period = django_filters.NumberFilter(field_name="period__id", lookup_expr="exact")
    month = django_filters.DateFilter(field_name="period__month", lookup_expr="exact")
    month_year = django_filters.CharFilter(method="filter_month_year")
    grade = django_filters.CharFilter(field_name="grade", lookup_expr="exact")
    finalized = django_filters.BooleanFilter(field_name="finalized")
    auto_assigned_to_employees = django_filters.BooleanFilter(field_name="auto_assigned_to_employees")

    class Meta:
        model = DepartmentKPIAssessment
        fields = [
            "department",
            "department_code",
            "period",
            "month",
            "month_year",
            "grade",
            "finalized",
            "auto_assigned_to_employees",
        ]

    def filter_month_year(self, queryset, name, value):
        """Filter by month in YYYY-MM format."""
        if not value:
            return queryset

        try:
            # Parse YYYY-MM format
            parts = value.split("-")
            if len(parts) == 2:
                year = int(parts[0])
                month_num = int(parts[1])
                return queryset.filter(period__month__year=year, period__month__month=month_num)
        except (ValueError, IndexError):
            pass

        return queryset
