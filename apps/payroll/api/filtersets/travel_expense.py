from datetime import date

import django_filters

from apps.payroll.models import TravelExpense


class TravelExpenseFilterSet(django_filters.FilterSet):
    """FilterSet for TravelExpense model.

    Provides filtering by expense_type, month, status, and organizational hierarchy
    (branch, block, department, position) through employee relationships.
    Month filter accepts MM/YYYY format and converts to first day of month.
    """

    expense_type = django_filters.ChoiceFilter(
        field_name="expense_type",
        choices=TravelExpense.ExpenseType.choices,
    )
    month = django_filters.CharFilter(method="filter_month")
    status = django_filters.ChoiceFilter(
        field_name="status",
        choices=TravelExpense.TravelExpenseStatus.choices,
    )

    # Organizational hierarchy filters through employee
    branch = django_filters.NumberFilter(field_name="employee__branch__id")
    block = django_filters.NumberFilter(field_name="employee__block__id")
    department = django_filters.NumberFilter(field_name="employee__department__id")
    position = django_filters.NumberFilter(field_name="employee__position__id")
    employee = django_filters.NumberFilter(field_name="employee__id")

    class Meta:
        model = TravelExpense
        fields = [
            "expense_type",
            "month",
            "status",
            "branch",
            "block",
            "department",
            "position",
            "employee",
        ]

    def filter_month(self, queryset, name, value):
        """Filter by month in MM/YYYY format."""
        if not value:
            return queryset

        try:
            # Parse MM/YYYY format
            parts = value.split("/")
            if len(parts) != 2:
                return queryset

            month_str, year_str = parts
            month = int(month_str)
            year = int(year_str)

            if month < 1 or month > 12:
                return queryset

            # Filter by first day of the month
            month_date = date(year, month, 1)
            return queryset.filter(month=month_date)

        except (ValueError, TypeError):
            return queryset
