"""Serializers for Sales Revenue Report APIs."""

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers


class SalesRevenueReportFieldValueSerializer(serializers.Serializer):
    """Serializer for field-value pair in report data."""

    field = serializers.CharField(help_text=_("Field name"))
    value = serializers.DecimalField(
        max_digits=20, decimal_places=2, coerce_to_string=False, help_text=_("Field value")
    )


class SalesRevenueReportListItemSerializer(serializers.Serializer):
    """Serializer for list action response items."""

    label = serializers.CharField(help_text=_("Month key in MM/YYYY format"))
    data = SalesRevenueReportFieldValueSerializer(many=True, help_text=_("List of field-value pairs"))


class SalesRevenueReportChartDataItemSerializer(serializers.Serializer):
    """Serializer for chart data items."""

    month = serializers.CharField(help_text=_("Month in MM/YYYY format"))
    employees_with_revenue = serializers.IntegerField(help_text=_("Number of employees who generated revenue"))
    total_employees = serializers.IntegerField(help_text=_("Total number of sales employees"))
    percentage = serializers.DecimalField(
        max_digits=7,
        decimal_places=2,
        coerce_to_string=False,
        help_text=_("Percentage of employees with revenue"),
    )


class SalesRevenueReportChartResponseSerializer(serializers.Serializer):
    """Serializer for chart action response."""

    labels = serializers.ListField(
        child=serializers.CharField(),
        help_text=_("Fixed labels for the chart"),
    )
    data = SalesRevenueReportChartDataItemSerializer(many=True, help_text=_("Monthly chart data"))
