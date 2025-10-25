from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.hrm.constants import RecruitmentSourceType
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
    """ViewSet for recruitment reports with aggregated data.

    Only staff_growth and hired_candidate reports aggregate by week/month periods.
    Other reports aggregate by organizational hierarchy or source type.
    No pagination - returns full aggregated datasets.
    """

    @extend_schema(
        summary="Staff Growth Report",
        description="Aggregate staff changes (introductions, returns, new hires, transfers, resignations) by period (week/month).",
        request=StaffGrowthReportParametersSerializer,
        responses={200: StaffGrowthReportAggregatedSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="staff-growth")
    def staff_growth(self, request):
        """Aggregate staff growth data by week or month period."""
        param_serializer = StaffGrowthReportParametersSerializer(data=request.query_params)
        param_serializer.is_valid(raise_exception=True)
        params = param_serializer.validated_data
        
        period_type = params.get("period", "month")
        from_date = params.get("from_date")
        to_date = params.get("to_date")
        
        if from_date and to_date:
            start_date, end_date = from_date, to_date
        else:
            if period_type == "week":
                start_date, end_date = get_current_week_range()
            else:
                start_date, end_date = get_current_month_range()

        queryset = StaffGrowthReport.objects.filter(report_date__range=[start_date, end_date])
        
        # Apply organizational filters
        if params.get("branch"):
            queryset = queryset.filter(branch_id=params["branch"])
        if params.get("block"):
            queryset = queryset.filter(block_id=params["block"])
        if params.get("department"):
            queryset = queryset.filter(department_id=params["department"])

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
        request=RecruitmentSourceReportParametersSerializer,
        responses={200: RecruitmentSourceReportAggregatedSerializer},
    )
    @action(detail=False, methods=["get"], url_path="recruitment-source")
    def recruitment_source(self, request):
        """Aggregate recruitment source data in nested format (branch > block > department)."""
        param_serializer = RecruitmentSourceReportParametersSerializer(data=request.query_params)
        param_serializer.is_valid(raise_exception=True)
        params = param_serializer.validated_data
        
        from_date = params.get("from_date")
        to_date = params.get("to_date")
        
        if from_date and to_date:
            start_date, end_date = from_date, to_date
        else:
            start_date, end_date = get_current_month_range()

        queryset = RecruitmentSourceReport.objects.filter(report_date__range=[start_date, end_date])
        
        # Apply organizational filters
        if params.get("branch"):
            queryset = queryset.filter(branch_id=params["branch"])
        if params.get("block"):
            queryset = queryset.filter(block_id=params["block"])
        if params.get("department"):
            queryset = queryset.filter(department_id=params["department"])
            
        queryset = queryset.select_related("recruitment_source", "branch", "block", "department")

        sources = list(queryset.values_list("recruitment_source__name", flat=True).distinct().order_by("recruitment_source__name"))
        
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
        request=RecruitmentChannelReportParametersSerializer,
        responses={200: RecruitmentChannelReportAggregatedSerializer},
    )
    @action(detail=False, methods=["get"], url_path="recruitment-channel")
    def recruitment_channel(self, request):
        """Aggregate recruitment channel data in nested format (branch > block > department)."""
        param_serializer = RecruitmentChannelReportParametersSerializer(data=request.query_params)
        param_serializer.is_valid(raise_exception=True)
        params = param_serializer.validated_data
        
        from_date = params.get("from_date")
        to_date = params.get("to_date")
        
        if from_date and to_date:
            start_date, end_date = from_date, to_date
        else:
            start_date, end_date = get_current_month_range()

        queryset = RecruitmentChannelReport.objects.filter(report_date__range=[start_date, end_date])
        
        # Apply organizational filters
        if params.get("branch"):
            queryset = queryset.filter(branch_id=params["branch"])
        if params.get("block"):
            queryset = queryset.filter(block_id=params["block"])
        if params.get("department"):
            queryset = queryset.filter(department_id=params["department"])
            
        queryset = queryset.select_related("recruitment_channel", "branch", "block", "department")

        sources = list(queryset.values_list("recruitment_channel__name", flat=True).distinct().order_by("recruitment_channel__name"))
        
        data = self._build_nested_structure(queryset, sources, "recruitment_channel__name", "num_hires")

        result = {
            "sources": sources,
            "data": data,
        }

        serializer = RecruitmentChannelReportAggregatedSerializer(result)
        return Response(serializer.data)

    @extend_schema(
        summary="Recruitment Cost Report",
        description="Aggregate recruitment cost data by source type and months (no period aggregation).",
        request=RecruitmentCostReportParametersSerializer,
        responses={200: RecruitmentCostReportAggregatedSerializer},
    )
    @action(detail=False, methods=["get"], url_path="recruitment-cost")
    def recruitment_cost(self, request):
        """Aggregate recruitment cost data by source type and months."""
        param_serializer = RecruitmentCostReportParametersSerializer(data=request.query_params)
        param_serializer.is_valid(raise_exception=True)
        params = param_serializer.validated_data
        
        from_date = params.get("from_date")
        to_date = params.get("to_date")
        
        if from_date and to_date:
            start_date, end_date = from_date, to_date
        else:
            start_date, end_date = get_current_month_range()

        queryset = RecruitmentCostReport.objects.filter(report_date__range=[start_date, end_date])
        
        # Apply organizational filters
        if params.get("branch"):
            queryset = queryset.filter(branch_id=params["branch"])
        if params.get("block"):
            queryset = queryset.filter(block_id=params["block"])
        if params.get("department"):
            queryset = queryset.filter(department_id=params["department"])

        month_stats = queryset.values("month_key", "source_type").annotate(
            total=Sum("total_cost"),
            count=Sum("num_hires"),
        ).order_by("month_key", "source_type")

        months_set = sorted(set(item["month_key"] for item in month_stats))
        months_list = months_set + [_("Total")]

        source_types = sorted(set(item["source_type"] for item in month_stats))

        data = []
        for source_type in source_types:
            source_months = []
            total_total = Decimal("0")
            total_count = 0

            for month in months_set:
                month_data = next(
                    (item for item in month_stats if item["month_key"] == month and item["source_type"] == source_type),
                    None
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
                source_months.append({
                    "total": total,
                    "count": count,
                    "avg": avg,
                })

            total_avg = (total_total / total_count) if total_count > 0 else Decimal("0")
            source_months.append({
                "total": total_total,
                "count": total_count,
                "avg": total_avg,
            })

            data.append({
                "source_type": source_type,
                "months": source_months,
            })

        result = {
            "months": months_list,
            "data": data,
        }

        serializer = RecruitmentCostReportAggregatedSerializer(result)
        return Response(serializer.data)

    @extend_schema(
        summary="Hired Candidate Report",
        description="Aggregate hired candidate statistics by source type with period aggregation (week/month) and conditional employee details.",
        request=HiredCandidateReportParametersSerializer,
        responses={200: HiredCandidateReportAggregatedSerializer},
    )
    @action(detail=False, methods=["get"], url_path="hired-candidate")
    def hired_candidate(self, request):
        """Aggregate hired candidate data by source type with conditional employee details for referral_source."""
        param_serializer = HiredCandidateReportParametersSerializer(data=request.query_params)
        param_serializer.is_valid(raise_exception=True)
        params = param_serializer.validated_data
        
        period_type = params.get("period", "month")
        from_date = params.get("from_date")
        to_date = params.get("to_date")
        
        if from_date and to_date:
            start_date, end_date = from_date, to_date
        else:
            if period_type == "week":
                start_date, end_date = get_current_week_range()
            else:
                start_date, end_date = get_current_month_range()

        queryset = HiredCandidateReport.objects.filter(report_date__range=[start_date, end_date])
        
        # Apply organizational filters
        if params.get("branch"):
            queryset = queryset.filter(branch_id=params["branch"])
        if params.get("block"):
            queryset = queryset.filter(block_id=params["block"])
        if params.get("department"):
            queryset = queryset.filter(department_id=params["department"])

        sources = list(RecruitmentSourceType.labels)

        source_stats = queryset.values("source_type").annotate(
            total_hired=Sum("num_candidates_hired"),
            total_experienced=Sum("num_experienced"),
        ).order_by("source_type")

        data = []
        for source_type_value in RecruitmentSourceType.values:
            source_type_label = RecruitmentSourceType.get_label(source_type_value)
            
            stats = next(
                (item for item in source_stats if item["source_type"] == source_type_value),
                {"total_hired": 0, "total_experienced": 0}
            )

            total_hired = stats["total_hired"] or 0
            total_experienced = stats["total_experienced"] or 0
            total_inexperienced = total_hired - total_experienced

            statistics = [total_hired, total_experienced, total_inexperienced]

            children = []
            if source_type_value == RecruitmentSourceType.REFERRAL_SOURCE.value:
                employee_stats = queryset.filter(
                    source_type=source_type_value,
                    employee__isnull=False,
                ).values("employee__code", "employee__fullname").annotate(
                    total_hired=Sum("num_candidates_hired"),
                    total_experienced=Sum("num_experienced"),
                ).order_by("employee__code")

                for emp_stat in employee_stats:
                    emp_hired = emp_stat["total_hired"] or 0
                    emp_experienced = emp_stat["total_experienced"] or 0
                    emp_inexperienced = emp_hired - emp_experienced

                    children.append({
                        "type": "employee",
                        "name": f"{emp_stat['employee__code']} - {emp_stat['employee__fullname']}",
                        "statistics": [emp_hired, emp_experienced, emp_inexperienced],
                    })

            data.append({
                "type": "source_type",
                "name": source_type_label,
                "statistics": statistics,
                "children": children,
            })

        result = {
            "period_type": period_type,
            "sources": [_("Total Hired"), _("Experienced"), _("Inexperienced")],
            "data": data,
        }

        serializer = HiredCandidateReportAggregatedSerializer(result)
        return Response(serializer.data)

    @extend_schema(
        summary="Referral Cost Report",
        description="Referral cost report with department summary and employee details (always restricted to single month).",
        request=ReferralCostReportParametersSerializer,
        responses={200: ReferralCostReportAggregatedSerializer},
    )
    @action(detail=False, methods=["get"], url_path="referral-cost")
    def referral_cost(self, request):
        """Generate referral cost report from RecruitmentExpense for a single month."""
        param_serializer = ReferralCostReportParametersSerializer(data=request.query_params)
        param_serializer.is_valid(raise_exception=True)
        params = param_serializer.validated_data
        
        month_param = params.get("month")
        if month_param:
            try:
                year, month = map(int, month_param.split("-"))
                start_date = datetime(year, month, 1).date()
                if month == 12:
                    end_date = datetime(year + 1, 1, 1).date() - timedelta(days=1)
                else:
                    end_date = datetime(year, month + 1, 1).date() - timedelta(days=1)
            except (ValueError, AttributeError):
                start_date, end_date = get_current_month_range()
        else:
            start_date, end_date = get_current_month_range()

        expenses = RecruitmentExpense.objects.filter(
            expense_date__range=[start_date, end_date],
            recruitment_source__allow_referral=True,
        ).select_related("employee", "employee__department", "referee", "referrer", "recruitment_source")

        departments = {}
        summary_total = Decimal("0")

        for expense in expenses:
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

    def _generate_period_label(self, period_type, start_date, end_date):
        """Generate period label based on period type."""
        if period_type == "week":
            return f"({start_date.strftime('%d/%m')} - {end_date.strftime('%d/%m')})"
        else:
            return f"{_('Month')} {start_date.strftime('%m/%Y')}"

    def _build_nested_structure(self, queryset, sources_list, source_field, value_field):
        """Build nested organizational structure for source/channel reports."""
        branches = queryset.values("branch", "branch__name").distinct().order_by("branch")

        data = []
        for branch in branches:
            if branch["branch"] is None:
                continue

            branch_stats = []
            for source in sources_list:
                total = (
                    queryset.filter(branch=branch["branch"], **{source_field: source})
                    .aggregate(total=Sum(value_field))["total"]
                    or 0
                )
                branch_stats.append(total)

            blocks = queryset.filter(branch=branch["branch"]).values("block", "block__name").distinct().order_by("block")
            
            branch_children = []
            for block in blocks:
                if block["block"] is None:
                    continue

                block_stats = []
                for source in sources_list:
                    total = (
                        queryset.filter(branch=branch["branch"], block=block["block"], **{source_field: source})
                        .aggregate(total=Sum(value_field))["total"]
                        or 0
                    )
                    block_stats.append(total)

                departments = queryset.filter(branch=branch["branch"], block=block["block"]).values("department", "department__name").distinct().order_by("department")

                block_children = []
                for dept in departments:
                    if dept["department"] is None:
                        continue

                    dept_stats = []
                    for source in sources_list:
                        total = (
                            queryset.filter(
                                branch=branch["branch"],
                                block=block["block"],
                                department=dept["department"],
                                **{source_field: source}
                            ).aggregate(total=Sum(value_field))["total"]
                            or 0
                        )
                        dept_stats.append(total)

                    block_children.append({
                        "type": "department",
                        "name": dept["department__name"],
                        "statistics": dept_stats,
                    })

                branch_children.append({
                    "type": "block",
                    "name": block["block__name"],
                    "statistics": block_stats,
                    "children": block_children,
                })

            data.append({
                "type": "branch",
                "name": branch["branch__name"],
                "statistics": branch_stats,
                "children": branch_children,
            })

        return data
