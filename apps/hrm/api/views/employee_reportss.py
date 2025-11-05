from datetime import date, timedelta

from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.hrm.constants import ExtendedReportPeriodType
from apps.hrm.models import Block, Branch, Department, EmployeeStatusBreakdownReport

from ..serializers import (
    EmployeeCountBreakdownReportParamsSerializer,
    EmployeeStatusBreakdownReportAggregatedSerializer,
)


class EmployeeReportsViewSet(viewsets.GenericViewSet):
    """
    ViewSet for employee reports with aggregated data.

    - employee_status_breakdown and employee_resigned_breakdown reports aggregate by week/month periods.
    - Other reports aggregate by organizational hierarchy or source type.
    - All endpoints return full aggregated datasets (no pagination).
    - All API responses use envelope format: {success, data, error}.
    """

    pagination_class = None

    def _generate_time_buckets_for_week(self, from_date: str, to_date: str) -> list[str, date, date]:
        buckets: list[str, date, date] = []

        current = from_date - timedelta(days=from_date.weekday())
        while current <= to_date:
            week_start = max(current, from_date)
            week_end = min(current + timedelta(days=6), to_date)
            iso_year, iso_week, __ = week_start.isocalendar()
            label = f"{_('Week')} {iso_week}/{iso_year}"
            buckets.append((label, week_start, week_end))
            current += timedelta(days=7)

        return buckets

    def _generate_time_buckets_for_month(self, from_date: str, to_date: str) -> list[str, date, date]:
        buckets: list[str, date, date] = []

        year, month = from_date.year, from_date.month
        while True:
            month_start = max(date(year, month, 1), from_date)
            if month == 12:
                month_end = min(date(year + 1, 1, 1) - timedelta(days=1), to_date)
            else:
                month_end = min(date(year, month + 1, 1) - timedelta(days=1), to_date)

            if month_start > to_date:
                break

            label = f"{_('Month')} {month:02d}/{year}"
            buckets.append((label, month_start, month_end))
            if month == 12:
                year += 1
                month = 1
            else:
                month += 1

        return buckets

    def _generate_time_buckets_for_quarter(self, from_date: str, to_date: str) -> list[str, date, date]:
        buckets: list[str, date, date] = []

        year, quarter = from_date.year, (from_date.month - 1) // 3 + 1
        while True:
            q_start_month = (quarter - 1) * 3 + 1
            q_end_month = quarter * 3
            quarter_start = max(date(year, q_start_month, 1), from_date)
            if q_end_month == 12:
                quarter_end = min(date(year + 1, 1, 1) - timedelta(days=1), to_date)
            else:
                quarter_end = min(date(year, q_end_month + 1, 1) - timedelta(days=1), to_date)

            if quarter_start > to_date:
                break

            label = f"{_('Quarter')} {quarter}/{year}"
            buckets.append((label, quarter_start, quarter_end))
            if quarter == 4:
                year += 1
                quarter = 1
            else:
                quarter += 1

        return buckets

    def _generate_time_buckets_for_year(self, from_date: str, to_date: str) -> list[str, date, date]:
        buckets: list[str, date, date] = []

        year = from_date.year
        while True:
            year_start = max(date(year, 1, 1), from_date)
            year_end = min(date(year, 12, 31), to_date)

            if year_start > to_date:
                break

            label = f"{_('Year')} {year}"
            buckets.append((label, year_start, year_end))
            year += 1

        return buckets

    def _generate_time_buckets(self, period_type: str, from_date: str, to_date: str) -> list[str, date, date]:
        """Generate time buckets based on period type.

        Returns list of tuples (bucket_label, bucket_start, bucket_end) where dates are clipped to [from_date, to_date].
        """

        if period_type == ExtendedReportPeriodType.WEEK.value:
            return self._generate_time_buckets_for_week(from_date, to_date)

        elif period_type == ExtendedReportPeriodType.MONTH.value:
            return self._generate_time_buckets_for_month(from_date, to_date)

        elif period_type == ExtendedReportPeriodType.QUARTER.value:
            return self._generate_time_buckets_for_quarter(from_date, to_date)

        return self._generate_time_buckets_for_year(from_date, to_date)

    def _get_bucket_value(self, branch_id, block_id, dept_id, bucket_start, bucket_end, value_field):
        """Get value for a specific bucket using target date fallback logic.

        1. Try target_date = bucket_end
        2. Fallback to latest record within bucket
        3. Return 0 if no data
        """
        base_qs = EmployeeStatusBreakdownReport.objects.filter(
            branch_id=branch_id,
            block_id=block_id,
            department_id=dept_id,
        )

        report = base_qs.filter(report_date=bucket_end).first()

        if not report:
            report = base_qs.filter(report_date__range=[bucket_start, bucket_end]).order_by("-report_date").first()

        if not report:
            return 0
        return getattr(report, value_field, 0)

    def _build_breakdown_nested_structure(self, buckets, value_field, org_filters):  # noqa: C901
        """Build nested organizational structure with time-series data."""
        branches_qs = Branch.objects.filter(is_active=True)
        if org_filters.get("branch_id"):
            branches_qs = branches_qs.filter(id=org_filters["branch_id"])

        data = []
        for branch in branches_qs:
            blocks_qs = Block.objects.filter(branch=branch, is_active=True)
            if org_filters.get("block_id"):
                blocks_qs = blocks_qs.filter(id=org_filters["block_id"])

            branch_stats = [0] * len(buckets)
            block_children = []
            for block in blocks_qs:
                depts_qs = Department.objects.filter(block=block, is_active=True)
                if org_filters.get("department_id"):
                    depts_qs = depts_qs.filter(id=org_filters["department_id"])

                block_stats = [0] * len(buckets)
                dept_children = []
                for dept in depts_qs:
                    dept_stats = []
                    for __, bucket_start, bucket_end in buckets:
                        value = self._get_bucket_value(
                            branch.id, block.id, dept.id, bucket_start, bucket_end, value_field
                        )
                        dept_stats.append(value)
                    dept_children.append({"type": "department", "name": dept.name, "statistics": dept_stats})
                    for i, val in enumerate(dept_stats):
                        block_stats[i] += val

                if dept_children:
                    block_children.append(
                        {"type": "block", "name": block.name, "statistics": block_stats, "children": dept_children}
                    )
                    for i, val in enumerate(block_stats):
                        branch_stats[i] += val

            if block_children:
                data.append(
                    {"type": "branch", "name": branch.name, "statistics": branch_stats, "children": block_children}
                )

        return data

    def _prepare_report_data(self, request, value_field) -> dict:
        param_serializer = EmployeeCountBreakdownReportParamsSerializer(data=request.query_params)
        param_serializer.is_valid(raise_exception=True)
        params = param_serializer.validated_data

        period_type = params["period_type"]
        from_date = params["from_date"]
        to_date = params["to_date"]

        buckets = self._generate_time_buckets(period_type, from_date, to_date)
        org_filters = {}
        if params.get("branch"):
            org_filters["branch_id"] = params["branch"]
        if params.get("block"):
            org_filters["block_id"] = params["block"]
        if params.get("department"):
            org_filters["department_id"] = params["department"]

        data = self._build_breakdown_nested_structure(buckets, value_field, org_filters)

        count_buckets = len(buckets)
        time_headers = [label for label, __, __ in buckets]
        for branch_item in data:
            avg = round(sum(branch_item["statistics"]) / count_buckets, 2) if buckets else 0.0
            branch_item["statistics"].append(avg)

            for block_item in branch_item.get("children", []):
                avg = round(sum(block_item["statistics"]) / count_buckets, 2) if buckets else 0.0
                block_item["statistics"].append(avg)

                for dept_item in block_item.get("children", []):
                    avg = round(sum(dept_item["statistics"]) / count_buckets, 2) if buckets else 0.0
                    dept_item["statistics"].append(avg)

        time_headers.append(_("Average"))

        return {"time_headers": time_headers, "data": data}

    @extend_schema(
        operation_id="hrm_reports_employee_status_breakdown_retrieve",
        summary="Employee Status Breakdown Report",
        description=(
            "Aggregate employee headcount data (total_not_resigned) by time period and organizational hierarchy. "
            "Returns time-series data with branch > block > department nesting."
        ),
        parameters=[EmployeeCountBreakdownReportParamsSerializer],
        responses={200: EmployeeStatusBreakdownReportAggregatedSerializer},
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "time_headers": ["Week 43/2025", "Week 44/2025", "Week 45/2025", "Average"],
                        "data": [
                            {
                                "type": "branch",
                                "name": "Branch A",
                                "statistics": [120, 125, 127, 124.00],
                                "children": [
                                    {
                                        "type": "block",
                                        "name": "Block X",
                                        "statistics": [80, 82, 83, 81.67],
                                        "children": [
                                            {"type": "department", "name": "Dept 1", "statistics": [30, 31, 32, 31.00]}
                                        ],
                                    }
                                ],
                            }
                        ],
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Error",
                value={"success": False, "data": None, "error": {"from_date": ["This field is required."]}},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    @action(detail=False, methods=["get"], url_path="employee-status-breakdown")
    def employee_status_breakdown(self, request):
        """Aggregate employee headcount (total_not_resigned) by time period and organizational hierarchy."""
        data = self._prepare_report_data(request, "total_not_resigned")
        serializer = EmployeeStatusBreakdownReportAggregatedSerializer(data)
        return Response(serializer.data)

    @extend_schema(
        operation_id="hrm_reports_employee_resigned_breakdown_retrieve",
        summary="Employee Resigned Breakdown Report",
        description=(
            "Aggregate resigned employee count (count_resigned) by time period and organizational hierarchy. "
            "Returns time-series data with branch > block > department nesting."
        ),
        parameters=[EmployeeCountBreakdownReportParamsSerializer],
        responses={200: EmployeeStatusBreakdownReportAggregatedSerializer},
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "time_headers": ["Month 10/2025", "Month 11/2025", "Average"],
                        "data": [
                            {
                                "type": "branch",
                                "name": "Branch A",
                                "statistics": [5, 8, 6.50],
                                "children": [
                                    {
                                        "type": "block",
                                        "name": "Block X",
                                        "statistics": [3, 5, 4.00],
                                        "children": [
                                            {"type": "department", "name": "Dept 1", "statistics": [2, 3, 2.50]}
                                        ],
                                    }
                                ],
                            }
                        ],
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Error",
                value={"success": False, "data": None, "error": {"to_date": ["This field is required."]}},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    @action(detail=False, methods=["get"], url_path="employee-resigned-breakdown")
    def employee_resigned_breakdown(self, request):
        """Aggregate resigned employee count (count_resigned) by time period and organizational hierarchy."""
        data = self._prepare_report_data(request, "count_resigned")
        serializer = EmployeeStatusBreakdownReportAggregatedSerializer(data)
        return Response(serializer.data)
