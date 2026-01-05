import django_filters

from apps.payroll.models import PayrollSlip


class PayrollSlipFilterSet(django_filters.FilterSet):
    """FilterSet for PayrollSlip model.

    Provides filtering by:
    - salary_period (exact match by period ID)
    - salary_period__month (exact match, gte, lte for date range)
    - month_year (year-month format n/YYYY via salary_period__month)
    - status (exact match, multiple values via __in)
    - employee (exact match by employee ID)
    - employee_code (exact match, icontains for partial match)
    - employee_name (icontains for partial match)
    - employee_email (exact match, icontains for partial match)
    - tax_code (exact match, icontains for partial match)
    - department_name (exact match, icontains for partial match)
    - position_name (exact match, icontains for partial match)
    - has_unpaid_penalty (boolean)
    - need_resend_email (boolean)
    - calculated_at (date range filtering, isnull for null check)
    - created_at (date range filtering)
    """

    salary_period = django_filters.NumberFilter(field_name="salary_period__id", lookup_expr="exact")
    salary_period__month = django_filters.DateFilter(field_name="salary_period__month", lookup_expr="exact")
    salary_period__month__gte = django_filters.DateFilter(field_name="salary_period__month", lookup_expr="gte")
    salary_period__month__lte = django_filters.DateFilter(field_name="salary_period__month", lookup_expr="lte")
    month_year = django_filters.CharFilter(method="filter_month_year")
    status = django_filters.CharFilter(field_name="status", lookup_expr="exact")
    status__in = django_filters.CharFilter(method="filter_status_in")
    employee = django_filters.NumberFilter(field_name="employee__id", lookup_expr="exact")
    employee_code = django_filters.CharFilter(field_name="employee_code", lookup_expr="exact")
    employee_code__icontains = django_filters.CharFilter(field_name="employee_code", lookup_expr="icontains")
    employee_name = django_filters.CharFilter(field_name="employee_name", lookup_expr="icontains")
    employee_email = django_filters.CharFilter(field_name="employee_email", lookup_expr="exact")
    employee_email__icontains = django_filters.CharFilter(field_name="employee_email", lookup_expr="icontains")
    tax_code = django_filters.CharFilter(field_name="tax_code", lookup_expr="exact")
    tax_code__icontains = django_filters.CharFilter(field_name="tax_code", lookup_expr="icontains")
    department_name = django_filters.CharFilter(field_name="department_name", lookup_expr="exact")
    department_name__icontains = django_filters.CharFilter(field_name="department_name", lookup_expr="icontains")
    position_name = django_filters.CharFilter(field_name="position_name", lookup_expr="exact")
    position_name__icontains = django_filters.CharFilter(field_name="position_name", lookup_expr="icontains")
    has_unpaid_penalty = django_filters.BooleanFilter(field_name="has_unpaid_penalty")
    need_resend_email = django_filters.BooleanFilter(field_name="need_resend_email")
    calculated_at__gte = django_filters.DateTimeFilter(field_name="calculated_at", lookup_expr="gte")
    calculated_at__lte = django_filters.DateTimeFilter(field_name="calculated_at", lookup_expr="lte")
    calculated_at__isnull = django_filters.BooleanFilter(field_name="calculated_at", lookup_expr="isnull")
    created_at__gte = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_at__lte = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = PayrollSlip
        fields = [
            "salary_period",
            "salary_period__month",
            "salary_period__month__gte",
            "salary_period__month__lte",
            "month_year",
            "status",
            "status__in",
            "employee",
            "employee_code",
            "employee_code__icontains",
            "employee_name",
            "employee_email",
            "employee_email__icontains",
            "tax_code",
            "tax_code__icontains",
            "department_name",
            "department_name__icontains",
            "position_name",
            "position_name__icontains",
            "has_unpaid_penalty",
            "need_resend_email",
            "calculated_at__gte",
            "calculated_at__lte",
            "calculated_at__isnull",
            "created_at__gte",
            "created_at__lte",
        ]

    def filter_month_year(self, queryset, name, value):
        """Filter by month in n/YYYY format via salary_period__month (e.g., 1/2025, 12/2025)."""
        if not value:
            return queryset

        try:
            # Parse n/YYYY format
            parts = value.split("/")
            if len(parts) == 2:
                month_num = int(parts[0])
                year = int(parts[1])
                return queryset.filter(salary_period__month__year=year, salary_period__month__month=month_num)
        except (ValueError, IndexError):
            pass

        return queryset

    def filter_status_in(self, queryset, name, value):
        """Filter by status allowing multiple values separated by comma."""
        if not value:
            return queryset

        statuses = [status.strip() for status in value.split(",") if status.strip()]
        if statuses:
            return queryset.filter(status__in=statuses)

        return queryset
