from collections import defaultdict
from decimal import Decimal

from django.db.models import Sum
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.hrm.constants import RecruitmentSourceType, ReportPeriodType
from apps.hrm.models import (
    HiredCandidateReport,
    RecruitmentChannelReport,
    RecruitmentCostReport,
    RecruitmentExpense,
    RecruitmentSourceReport,
    StaffGrowthReport,
)
from apps.hrm.utils import get_current_month_range, get_current_week_range

from ..serializers.recruitment_reports import (
    HiredCandidateReportAggregatedSerializer,
    HiredCandidateReportParametersSerializer,
    RecruitmentChannelReportAggregatedSerializer,
    RecruitmentChannelReportParametersSerializer,
    RecruitmentCostReportAggregatedSerializer,
    RecruitmentCostReportParametersSerializer,
    RecruitmentSourceReportAggregatedSerializer,
    RecruitmentSourceReportParametersSerializer,
    ReferralCostReportAggregatedSerializer,
    ReferralCostReportParametersSerializer,
    StaffGrowthReportAggregatedSerializer,
    StaffGrowthReportParametersSerializer,
)


class RecruitmentReportsViewSet(viewsets.GenericViewSet):
    """
    ViewSet for recruitment reports with aggregated data.

    - staff_growth and hired_candidate reports aggregate by week/month periods.
    - Other reports aggregate by organizational hierarchy or source type.
    - All endpoints return full aggregated datasets (no pagination).
    - All API responses use envelope format: {success, data, error}.
    """

    pagination_class = None

    @extend_schema(
        summary="Staff Growth Report",
        description=(
            "Aggregate staff changes (introductions, returns, new hires, transfers, resignations) "
            "by period (week/month)."
        ),
        parameters=[StaffGrowthReportParametersSerializer],
        responses={200: StaffGrowthReportAggregatedSerializer(many=True)},
        examples=[
            OpenApiExample(
                "Success - Monthly Report",
                value={
                    "success": True,
                    "data": [
                        {
                            "period_type": "month",
                            "label": "Month 10/2025",
                            "num_introductions": 5,
                            "num_returns": 2,
                            "num_recruitment_source": 10,
                            "num_transfers": 3,
                            "num_resignations": 1,
                        }
                    ],
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Error - Invalid Date Range",
                value={"success": False, "data": None, "error": {"from_date": ["Invalid date format"]}},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    @action(detail=False, methods=["get"], url_path="staff-growth")
    def staff_growth(self, request):
        """
        Aggregate staff growth data by week or month period.
        Returns a list of period objects with staff change statistics for each period.
        """
        queryset, __, __, __, period_type = self._prepare_report_queryset(
            request,
            StaffGrowthReportParametersSerializer,
            StaffGrowthReport,
            period_param="period_type",
        )

        # Group by period (week or month)
        if period_type == ReportPeriodType.WEEK.value:
            period_field = "week_key"
        else:
            period_field = "month_key"

        aggregated = (
            queryset.values(period_field)
            .order_by(period_field)
            .annotate(
                num_introductions=Sum("num_introductions"),
                num_returns=Sum("num_returns"),
                num_recruitment_source=Sum("num_recruitment_source"),
                num_transfers=Sum("num_transfers"),
                num_resignations=Sum("num_resignations"),
            )
        )

        # Build period label for each period
        results = []
        for item in aggregated:
            if period_type == ReportPeriodType.WEEK.value:
                label = item[period_field]
            else:
                # month_key is MM/YYYY, label as 'Month MM/YYYY'
                label = f"{_('Month')} {item[period_field]}"
            results.append(
                {
                    "period_type": period_type,
                    "label": label,
                    "num_introductions": item["num_introductions"] or 0,
                    "num_returns": item["num_returns"] or 0,
                    "num_recruitment_source": item["num_recruitment_source"] or 0,
                    "num_transfers": item["num_transfers"] or 0,
                    "num_resignations": item["num_resignations"] or 0,
                }
            )

        serializer = StaffGrowthReportAggregatedSerializer(results, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Recruitment Source Report",
        description=(
            "Aggregate hire statistics by recruitment source in nested organizational format (no period aggregation)."
        ),
        parameters=[RecruitmentSourceReportParametersSerializer],
        responses={200: RecruitmentSourceReportAggregatedSerializer},
        examples=[
            OpenApiExample(
                "Success - Nested Organization Report",
                value={
                    "success": True,
                    "data": {
                        "sources": ["LinkedIn", "Job Fair", "Employee Referral"],
                        "data": [
                            {
                                "type": "branch",
                                "name": "Hanoi Branch",
                                "statistics": [15, 8, 12],
                                "children": [
                                    {
                                        "type": "block",
                                        "name": "Business Block",
                                        "statistics": [10, 5, 8],
                                        "children": [
                                            {
                                                "type": "department",
                                                "name": "Sales Department",
                                                "statistics": [5, 3, 4],
                                            }
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
                "Error - Invalid Filter",
                value={"success": False, "data": None, "error": {"branch": ["Invalid branch ID"]}},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    @action(detail=False, methods=["get"], url_path="recruitment-source")
    def recruitment_source(self, request):
        """
        Aggregate recruitment source data in nested format (branch > block > department).
        Returns a nested list of branches, each with blocks and departments, and hire statistics by source.
        """
        queryset, __, __, __, __ = self._prepare_report_queryset(
            request,
            RecruitmentSourceReportParametersSerializer,
            RecruitmentSourceReport,
        )
        queryset = queryset.select_related("recruitment_source", "branch", "block", "department")

        sources = list(
            queryset.values_list("recruitment_source__name", flat=True).distinct().order_by("recruitment_source__name")
        )

        data = self._build_nested_structure(queryset, sources, "recruitment_source__name", "num_hires")

        result = {
            "sources": sources,
            "data": data,
        }

        serializer = RecruitmentSourceReportAggregatedSerializer(result)
        return Response(serializer.data)

    @extend_schema(
        summary="Recruitment Channel Report",
        description=(
            "Aggregate hire statistics by recruitment channel in nested organizational format (no period aggregation)."
        ),
        parameters=[RecruitmentChannelReportParametersSerializer],
        responses={200: RecruitmentChannelReportAggregatedSerializer},
        examples=[
            OpenApiExample(
                "Success - Channel Report",
                value={
                    "success": True,
                    "data": {
                        "channels": ["Facebook", "LinkedIn", "Job Website"],
                        "data": [
                            {
                                "type": "branch",
                                "name": "Hanoi Branch",
                                "statistics": [20, 15, 25],
                                "children": [
                                    {
                                        "type": "block",
                                        "name": "Business Block",
                                        "statistics": [12, 10, 18],
                                        "children": [
                                            {
                                                "type": "department",
                                                "name": "Marketing Department",
                                                "statistics": [8, 5, 10],
                                            }
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
                "Error - Invalid Date",
                value={"success": False, "data": None, "error": {"from_date": ["Date must be in YYYY-MM-DD format"]}},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    @action(detail=False, methods=["get"], url_path="recruitment-channel")
    def recruitment_channel(self, request):
        """
        Aggregate recruitment channel data in nested format (branch > block > department).
        Returns a nested list of branches, each with blocks and departments, and hire statistics by channel.
        """
        queryset, __, __, __, __ = self._prepare_report_queryset(
            request,
            RecruitmentChannelReportParametersSerializer,
            RecruitmentChannelReport,
        )
        queryset = queryset.select_related("recruitment_channel", "branch", "block", "department")

        channels = list(
            queryset.values_list("recruitment_channel__name", flat=True)
            .distinct()
            .order_by("recruitment_channel__name")
        )

        data = self._build_nested_structure(queryset, channels, "recruitment_channel__name", "num_hires")

        result = {
            "channels": channels,
            "data": data,
        }

        serializer = RecruitmentChannelReportAggregatedSerializer(result)
        return Response(serializer.data)

    @extend_schema(
        summary="Recruitment Cost Report",
        description="Aggregate recruitment cost data by source type and months (no period aggregation).",
        parameters=[RecruitmentCostReportParametersSerializer],
        responses={200: RecruitmentCostReportAggregatedSerializer},
        examples=[
            OpenApiExample(
                "Success - Cost Report",
                value={
                    "success": True,
                    "data": {
                        "months": ["10/2025", "11/2025", "Total"],
                        "data": [
                            {
                                "source_type": "referral_source",
                                "months": [
                                    {"total": 5000000.0, "count": 10, "avg": 500000.0},
                                    {"total": 6000000.0, "count": 12, "avg": 500000.0},
                                    {"total": 11000000.0, "count": 22, "avg": 500000.0},
                                ],
                            },
                            {
                                "source_type": "marketing_channel",
                                "months": [
                                    {"total": 8000000.0, "count": 15, "avg": 533333.33},
                                    {"total": 7500000.0, "count": 14, "avg": 535714.29},
                                    {"total": 15500000.0, "count": 29, "avg": 534482.76},
                                ],
                            },
                        ],
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Error - Invalid Parameters",
                value={"success": False, "data": None, "error": {"department": ["Invalid department ID"]}},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    @action(detail=False, methods=["get"], url_path="recruitment-cost")
    def recruitment_cost(self, request):
        """
        Aggregate recruitment cost data by source type and months.
        Returns a list of source types, each with monthly and total cost, count, and average.
        """
        queryset, __, __, __, __ = self._prepare_report_queryset(
            request,
            RecruitmentCostReportParametersSerializer,
            RecruitmentCostReport,
        )

        month_stats = list(
            queryset.values("month_key", "source_type")
            .annotate(
                total=Sum("total_cost"),
                count=Sum("num_hires"),
            )
            .order_by("month_key", "source_type")
        )

        months_set, months_list = self._get_months_and_labels_from_stats(month_stats)
        source_types = sorted({item["source_type"] for item in month_stats})

        data = []
        for source_type in source_types:
            source_months = []
            total_total = Decimal("0")
            total_count = 0
            for month in months_set:
                month_data = next(
                    (
                        item
                        for item in month_stats
                        if item["month_key"] == month and item["source_type"] == source_type
                    ),
                    None,
                )
                if month_data:
                    total = month_data["total"] or Decimal("0")
                    count = month_data["count"] or 0
                    total_total += total
                    total_count += count
                else:
                    total = Decimal("0")
                    count = 0
                avg = (total / count) if count > 0 else Decimal("0")
                source_months.append({"total": total, "count": count, "avg": avg})
            total_avg = (total_total / total_count) if total_count > 0 else Decimal("0")
            source_months.append({"total": total_total, "count": total_count, "avg": total_avg})
            data.append({"source_type": source_type, "months": source_months})

        result = {"months": months_list, "data": data}
        serializer = RecruitmentCostReportAggregatedSerializer(result)
        return Response(serializer.data)

    @extend_schema(
        summary="Hired Candidate Report",
        description=(
            "Aggregate hired candidate statistics by source type with period aggregation "
            "(week/month) and conditional employee details."
        ),
        parameters=[HiredCandidateReportParametersSerializer],
        responses={200: HiredCandidateReportAggregatedSerializer},
        examples=[
            OpenApiExample(
                "Success - Hired Candidate Report",
                value={
                    "success": True,
                    "data": {
                        "period_type": "month",
                        "headers": ["10/2025", "11/2025", "Total"],
                        "data": [
                            {
                                "type": "source_type",
                                "name": "Referral Source",
                                "statistics": [10, 12, 22],
                                "children": [
                                    {
                                        "type": "employee",
                                        "name": "Nguyen Van A",
                                        "statistics": [5, 6, 11],
                                    },
                                    {
                                        "type": "employee",
                                        "name": "Tran Thi B",
                                        "statistics": [5, 6, 11],
                                    },
                                ],
                            },
                            {
                                "type": "source_type",
                                "name": "Marketing Channel",
                                "statistics": [15, 18, 33],
                                "children": None,
                            },
                        ],
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Success - Hired Candidate Report",
                value={
                    "success": True,
                    "data": {
                        "period_type": "week",
                        "headers": ["Tuần 1 - 10/2025", "Tuần 2 - 10/2025", "Total"],
                        "data": [
                            {
                                "type": "source_type",
                                "name": "Referral Source",
                                "statistics": [10, 12, 22],
                                "children": [
                                    {
                                        "type": "employee",
                                        "name": "Nguyen Van A",
                                        "statistics": [5, 6, 11],
                                    },
                                    {
                                        "type": "employee",
                                        "name": "Tran Thi B",
                                        "statistics": [5, 6, 11],
                                    },
                                ],
                            },
                            {
                                "type": "source_type",
                                "name": "Marketing Channel",
                                "statistics": [15, 18, 33],
                                "children": None,
                            },
                        ],
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Error - Invalid Period Type",
                value={"success": False, "data": None, "error": {"period_type": ["Invalid choice"]}},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    @action(detail=False, methods=["get"], url_path="hired-candidate")
    def hired_candidate(self, request):
        """Aggregate hired candidate data by source type with period-based statistics.

        Includes conditional employee details for referral_source.
        Returns a list of source types with statistics per period (week/month) and,
        for referral_source, a breakdown by employee.
        """
        queryset, __, start_date, end_date, period_type = self._prepare_report_queryset(
            request,
            HiredCandidateReportParametersSerializer,
            HiredCandidateReport,
            period_param="period_type",
        )

        # Aggregate by week or month based on period_type
        if period_type == ReportPeriodType.WEEK.value:
            # Week aggregation using database week_key field
            raw_stats = list(
                queryset.values("week_key", "source_type", "employee__code", "employee__fullname")
                .annotate(total_hired=Sum("num_candidates_hired"))
                .order_by("source_type", "employee__fullname", "week_key")
            )
            # Rename week_key to key for consistency
            for item in raw_stats:
                item["key"] = item.pop("week_key")
        else:
            # Month aggregation (existing logic)
            raw_stats = list(
                queryset.values("month_key", "source_type", "employee__code", "employee__fullname")
                .annotate(total_hired=Sum("num_candidates_hired"))
                .order_by("source_type", "employee__fullname", "month_key")
            )
            # Rename month_key to key for consistency
            for item in raw_stats:
                item["key"] = item.pop("month_key")

        periods, period_labels = self._get_periods_and_labels(period_type, start_date, end_date, raw_stats)
        stats, emp_stats, emp_code_to_name = self._aggregate_hired_candidate_stats(raw_stats)
        data = self._format_hired_candidate_result(periods, stats, emp_stats, emp_code_to_name)

        result = {
            "period_type": period_type,
            "labels": period_labels,
            "data": data,
        }

        serializer = HiredCandidateReportAggregatedSerializer(result)
        return Response(serializer.data)

    @extend_schema(
        summary="Referral Cost Report",
        description=(
            "Referral cost report with department summary and employee details (always restricted to single month)."
        ),
        parameters=[ReferralCostReportParametersSerializer],
        responses={200: ReferralCostReportAggregatedSerializer},
        examples=[
            OpenApiExample(
                "Success - Referral Cost Report",
                value={
                    "success": True,
                    "data": {
                        "data": [
                            {
                                "name": "IT Department",
                                "items": [
                                    {
                                        "id": 1,
                                        "expense_date": "2025-10-15",
                                        "amount": 500000.0,
                                        "recruitment_source": {"id": 1, "name": "Employee Referral"},
                                        "employee": {
                                            "id": 1,
                                            "fullname": "Nguyen Van A",
                                            "code": "NV001",
                                        },
                                        "referee": {
                                            "id": 2,
                                            "fullname": "Tran Thi B",
                                            "code": "NV002",
                                        },
                                        "referrer": {
                                            "id": 1,
                                            "fullname": "Nguyen Van A",
                                            "code": "NV001",
                                        },
                                    }
                                ],
                            }
                        ],
                        "summary_total": 500000.0,
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Error - Invalid Month Format",
                value={
                    "success": False,
                    "data": None,
                    "error": {"month": ["Invalid month format. Use MM/YYYY."]},
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    @action(detail=False, methods=["get"], url_path="referral-cost")
    def referral_cost(self, request):
        """
        Generate referral cost report from RecruitmentExpense for a single month, with branch/block/department filters.
        Returns a list of departments, each with referral expenses and employees, and a total summary.
        """
        queryset, __, __, __, __ = self._prepare_report_queryset(
            request,
            ReferralCostReportParametersSerializer,
            RecruitmentExpense,
            period_param="month",  # Referral cost uses 'month' param
            date_field="date",
            org_field_prefix="referee",
        )
        queryset = queryset.filter(recruitment_source__allow_referral=True)
        queryset = queryset.select_related("referee__department__block__branch", "referrer", "recruitment_source")

        departments = {}
        summary_total = Decimal("0")

        for expense in queryset:
            dept_name = _("No Department")
            if expense.referee and expense.referee.department:
                department = expense.referee.department
                block = department.block
                branch = block.branch
                dept_name = f"{branch.name} - {block.name} - {department.name}"

            if dept_name not in departments:
                departments[dept_name] = {
                    "name": dept_name,
                    "items": [],
                }

            departments[dept_name]["items"].append(expense)
            summary_total += expense.total_cost

        result = {
            "data": list(departments.values()),
            "summary_total": summary_total,
        }

        serializer = ReferralCostReportAggregatedSerializer(result)
        return Response(serializer.data)

    def _get_months_and_labels_from_stats(self, month_stats):
        months_set = sorted({item["month_key"] for item in month_stats if item["month_key"]})
        months_list = months_set + [_("Total")]
        return months_set, months_list

    def _get_periods_and_labels(self, period_type, start_date, end_date, raw_stats):
        periods_set = set()
        for item in raw_stats:
            if item["key"]:
                periods_set.add(item["key"])

        if period_type == ReportPeriodType.MONTH.value:
            periods = []
            cur = start_date.replace(day=1)
            while cur <= end_date:
                periods.append(f"{cur.month:02d}/{cur.year}")
                if cur.month == 12:
                    cur = cur.replace(year=cur.year + 1, month=1)
                else:
                    cur = cur.replace(month=cur.month + 1)
        else:
            # For week period, translate week keys from English to current language
            periods = []
            for key in sorted(periods_set):
                # Replace "Week" with translated version
                if key.startswith("Week "):
                    translated_key = key.replace("Week ", f"{_('Week')} ", 1)
                    periods.append(translated_key)
                else:
                    periods.append(key)

        period_labels = periods + [_("Total")]
        return periods, period_labels

    def _aggregate_hired_candidate_stats(self, raw_stats):
        stats = defaultdict(lambda: defaultdict(int))
        emp_stats = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
        emp_code_to_name = {}
        for item in raw_stats:
            source_type = item["source_type"]
            key = item["key"]
            total_hired = item["total_hired"] or 0
            employee_code = item.get("employee__code")
            employee_fullname = item.get("employee__fullname")
            stats[source_type][key] += total_hired
            if source_type == RecruitmentSourceType.REFERRAL_SOURCE.value and employee_code:
                emp_stats[employee_code][source_type][key] += total_hired
                emp_code_to_name[employee_code] = employee_fullname
        return stats, emp_stats, emp_code_to_name

    def _format_hired_candidate_result(self, periods, stats, emp_stats, emp_code_to_name):
        data = []
        for source_type_value in RecruitmentSourceType.values:
            source_type_label = RecruitmentSourceType.get_label(source_type_value)
            statistics = []
            total_hired_sum = 0
            for period in periods:
                hired = stats[source_type_value][period] if period in stats[source_type_value] else 0
                statistics.append(hired)
                total_hired_sum += hired
            statistics.append(total_hired_sum)

            children = []
            if source_type_value == RecruitmentSourceType.REFERRAL_SOURCE.value:
                sorted_emps = sorted(emp_stats.items(), key=lambda x: emp_code_to_name.get(x[0], ""))
                for emp_code, emp_source_dict in sorted_emps:
                    if source_type_value not in emp_source_dict:
                        continue
                    emp_statistics = []
                    emp_total_hired = 0
                    for period in periods:
                        hired = (
                            emp_source_dict[source_type_value][period]
                            if period in emp_source_dict[source_type_value]
                            else 0
                        )
                        emp_statistics.append(hired)
                        emp_total_hired += hired
                    emp_statistics.append(emp_total_hired)
                    children.append(
                        {
                            "type": "employee",
                            "name": emp_code_to_name.get(emp_code, ""),
                            "statistics": emp_statistics,
                        }
                    )

            data.append(
                {
                    "type": "source_type",
                    "name": source_type_label,
                    "statistics": statistics,
                    "children": children,
                }
            )
        return data

    def _prepare_report_queryset(
        self,
        request,
        param_serializer_class,
        model_class,
        period_param="period",
        date_field="report_date",
        org_field_prefix=None,
    ):
        """
        Common logic for report actions:
        - Validate query params
        - Determine date range (from_date/to_date or default by period)
        - Build base queryset
        - Apply org filters (branch, block, department)
        Returns: (queryset, params, start_date, end_date, period_type)
        """
        param_serializer = param_serializer_class(data=request.query_params)
        param_serializer.is_valid(raise_exception=True)
        params = param_serializer.validated_data

        period_type = params.get(period_param, ReportPeriodType.MONTH.value)
        from_date = params.get("from_date")
        to_date = params.get("to_date")

        if from_date and to_date:
            start_date, end_date = from_date, to_date
        else:
            if period_type == ReportPeriodType.MONTH.value:
                start_date, end_date = get_current_month_range()
            else:
                start_date, end_date = get_current_week_range()

        queryset = model_class.objects.filter(**{f"{date_field}__range": [start_date, end_date]})

        # Apply organizational filters
        org_filters = {}
        for field in ["branch", "block", "department"]:
            if not params.get(field):
                continue

            if org_field_prefix:
                org_filters[f"{org_field_prefix}__{field}_id"] = params[field]
            else:
                org_filters[f"{field}_id"] = params[field]

        if org_filters:
            queryset = queryset.filter(**org_filters)

        return queryset, params, start_date, end_date, period_type

    def _generate_period_label(self, period_type, start_date, end_date):
        """
        Generate period label based on period type.
        Returns 'Month MM/YYYY' for month, or '(DD/MM - DD/MM)' for week.
        """
        if period_type == ReportPeriodType.MONTH.value:
            return f"{_('Month')} {start_date.strftime('%m/%Y')}"
        else:
            return f"({start_date.strftime('%d/%m')} - {end_date.strftime('%d/%m')})"

    def _build_nested_structure(self, queryset, sources_list, source_field, value_field):
        """
        Efficiently build nested organizational structure for source/channel reports.
        Reduces DB queries by aggregating all data in a single query and building the tree in Python.
        Returns a nested list of branches, each with blocks and departments, and statistics by source/channel.
        """
        rows = list(
            queryset.values(
                "branch", "branch__name", "block", "block__name", "department", "department__name", source_field
            ).annotate(total=Sum(value_field))
        )

        stats = {}
        branches = {}
        blocks = {}
        departments = {}

        for row in rows:
            branch_id = row["branch"]
            block_id = row["block"]
            dept_id = row["department"]
            source = row[source_field]
            total = row["total"] or 0

            stats[(branch_id, block_id, dept_id, source)] = total

            if branch_id is not None:
                branches[branch_id] = row["branch__name"]
            if block_id is not None:
                blocks[(branch_id, block_id)] = row["block__name"]
            if dept_id is not None:
                departments[(branch_id, block_id, dept_id)] = row["department__name"]

        data = []
        for branch_id, branch_name in branches.items():
            block_ids = {k[1]: v for k, v in blocks.items() if k[0] == branch_id}
            branch_children = []
            branch_stats = [0 for _ in sources_list]
            for block_id, block_name in block_ids.items():
                block_node, block_stats = self._build_block_node(
                    branch_id, block_id, block_name, departments, stats, sources_list
                )
                branch_children.append(block_node)
                for i, val in enumerate(block_stats):
                    branch_stats[i] += val
            if not branch_children:
                branch_stats = [stats.get((branch_id, None, None, source), 0) for source in sources_list]
            branch_node = {
                "type": "branch",
                "name": branch_name,
                "statistics": branch_stats,
                "children": branch_children,
            }
            data.append(branch_node)
        return data

    def _build_department_node(self, branch_id, block_id, dept_id, dept_name, stats, sources_list):
        dept_stats = [stats.get((branch_id, block_id, dept_id, source), 0) for source in sources_list]
        return {
            "type": "department",
            "name": dept_name,
            "statistics": dept_stats,
        }, dept_stats

    def _build_block_node(self, branch_id, block_id, block_name, departments, stats, sources_list):
        dept_ids = {k[2]: v for k, v in departments.items() if k[0] == branch_id and k[1] == block_id}
        block_children = []
        block_stats = [0 for _ in sources_list]
        for dept_id, dept_name in dept_ids.items():
            dept_node, dept_stats = self._build_department_node(
                branch_id, block_id, dept_id, dept_name, stats, sources_list
            )
            block_children.append(dept_node)
            for i, val in enumerate(dept_stats):
                block_stats[i] += val
        if not block_children:
            block_stats = [stats.get((branch_id, block_id, None, source), 0) for source in sources_list]
        return {
            "type": "block",
            "name": block_name,
            "statistics": block_stats,
            "children": block_children,
        }, block_stats
