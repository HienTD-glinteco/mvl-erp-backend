from collections import defaultdict
from datetime import date, timedelta

from django.conf import settings
from django.db.models import Prefetch, Sum
from django.utils.module_loading import import_string
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema, extend_schema_view
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.hrm.constants import ExtendedReportPeriodType
from apps.hrm.models import (
    Block,
    Branch,
    Department,
    EmployeeResignedReasonReport,
    EmployeeStatusBreakdownReport,
    EmployeeWorkHistory,
)
from apps.hrm.models.employee import Employee
from apps.hrm.utils import (
    get_current_month_range,
    get_current_week_range,
)
from libs.drf.base_viewset import BaseGenericViewSet
from libs.export_xlsx import ExportXLSXMixin

from ..filtersets.employee_seniority_filter import EmployeeSeniorityFilterSet
from ..filtersets.seniority_ordering_filter import SeniorityOrderingFilter
from ..serializers import (
    EmployeeCountBreakdownReportParamsSerializer,
    EmployeeResignedReasonSummarySerializer,
    EmployeeSenioritySerializer,
    EmployeeStatusBreakdownReportAggregatedSerializer,
)


class EmployeeReportsViewSet(BaseGenericViewSet):
    """
    ViewSet for employee reports with aggregated data.

    - employee_status_breakdown and employee_resigned_breakdown reports aggregate by week/month periods.
    - Other reports aggregate by organizational hierarchy or source type.
    - All endpoints return full aggregated datasets (no pagination).
    - All API responses use envelope format: {success, data, error}.
    """

    pagination_class = None

    module = "REPORT"
    submodule = _("Employee Reports")
    permission_prefix = "employee_reports"

    def _generate_time_buckets_for_week(self, from_date: date, to_date: date) -> list[tuple[str, date, date]]:
        buckets: list[tuple[str, date, date]] = []

        current = from_date - timedelta(days=from_date.weekday())
        while current <= to_date:
            week_start = max(current, from_date)
            week_end = min(current + timedelta(days=6), to_date)
            iso_year, iso_week, __ = week_start.isocalendar()
            label = f"{_('Week')} {iso_week}/{iso_year}"
            buckets.append((label, week_start, week_end))
            current += timedelta(days=7)

        return buckets

    def _generate_time_buckets_for_month(self, from_date: date, to_date: date) -> list[tuple[str, date, date]]:
        buckets: list[tuple[str, date, date]] = []

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

    def _generate_time_buckets_for_quarter(self, from_date: date, to_date: date) -> list[tuple[str, date, date]]:
        buckets: list[tuple[str, date, date]] = []

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

    def _generate_time_buckets_for_year(self, from_date: date, to_date: date) -> list[tuple[str, date, date]]:
        buckets: list[tuple[str, date, date]] = []

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

    def _generate_time_buckets(self, period_type: str, from_date: date, to_date: date) -> list[tuple[str, date, date]]:
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

    def _build_breakdown_nested_structure(self, buckets, value_field, org_filters):  # noqa: C901
        """Build nested organizational structure with time-series data.

        Optimized to fetch only necessary dates and build structure in a single pass.
        """
        if not buckets:
            return []

        # Collect all bucket end dates (target dates for lookup)
        bucket_dates = {bucket_end for __, __, bucket_end in buckets}

        # Add all dates within each bucket range for fallback
        for __, bucket_start, bucket_end in buckets:
            current = bucket_start
            while current <= bucket_end:
                bucket_dates.add(current)
                current += timedelta(days=1)

        # Single query to fetch only relevant report dates with related objects
        reports_qs = (
            EmployeeStatusBreakdownReport.objects.filter(
                report_date__in=bucket_dates, branch__is_active=True, block__is_active=True, department__is_active=True
            )
            .select_related("branch", "block", "department")
            .only("branch", "block", "department", value_field, "report_date")
            .order_by("report_date")
        )

        # Apply organizational filters
        if org_filters.get("branch_id"):
            reports_qs = reports_qs.filter(branch_id=org_filters["branch_id"])
        if org_filters.get("block_id"):
            reports_qs = reports_qs.filter(block_id=org_filters["block_id"])
        if org_filters.get("block_type"):
            reports_qs = reports_qs.filter(block__block_type=org_filters["block_type"])
        if org_filters.get("department_id"):
            reports_qs = reports_qs.filter(department_id=org_filters["department_id"])

        # Fetch all reports at once
        all_reports = list(reports_qs)

        # Build structures and value lookup in a single pass
        reports_by_org_date = {}  # {(branch_id, block_id, dept_id, date): report}
        org_hierarchy = defaultdict(lambda: defaultdict(set))
        branch_names = {}
        block_names = {}
        dept_names = {}

        for report in all_reports:
            key = (report.branch_id, report.block_id, report.department_id, report.report_date)
            reports_by_org_date[key] = report

            # Track names
            branch_names[report.branch_id] = report.branch.name
            block_names[report.block_id] = report.block.name
            dept_names[report.department_id] = report.department.name

            # Build hierarchy
            org_hierarchy[report.branch_id][report.block_id].add(report.department_id)

        # Helper to get value for a bucket
        def get_value(branch_id, block_id, dept_id, bucket_start, bucket_end):
            # Try exact match on bucket_end first
            key = (branch_id, block_id, dept_id, bucket_end)
            if key in reports_by_org_date:
                return getattr(reports_by_org_date[key], value_field, 0)

            # Fallback: find latest date within bucket range
            latest_date = None
            for report_date in bucket_dates:
                if bucket_start <= report_date <= bucket_end:
                    test_key = (branch_id, block_id, dept_id, report_date)
                    if test_key in reports_by_org_date:
                        if latest_date is None or report_date > latest_date:
                            latest_date = report_date

            if latest_date:
                key = (branch_id, block_id, dept_id, latest_date)
                return getattr(reports_by_org_date[key], value_field, 0)

            return 0

        # Build the nested structure
        data = []
        for branch_id in sorted(org_hierarchy.keys()):
            branch_stats = [0] * len(buckets)
            block_children = []

            for block_id in sorted(org_hierarchy[branch_id].keys()):
                block_stats = [0] * len(buckets)
                dept_children = []

                for dept_id in sorted(org_hierarchy[branch_id][block_id]):
                    dept_stats = []
                    for __, bucket_start, bucket_end in buckets:
                        value = get_value(branch_id, block_id, dept_id, bucket_start, bucket_end)
                        dept_stats.append(value)

                    dept_children.append({"type": "department", "name": dept_names[dept_id], "statistics": dept_stats})

                    # Aggregate to block level
                    for i, val in enumerate(dept_stats):
                        block_stats[i] += val

                if dept_children:
                    block_children.append(
                        {
                            "type": "block",
                            "name": block_names[block_id],
                            "statistics": block_stats,
                            "children": dept_children,
                        }
                    )

                    # Aggregate to branch level
                    for i, val in enumerate(block_stats):
                        branch_stats[i] += val

            if block_children:
                data.append(
                    {
                        "type": "branch",
                        "name": branch_names[branch_id],
                        "statistics": branch_stats,
                        "children": block_children,
                    }
                )

        return data

    def _get_from_date_to_date(self, params: dict) -> tuple[date, date]:
        period_type = params["period_type"]
        from_date = params.get("from_date")
        to_date = params.get("to_date")

        if not from_date or not to_date:
            if period_type == ExtendedReportPeriodType.WEEK.value:
                from_date, to_date = get_current_month_range()
            elif period_type == ExtendedReportPeriodType.MONTH.value:
                from_date, to_date = get_current_month_range()
            elif period_type == ExtendedReportPeriodType.QUARTER.value:
                from_date, to_date = get_current_month_range()
            else:
                from_date, to_date = get_current_week_range()
        return from_date, to_date

    def _prepare_report_data(self, request, value_field) -> dict:
        param_serializer = EmployeeCountBreakdownReportParamsSerializer(data=request.query_params)
        param_serializer.is_valid(raise_exception=True)
        params = param_serializer.validated_data

        period_type = params["period_type"]
        from_date, to_date = self._get_from_date_to_date(params)

        buckets = self._generate_time_buckets(period_type, from_date, to_date)

        org_filters = {}
        if params.get("branch"):
            org_filters["branch_id"] = params["branch"]
        if params.get("block"):
            org_filters["block_id"] = params["block"]
        if params.get("block_type"):
            org_filters["block_type"] = params["block_type"]
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
            "Returns time-series data with branch > block > department nesting. "
            "Supports filtering by branch, block, block_type, or department."
        ),
        tags=["5.5: Employee Reports"],
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
            "Returns time-series data with branch > block > department nesting. "
            "Supports filtering by branch, block, block_type, or department."
        ),
        tags=["5.5: Employee Reports"],
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

    @extend_schema(
        operation_id="hrm_reports_employee_resigned_reasons_summary_retrieve",
        summary="Employee Resignation Reason Rate Report (Pie Chart)",
        description=(
            "Returns aggregated resignation reason counts and percentages for a selected date range "
            "and organizational filter. Suitable for displaying a pie chart. "
            "Filters resignation data by time period (date range) and organizational units (Branch/Block/Department). "
            "Only resignation reasons with count > 0 are displayed. "
            "Default date range: 1st of current month to today."
        ),
        tags=["5.5: Employee Reports"],
        parameters=[
            OpenApiParameter(
                name="from_date",
                type=str,
                required=False,
                description="Start date (YYYY-MM-DD). Default: 1st of current month",
            ),
            OpenApiParameter(
                name="to_date", type=str, required=False, description="End date (YYYY-MM-DD). Default: today"
            ),
            OpenApiParameter(name="branch", type=int, required=False, description="Branch ID"),
            OpenApiParameter(name="block", type=int, required=False, description="Block ID"),
            OpenApiParameter(
                name="block_type", type=str, required=False, description="Block type: 'support' or 'business'"
            ),
            OpenApiParameter(name="department", type=int, required=False, description="Department ID"),
        ],
        responses={200: EmployeeResignedReasonSummarySerializer},
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "total_resigned": 127,
                        "from_date": "2025-01-01",
                        "to_date": "2025-06-30",
                        "filters": {"branch": "Branch A", "block": None, "department": None, "block_type": None},
                        "reasons": [
                            {
                                "code": "VOLUNTARY_CAREER_CHANGE",
                                "label": "Voluntary - Career Change",
                                "count": 45,
                                "percentage": "35.43",
                            },
                            {
                                "code": "VOLUNTARY_PERSONAL",
                                "label": "Voluntary - Personal Reasons",
                                "count": 32,
                                "percentage": "25.20",
                            },
                            {"code": "PROBATION_FAIL", "label": "Probation Fail", "count": 20, "percentage": "15.75"},
                            {
                                "code": "CONTRACT_EXPIRED",
                                "label": "Contract Expired",
                                "count": 15,
                                "percentage": "11.81",
                            },
                            {
                                "code": "VOLUNTARY_HEALTH",
                                "label": "Voluntary - Health Reasons",
                                "count": 10,
                                "percentage": "7.87",
                            },
                            {"code": "OTHER", "label": "Other", "count": 5, "percentage": "3.94"},
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
    @action(detail=False, methods=["get"], url_path="employee-resigned-reasons-summary")
    def employee_resigned_reasons_summary(self, request):
        """
        Aggregate resigned reasons by date range and organizational filters.
        Returns flat list of reasons with counts and percentages.
        Default date range: 1st of current month to today (or end of month if today is past end of month).
        """
        # Mapping: column name -> (code, label)
        reason_fields = [
            ("agreement_termination", Employee.ResignationReason.AGREEMENT_TERMINATION, _("Agreement Termination")),
            ("probation_fail", Employee.ResignationReason.PROBATION_FAIL, _("Probation Fail")),
            ("job_abandonment", Employee.ResignationReason.JOB_ABANDONMENT, _("Job Abandonment")),
            (
                "disciplinary_termination",
                Employee.ResignationReason.DISCIPLINARY_TERMINATION,
                _("Disciplinary Termination"),
            ),
            ("workforce_reduction", Employee.ResignationReason.WORKFORCE_REDUCTION, _("Workforce Reduction")),
            ("underperforming", Employee.ResignationReason.UNDERPERFORMING, _("Underperforming")),
            ("contract_expired", Employee.ResignationReason.CONTRACT_EXPIRED, _("Contract Expired")),
            ("voluntary_health", Employee.ResignationReason.VOLUNTARY_HEALTH, _("Voluntary - Health Reasons")),
            ("voluntary_personal", Employee.ResignationReason.VOLUNTARY_PERSONAL, _("Voluntary - Personal Reasons")),
            (
                "voluntary_career_change",
                Employee.ResignationReason.VOLUNTARY_CAREER_CHANGE,
                _("Voluntary - Career Change"),
            ),
            ("voluntary_other", Employee.ResignationReason.VOLUNTARY_OTHER, _("Voluntary - Other")),
            ("other", Employee.ResignationReason.OTHER, _("Other")),
        ]

        # Get or set default date range: 1st of current month to today
        from_date = request.query_params.get("from_date")
        to_date = request.query_params.get("to_date")

        if not from_date or not to_date:
            # Default: 1st of current month to today
            today = date.today()
            from_date = date(today.year, today.month, 1).isoformat()
            to_date = today.isoformat()

        # Build base queryset
        qs = EmployeeResignedReasonReport.objects.filter(
            report_date__range=[from_date, to_date],
            branch__is_active=True,
            block__is_active=True,
            department__is_active=True,
        )

        # Apply organizational filters
        filter_info = {}

        branch_id = request.query_params.get("branch")
        if branch_id:
            qs = qs.filter(branch_id=branch_id)
            branch_obj = Branch.objects.filter(id=branch_id).first()
            filter_info["branch"] = branch_obj.name if branch_obj else None
        else:
            filter_info["branch"] = None

        block_id = request.query_params.get("block")
        if block_id:
            qs = qs.filter(block_id=block_id)
            block_obj = Block.objects.filter(id=block_id).first()
            filter_info["block"] = block_obj.name if block_obj else None
        else:
            filter_info["block"] = None

        block_type = request.query_params.get("block_type")
        if block_type:
            qs = qs.filter(block__block_type=block_type)
            filter_info["block_type"] = block_type
        else:
            filter_info["block_type"] = None

        department_id = request.query_params.get("department")
        if department_id:
            qs = qs.filter(department_id=department_id)
            dept_obj = Department.objects.filter(id=department_id).first()
            filter_info["department"] = dept_obj.name if dept_obj else None
        else:
            filter_info["department"] = None

        # Aggregate all reason columns
        agg_fields = {"total_resigned": Sum("count_resigned")}
        for field_name, __, __ in reason_fields:
            agg_fields[field_name] = Sum(field_name)

        aggregates = qs.aggregate(**agg_fields)

        total_resigned = aggregates.get("total_resigned") or 0

        # Build reasons list (only include reasons with count > 0)
        reasons = []
        for field_name, code, label in reason_fields:
            count = aggregates.get(field_name) or 0
            if count > 0:
                percentage = round((count / total_resigned * 100), 2) if total_resigned > 0 else 0.0
                reasons.append({"code": code, "label": str(label), "count": count, "percentage": percentage})

        # Sort by count descending
        reasons.sort(key=lambda x: x["count"], reverse=True)

        # Build response
        data = {
            "total_resigned": total_resigned,
            "from_date": from_date,
            "to_date": to_date,
            "filters": filter_info,
            "reasons": reasons,
        }

        serializer = EmployeeResignedReasonSummarySerializer(data)
        return Response(serializer.data)


@extend_schema_view(
    export=extend_schema(
        tags=["5.5: Employee Reports"],
    ),
)
class EmployeeSeniorityReportViewSet(ExportXLSXMixin, BaseGenericViewSet):
    """ViewSet for employee seniority report.

    - Supports `list` (with filtering, ordering and pagination) and `/export/` via `ExportXLSXMixin`.
    - Reuses the existing `EmployeeSeniorityFilterSet`, `SeniorityOrderingFilter` and serializer.
    """

    module = _("REPORT")
    submodule = _("Employee Seniority Report")
    permission_prefix = "employee_seniority_report"
    STANDARD_ACTIONS = {
        "list": {
            "name_template": _("Employee Seniority Report"),
            "description_template": _("Retrieve employee seniority report with filtering and sorting"),
        },
        "export": {
            "name_template": _("Export Employee Seniority Report"),
            "description_template": _("Export employee seniority report to XLSX format"),
        },
    }
    queryset = Employee.objects.none()

    # Provide filterset and serializer for ExportXLSXMixin to work with
    filterset_class = EmployeeSeniorityFilterSet
    serializer_class = EmployeeSenioritySerializer

    @extend_schema(
        operation_id="hrm_reports_employee_seniority_report_list",
        summary="Employee Seniority Report",
        description=(
            "Retrieve employee seniority report with filtering and sorting. "
            "Calculates seniority based on work history with retain_seniority logic. "
            "Only includes employees with status Active, Maternity Leave, or Unpaid Leave. "
            "Excludes employees with code starting with 'OS'."
        ),
        tags=["5.5: Employee Reports"],
        parameters=[
            OpenApiParameter(
                name="page", type=int, required=False, description="A page number within the paginated result set."
            ),
            OpenApiParameter(
                name="page_size", type=int, required=False, description="Number of results to return per page."
            ),
            OpenApiParameter(name="branch_id", type=int, required=False, description="Filter by branch ID"),
            OpenApiParameter(name="block_id", type=int, required=False, description="Filter by block ID"),
            OpenApiParameter(name="department_id", type=int, required=False, description="Filter by department ID"),
            OpenApiParameter(
                name="function_block",
                type=str,
                required=False,
                description="Filter by function block type (support/business)",
            ),
            OpenApiParameter(
                name="ordering",
                type=str,
                required=False,
                description="Sort field: seniority_days, -seniority_days, code, fullname",
                examples=[
                    OpenApiExample(
                        "Sort by seniority descending",
                        value="-seniority_days",
                    ),
                    OpenApiExample(
                        "Sort by employee code",
                        value="code",
                    ),
                ],
            ),
        ],
        responses={200: EmployeeSenioritySerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        # Build base queryset with business rules BR-1
        queryset = Employee.objects.filter(
            status__in=[
                Employee.Status.ACTIVE,
                Employee.Status.MATERNITY_LEAVE,
                Employee.Status.UNPAID_LEAVE,
            ]
        ).exclude(code_type="OS")

        # Apply filters (validate explicitly to keep previous behavior)
        filterset = EmployeeSeniorityFilterSet(request.GET, queryset=queryset)
        if not filterset.is_valid():
            return Response(filterset.errors, status=400)

        queryset = filterset.qs

        # Optimize query with prefetch of work histories
        work_history_prefetch = Prefetch(
            "work_histories",
            queryset=EmployeeWorkHistory.objects.select_related(
                "branch", "block", "department", "position", "employee"
            ).order_by("from_date"),
            to_attr="cached_work_histories",
        )

        queryset = queryset.select_related("branch", "block", "department").prefetch_related(work_history_prefetch)

        # Apply ordering
        ordering_filter = SeniorityOrderingFilter()
        queryset = ordering_filter.filter_queryset(request, queryset, self)

        # Apply pagination using REST framework settings
        pagination_class = settings.REST_FRAMEWORK.get("DEFAULT_PAGINATION_CLASS")
        if pagination_class:
            paginator = import_string(pagination_class)()
            page = paginator.paginate_queryset(queryset, request)

            if page is not None:
                serializer = EmployeeSenioritySerializer(page, many=True)
                return paginator.get_paginated_response(serializer.data)

        serializer = EmployeeSenioritySerializer(queryset, many=True)
        return Response(serializer.data)
