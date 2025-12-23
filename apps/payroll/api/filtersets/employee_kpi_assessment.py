import django_filters

from apps.payroll.models import EmployeeKPIAssessment


class EmployeeKPIAssessmentFilterSet(django_filters.FilterSet):
    """FilterSet for EmployeeKPIAssessment model.

    Provides filtering by:
    - employee (exact match by ID)
    - employee_username (exact match)
    - period (exact match by period ID)
    - month (exact match by date via period)
    - month_year (year-month format n/YYYY via period)
    - grade_manager (exact match)
    - grade_hrm (exact match)
    - finalized (boolean)
    - branch (filter by employee's branch)
    - block (filter by employee's block)
    - department (filter by employee's department)
    - position (filter by employee's position)
    """

    employee = django_filters.NumberFilter(field_name="employee__id", lookup_expr="exact")
    employee_username = django_filters.CharFilter(field_name="employee__username", lookup_expr="exact")
    period = django_filters.NumberFilter(field_name="period__id", lookup_expr="exact")
    month = django_filters.DateFilter(field_name="period__month", lookup_expr="exact")
    month_year = django_filters.CharFilter(method="filter_month_year")
    grade_manager = django_filters.CharFilter(field_name="grade_manager", lookup_expr="exact")
    grade_hrm = django_filters.CharFilter(field_name="grade_hrm", lookup_expr="exact")
    finalized = django_filters.BooleanFilter(field_name="finalized")
    branch = django_filters.NumberFilter(field_name="employee__branch__id", lookup_expr="exact")
    block = django_filters.NumberFilter(field_name="employee__block__id", lookup_expr="exact")
    department = django_filters.NumberFilter(field_name="employee__department__id", lookup_expr="exact")
    position = django_filters.NumberFilter(field_name="employee__position__", lookup_expr="exact")

    class Meta:
        model = EmployeeKPIAssessment
        fields = [
            "employee",
            "employee_username",
            "period",
            "month",
            "month_year",
            "grade_manager",
            "grade_hrm",
            "finalized",
            "branch",
            "block",
            "department",
            "position",
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
                return queryset.filter(period__month__year=year, period__month__month=month_num)
        except (ValueError, IndexError):
            pass

        return queryset
