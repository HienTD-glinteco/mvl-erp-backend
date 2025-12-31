import django_filters

from apps.payroll.models import EmployeeKPIAssessment


class EmployeeKPIAssessmentFilterSet(django_filters.FilterSet):
    """FilterSet for EmployeeKPIAssessment model.

    Provides filtering by:
    - employee (exact match by ID)
    - employee_username (exact match)
    - employee_position (filter by employee's position)
    - period (exact match by period ID)
    - month (exact match by date via period)
    - month_year (year-month format n/YYYY via period)
    - grade_manager (multiple values filter)
    - grade_hrm (multiple values filter)
    - status (filter by assessment status)
    - finalized (boolean)
    - branch (filter by employee's branch)
    - block (filter by employee's block)
    - department (filter by employee's department)
    - position (filter by employee's position)
    """

    employee = django_filters.NumberFilter(field_name="employee__id", lookup_expr="exact")
    employee_username = django_filters.CharFilter(field_name="employee__username", lookup_expr="exact")
    employee_position = django_filters.NumberFilter(field_name="employee__position__id", lookup_expr="exact")
    period = django_filters.NumberFilter(field_name="period__id", lookup_expr="exact")
    month = django_filters.DateFilter(field_name="period__month", lookup_expr="exact")
    month_year = django_filters.CharFilter(method="filter_month_year")
    grade_manager = django_filters.CharFilter(method="filter_grade_manager")
    grade_hrm = django_filters.CharFilter(method="filter_grade_hrm")
    finalized = django_filters.BooleanFilter(field_name="finalized")
    branch = django_filters.NumberFilter(field_name="employee__branch__id", lookup_expr="exact")
    block = django_filters.NumberFilter(field_name="employee__block__id", lookup_expr="exact")
    department = django_filters.NumberFilter(field_name="employee__department__id", lookup_expr="exact")
    position = django_filters.NumberFilter(field_name="employee__position__id", lookup_expr="exact")
    status = django_filters.CharFilter(field_name="status", lookup_expr="exact")

    class Meta:
        model = EmployeeKPIAssessment
        fields = [
            "employee",
            "employee_username",
            "employee_position",
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
            "status",
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

    def filter_grade_manager(self, queryset, name, value):
        """Filter by grade_manager allowing multiple values separated by comma."""
        if not value:
            return queryset

        grades = [grade.strip() for grade in value.split(",") if grade.strip()]
        if grades:
            return queryset.filter(grade_manager__in=grades)

        return queryset

    def filter_grade_hrm(self, queryset, name, value):
        """Filter by grade_hrm allowing multiple values separated by comma."""
        if not value:
            return queryset

        grades = [grade.strip() for grade in value.split(",") if grade.strip()]
        if grades:
            return queryset.filter(grade_hrm__in=grades)

        return queryset
