from collections import defaultdict
from decimal import Decimal

from django.db.models import Sum
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
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

    @extend_schema(
        summary="Staff Growth Report",
        description="Aggregate staff changes (introductions, returns, new hires, transfers, resignations) by period (week/month).",
        parameters=[StaffGrowthReportParametersSerializer],
        responses={200: StaffGrowthReportAggregatedSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="staff-growth")
    def staff_growth(self, request):
        """
        Aggregate staff growth data by week or month period.
        Returns a list of period objects with staff change statistics for each period.
        """
        queryset, _, start_date, end_date, period_type = self._prepare_report_queryset(
            request,
            StaffGrowthReportParametersSerializer,
            StaffGrowthReport,
        )

        aggregated = (
            queryset.values("branch", "branch__name", "block", "block__name", "department", "department__name")
            .annotate(
                num_introductions=Sum("num_introductions"),
                num_returns=Sum("num_returns"),
                num_new_hires=Sum("num_new_hires"),
                num_transfers=Sum("num_transfers"),
                num_resignations=Sum("num_resignations"),
            )
            .order_by("branch", "block", "department")
        )

        results = [
            {
                "period_type": period_type,
                "label": self._generate_period_label(period_type, start_date, end_date),
                "num_introductions": item["num_introductions"] or 0,
                "num_returns": item["num_returns"] or 0,
                "num_new_hires": item["num_new_hires"] or 0,
                "num_transfers": item["num_transfers"] or 0,
                "num_resignations": item["num_resignations"] or 0,
            }
            for item in aggregated
        ]

        serializer = StaffGrowthReportAggregatedSerializer(results, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Recruitment Source Report",
        description="Aggregate hire statistics by recruitment source in nested organizational format (no period aggregation).",
        parameters=[RecruitmentSourceReportParametersSerializer],
        responses={200: RecruitmentSourceReportAggregatedSerializer},
    )
    @action(detail=False, methods=["get"], url_path="recruitment-source")
    def recruitment_source(self, request):
        """
        Aggregate recruitment source data in nested format (branch > block > department).
        Returns a nested list of branches, each with blocks and departments, and hire statistics by source.
        """
        queryset, _, _, _, _ = self._prepare_report_queryset(
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
        description="Aggregate hire statistics by recruitment channel in nested organizational format (no period aggregation).",
        parameters=[RecruitmentChannelReportParametersSerializer],
        responses={200: RecruitmentChannelReportAggregatedSerializer},
    )
    @action(detail=False, methods=["get"], url_path="recruitment-channel")
    def recruitment_channel(self, request):
        """
        Aggregate recruitment channel data in nested format (branch > block > department).
        Returns a nested list of branches, each with blocks and departments, and hire statistics by channel.
        """
        queryset, _, _, _, _ = self._prepare_report_queryset(
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
    )
    @action(detail=False, methods=["get"], url_path="recruitment-cost")
    def recruitment_cost(self, request):
        """
        Aggregate recruitment cost data by source type and months.
        Returns a list of source types, each with monthly and total cost, count, and average.
        """
        queryset, _, _, _, _ = self._prepare_report_queryset(
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
        description="Aggregate hired candidate statistics by source type with period aggregation (week/month) and conditional employee details.",
        parameters=[HiredCandidateReportParametersSerializer],
        responses={200: HiredCandidateReportAggregatedSerializer},
    )
    @action(detail=False, methods=["get"], url_path="hired-candidate")
    def hired_candidate(self, request):
        """
        Aggregate hired candidate data by source type with monthly statistics and conditional employee details for referral_source.
        Returns a list of source types, each with statistics per period and, for referral_source, a breakdown by employee.
        """
        queryset, _, start_date, end_date, period_type = self._prepare_report_queryset(
            request,
            HiredCandidateReportParametersSerializer,
            HiredCandidateReport,
        )

        raw_stats = list(
            queryset.values("month_key", "source_type", "employee__code", "employee__fullname")
            .annotate(total_hired=Sum("num_candidates_hired"))
            .order_by("source_type", "employee__fullname", "month_key")
        )

        months, months_labels = self._get_months_and_labels(period_type, start_date, end_date, raw_stats)
        stats, emp_stats, emp_code_to_name = self._aggregate_hired_candidate_stats(raw_stats)
        data = self._format_hired_candidate_result(months, stats, emp_stats, emp_code_to_name)

        result = {
            "period_type": period_type,
            "months": months_labels,
            "sources": [_("Total Hired")],
            "data": data,
        }

        serializer = HiredCandidateReportAggregatedSerializer(result)
        return Response(serializer.data)

    @extend_schema(
        summary="Referral Cost Report",
        description="Referral cost report with department summary and employee details (always restricted to single month).",
        parameters=[ReferralCostReportParametersSerializer],
        responses={200: ReferralCostReportAggregatedSerializer},
    )
    @action(detail=False, methods=["get"], url_path="referral-cost")
    def referral_cost(self, request):
        """
        Generate referral cost report from RecruitmentExpense for a single month, with branch/block/department filters.
        Returns a list of departments, each with referral expenses and employees, and a total summary.
        """
        queryset, _, _, _, _ = self._prepare_report_queryset(
            request,
            ReferralCostReportParametersSerializer,
            RecruitmentExpense,
            period_param="month",  # Referral cost uses 'month' param
            date_field="expense_date",
        )
        queryset = queryset.filter(recruitment_source__allow_referral=True)
        queryset = queryset.select_related(
            "employee", "employee__department", "referee", "referrer", "recruitment_source"
        )

        departments = {}
        summary_total = Decimal("0")

        for expense in queryset:
            dept_name = (
                expense.employee.department.name
                if expense.employee and expense.employee.department
                else _("No Department")
            )

            if dept_name not in departments:
                departments[dept_name] = {
                    "name": dept_name,
                    "items": [],
                }

            departments[dept_name]["items"].append(expense)
            summary_total += expense.amount

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

    def _get_months_and_labels(self, period_type, start_date, end_date, raw_stats):
        months_set = set()
        for item in raw_stats:
            if item["month_key"]:
                months_set.add(item["month_key"])
        if period_type == ReportPeriodType.MONTH.value:
            months = []
            cur = start_date.replace(day=1)
            while cur <= end_date:
                months.append(f"{cur.month:02d}/{cur.year}")
                if cur.month == 12:
                    cur = cur.replace(year=cur.year + 1, month=1)
                else:
                    cur = cur.replace(month=cur.month + 1)
        else:
            months = sorted(months_set)
        months = sorted((m for m in months_set))
        months_labels = months + [_("Total")]
        return months, months_labels

    def _aggregate_hired_candidate_stats(self, raw_stats):
        stats = defaultdict(lambda: defaultdict(int))
        emp_stats = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
        emp_code_to_name = {}
        for item in raw_stats:
            source_type = item["source_type"]
            month_key = item["month_key"]
            total_hired = item["total_hired"] or 0
            employee_code = item.get("employee__code")
            employee_fullname = item.get("employee__fullname")
            stats[source_type][month_key] += total_hired
            if source_type == RecruitmentSourceType.REFERRAL_SOURCE.value and employee_code:
                emp_stats[employee_code][source_type][month_key] += total_hired
                emp_code_to_name[employee_code] = employee_fullname
        return stats, emp_stats, emp_code_to_name

    def _format_hired_candidate_result(self, months, stats, emp_stats, emp_code_to_name):
        data = []
        for source_type_value in RecruitmentSourceType.values:
            source_type_label = RecruitmentSourceType.get_label(source_type_value)
            statistics = []
            total_hired_sum = 0
            for m in months:
                hired = stats[source_type_value][m] if m in stats[source_type_value] else 0
                statistics.append([hired])
                total_hired_sum += hired
            statistics.append([total_hired_sum])

            children = []
            if source_type_value == RecruitmentSourceType.REFERRAL_SOURCE.value:
                sorted_emps = sorted(emp_stats.items(), key=lambda x: emp_code_to_name.get(x[0], ""))
                for emp_code, emp_source_dict in sorted_emps:
                    if source_type_value not in emp_source_dict:
                        continue
                    emp_statistics = []
                    emp_total_hired = 0
                    for m in months:
                        hired = emp_source_dict[source_type_value][m] if m in emp_source_dict[source_type_value] else 0
                        emp_statistics.append([hired])
                        emp_total_hired += hired
                    emp_statistics.append([emp_total_hired])
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
        self, request, param_serializer_class, model_class, period_param="period", date_field="report_date"
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
        if params.get("branch"):
            queryset = queryset.filter(branch_id=params["branch"])
        if params.get("block"):
            queryset = queryset.filter(block_id=params["block"])
        if params.get("department"):
            queryset = queryset.filter(department_id=params["department"])

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
        # Fetch all relevant data in one query
        rows = list(
            queryset.values(
                "branch", "branch__name", "block", "block__name", "department", "department__name", source_field
            ).annotate(total=Sum(value_field))
        )

        # Organize data for fast lookup
        # Structure: {(branch, block, department, source): total}
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

            # Collect unique branches, blocks, departments
            if branch_id is not None:
                branches[branch_id] = row["branch__name"]
            if block_id is not None:
                blocks[(branch_id, block_id)] = row["block__name"]
            if dept_id is not None:
                departments[(branch_id, block_id, dept_id)] = row["department__name"]

        # Build nested structure
        data = []
        for branch_id, branch_name in branches.items():
            branch_stats = [stats.get((branch_id, None, None, source), 0) for source in sources_list]
            branch_children = []
            # Find blocks for this branch
            block_ids = {k[1]: v for k, v in blocks.items() if k[0] == branch_id}
            for block_id, block_name in block_ids.items():
                block_stats = [stats.get((branch_id, block_id, None, source), 0) for source in sources_list]
                block_children = []
                # Find departments for this branch/block
                dept_ids = {k[2]: v for k, v in departments.items() if k[0] == branch_id and k[1] == block_id}
                for dept_id, dept_name in dept_ids.items():
                    dept_stats = [stats.get((branch_id, block_id, dept_id, source), 0) for source in sources_list]
                    block_children.append(
                        {
                            "type": "department",
                            "name": dept_name,
                            "statistics": dept_stats,
                        }
                    )
                branch_children.append(
                    {
                        "type": "block",
                        "name": block_name,
                        "statistics": block_stats,
                        "children": block_children,
                    }
                )
            data.append(
                {
                    "type": "branch",
                    "name": branch_name,
                    "statistics": branch_stats,
                    "children": branch_children,
                }
            )
        return data
