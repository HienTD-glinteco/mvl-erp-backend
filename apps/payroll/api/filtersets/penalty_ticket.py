"""FilterSet for PenaltyTicket model."""

import django_filters

from apps.payroll.models import PenaltyTicket


class PenaltyTicketFilterSet(django_filters.FilterSet):
    """FilterSet for PenaltyTicket model."""

    month = django_filters.CharFilter(method="filter_month")
    employee_code = django_filters.CharFilter(field_name="employee_code", lookup_expr="exact")
    status = django_filters.ChoiceFilter(
        field_name="status", choices=PenaltyTicket.Status.choices, lookup_expr="exact"
    )
    # Organizational hierarchy filters through employee
    branch = django_filters.NumberFilter(field_name="employee__branch__id")
    block = django_filters.NumberFilter(field_name="employee__block__id")
    department = django_filters.NumberFilter(field_name="employee__department__id")
    position = django_filters.NumberFilter(field_name="employee__position__id")
    employee = django_filters.NumberFilter(field_name="employee__id")
    payment_date = django_filters.DateFilter(field_name="payment_date", lookup_expr="exact")

    class Meta:
        model = PenaltyTicket
        fields = [
            "month",
            "branch",
            "block",
            "department",
            "position",
            "employee",
            "employee_code",
            "status",
            "payment_date",
        ]

    def filter_month(self, queryset, name, value):
        """Filter by month in MM/YYYY format."""
        if not value:
            return queryset

        try:
            month, year = value.split("/")
            month = int(month)
            year = int(year)

            if month < 1 or month > 12:
                return queryset.none()

            return queryset.filter(month__year=year, month__month=month)

        except (ValueError, AttributeError):
            return queryset
