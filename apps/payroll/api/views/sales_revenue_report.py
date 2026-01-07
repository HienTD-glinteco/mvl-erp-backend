"""ViewSet for Sales Revenue Report APIs."""

from datetime import date, timedelta

from django.db.models import Sum
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.payroll.api.filtersets import SalesRevenueReportFilterSet
from apps.payroll.api.serializers import (
    SalesRevenueReportChartResponseSerializer,
    SalesRevenueReportListItemSerializer,
)
from apps.payroll.models import SalesRevenueReportFlatModel
from libs.drf.base_viewset import BaseGenericViewSet
from libs.export_xlsx.mixins import ExportXLSXMixin


@extend_schema_view(
    export=extend_schema(
        tags=["10.5.1: Sales Personnel Quality Report"],
    ),
)
class SalesRevenueReportViewSet(ExportXLSXMixin, BaseGenericViewSet):
    """ViewSet for sales revenue reports.

    Provides two main actions:
    - list: Returns aggregated monthly data grouped by month (default: last 6 months)
    - chart: Returns data formatted for dashboard chart visualization (default: current year)

    Both actions support filtering by organizational hierarchy and date range.
    """

    queryset = SalesRevenueReportFlatModel.objects.select_related("branch", "block", "department").all()
    filterset_class = SalesRevenueReportFilterSet
    serializer_class = SalesRevenueReportListItemSerializer

    module = _("Payroll")
    submodule = _("Sales Revenue Reports")
    permission_prefix = "sales_revenue_report"

    PERMISSION_REGISTERED_ACTIONS = {
        "list": {
            "name_template": _("View sales revenue quality reports"),
            "description_template": _("View list of sales revenue quality reports"),
        },
        "chart": {
            "name_template": _("View sales revenue chart"),
            "description_template": _("View sales revenue chart data for dashboard"),
        },
        "export": {
            "name_template": _("Export sales revenue quality reports"),
            "description_template": _("Export sales revenue quality reports to file"),
        },
    }

    def _apply_default_6_months_filter(self, queryset):
        """Apply default filter for last 6 months if no date range specified."""
        request = self.request
        if not request.query_params.get("from_month") and not request.query_params.get("to_month"):
            today = date.today()
            # Get first day of current month
            current_month_start = date(today.year, today.month, 1)
            # Go back 6 months
            six_months_ago = current_month_start - timedelta(days=180)
            from_date = date(six_months_ago.year, six_months_ago.month, 1)
            queryset = queryset.filter(report_date__gte=from_date, report_date__lte=current_month_start)
        return queryset

    def _apply_default_year_filter(self, queryset):
        """Apply default filter for current year if no date range specified."""
        request = self.request
        if not request.query_params.get("from_month") and not request.query_params.get("to_month"):
            current_year = date.today().year
            first_day_of_year = date(current_year, 1, 1)
            last_day_of_year = date(current_year, 12, 31)
            queryset = queryset.filter(report_date__gte=first_day_of_year, report_date__lte=last_day_of_year)
        return queryset

    @extend_schema(
        summary="List sales revenue quality report",
        description=(
            "Get aggregated sales revenue report data grouped by month. "
            "Returns list of monthly metrics including targets, revenue, employee counts, and percentages. "
            "Default: last 6 months. No pagination."
        ),
        responses={200: SalesRevenueReportListItemSerializer(many=True)},
        tags=["10.5.1: Sales Personnel Quality Report"],
    )
    def list(self, request, *args, **kwargs):
        """List action - returns monthly aggregated data."""
        # Get filtered queryset with default 6 months
        queryset = self.filter_queryset(self.get_queryset())
        queryset = self._apply_default_6_months_filter(queryset)

        # Group by month and aggregate
        monthly_data = (
            queryset.values("month_key")
            .annotate(
                total_kpi_target=Sum("total_kpi_target"),
                total_revenue=Sum("total_revenue"),
                employees_with_revenue=Sum("employees_with_revenue"),
                total_sales_employees=Sum("total_sales_employees"),
            )
            .order_by("month_key")
        )

        # Format response
        result = []
        for month_data in monthly_data:
            # Calculate percentages for aggregated data
            total_kpi_target = float(month_data["total_kpi_target"] or 0)
            total_revenue = float(month_data["total_revenue"] or 0)
            employees_with_revenue = month_data["employees_with_revenue"] or 0
            total_sales_employees = month_data["total_sales_employees"] or 0

            if total_kpi_target > 0:
                revenue_vs_target = round((total_revenue / total_kpi_target) * 100, 2)
            else:
                revenue_vs_target = 0.00

            if total_sales_employees > 0:
                employee_with_revenue_percent = round((employees_with_revenue / total_sales_employees) * 100, 2)
                avg_revenue_per_employee = round(total_revenue / total_sales_employees, 2)
            else:
                employee_with_revenue_percent = 0.00
                avg_revenue_per_employee = 0.00

            # Response format: list of {field, value} pairs
            result.append(
                {
                    "label": month_data["month_key"],
                    "data": [
                        {"field": _("KPI Target"), "value": total_kpi_target},
                        {"field": _("Total Revenue"), "value": total_revenue},
                        {"field": _("Employees with Revenue"), "value": employees_with_revenue},
                        {"field": _("Total Sales Employees"), "value": total_sales_employees},
                        {"field": _("Revenue vs Target (%)"), "value": revenue_vs_target},
                        {"field": _("Employee with Revenue (%)"), "value": employee_with_revenue_percent},
                        {"field": _("Average Revenue per Employee"), "value": avg_revenue_per_employee},
                    ],
                }
            )

        return Response(result)

    @extend_schema(
        summary="Get chart data for dashboard",
        description=(
            "Get sales revenue data formatted for dashboard column chart. "
            "Returns employee counts and percentages by month. "
            "Default: current year."
        ),
        filters=True,
        responses={200: SalesRevenueReportChartResponseSerializer},
        tags=["10.5.1: Sales Personnel Quality Report"],
    )
    @action(detail=False, methods=["get"])
    def chart(self, request, *args, **kwargs):
        """Chart action - returns data for dashboard visualization."""
        # Get filtered queryset with default current year
        queryset = self.filter_queryset(self.get_queryset())
        queryset = self._apply_default_year_filter(queryset)

        # Group by month and aggregate
        monthly_data = (
            queryset.values("month_key")
            .annotate(
                employees_with_revenue=Sum("employees_with_revenue"),
                total_sales_employees=Sum("total_sales_employees"),
            )
            .order_by("month_key")
        )

        # Format chart data
        chart_data = []
        for month_data in monthly_data:
            employees_with_revenue = month_data["employees_with_revenue"] or 0
            total_sales_employees = month_data["total_sales_employees"] or 0

            if total_sales_employees > 0:
                percentage = round((employees_with_revenue / total_sales_employees) * 100, 2)
            else:
                percentage = 0.00

            chart_data.append(
                {
                    "month": month_data["month_key"],
                    "employees_with_revenue": employees_with_revenue,
                    "total_employees": total_sales_employees,
                    "percentage": percentage,
                }
            )

        response_data = {
            "labels": [_("Total Employees"), _("Employees with Revenue")],
            "data": chart_data,
        }

        serializer = SalesRevenueReportChartResponseSerializer(response_data)
        return Response(serializer.data)

    def get_export_data(self, request):
        """Custom export data for sales revenue reports."""
        # Reuse list logic
        list_response = self.list(request)
        data = list_response.data

        # Transform for export - flatten the list of field/value pairs
        export_rows = []
        for item in data:
            row = {_("Month"): item["label"]}
            for field_value in item["data"]:
                row[field_value["field"]] = field_value["value"]
            export_rows.append(row)

        return {
            "sheets": [
                {
                    "name": str(_("Sales Revenue Quality Report")),
                    "headers": list(export_rows[0].keys()) if export_rows else [],
                    "field_names": list(export_rows[0].keys()) if export_rows else [],
                    "data": export_rows,
                }
            ]
        }
