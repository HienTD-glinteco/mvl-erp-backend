from datetime import date

import django_filters

from apps.payroll.models import RecoveryVoucher


class RecoveryVoucherFilterSet(django_filters.FilterSet):
    """FilterSet for RecoveryVoucher with search and filter capabilities."""

    voucher_type = django_filters.ChoiceFilter(
        field_name="voucher_type",
        choices=RecoveryVoucher.VoucherType.choices,
    )
    status = django_filters.ChoiceFilter(
        field_name="status",
        choices=RecoveryVoucher.RecoveryVoucherStatus.choices,
    )
    employee_id = django_filters.UUIDFilter(field_name="employee__id")
    month = django_filters.CharFilter(method="filter_month")
    amount_min = django_filters.NumberFilter(field_name="amount", lookup_expr="gte")
    amount_max = django_filters.NumberFilter(field_name="amount", lookup_expr="lte")

    class Meta:
        model = RecoveryVoucher
        fields = ["voucher_type", "status", "employee_id", "month", "amount_min", "amount_max"]

    def filter_month(self, queryset, name, value):
        """Filter by month in MM/YYYY format."""
        try:
            # Parse MM/YYYY format
            month, year = value.split("/")
            month = int(month)
            year = int(year)

            month_date = date(year, month, 1)

            return queryset.filter(month=month_date)
        except (ValueError, AttributeError):
            # Invalid format, return empty queryset
            return queryset.none()
