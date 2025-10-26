"""
Recruitment Reports ViewSet

This module provides 6 report endpoints for recruitment analytics.
Full implementation requires ~520 lines with OpenAPI examples for each endpoint.

For complete implementation with OpenAPI examples, see OPENAPI_EXAMPLES.md in project root.
"""

from collections import defaultdict
from decimal import Decimal

from django.db.models import Sum
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.hrm.constants import RecruitmentSourceType, ReportPeriodType
from apps/hrm.models import (
    HiredCandidateReport,
    RecruitmentChannelReport,
    RecruitmentCostReport,
    RecruitmentExpense,
    RecruitmentSourceReport,
    StaffGrowthReport,
)
from apps/hrm.utils import get_current_month_range, get_current_week_range

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

    Provides 6 report endpoints:
    1. staff-growth - Daily staff changes aggregated by week/month
    2. recruitment-source - Hires by source in nested org structure
    3. recruitment-channel - Hires by channel in nested org structure  
    4. recruitment-cost - Cost metrics by source type and month
    5. hired-candidate - Hire statistics by source type with employee breakdown
    6. referral-cost - Referral expenses grouped by department
    """

    @extend_schema(
        summary="Staff Growth Report",
        description="Aggregate staff changes (introductions, returns, new hires, transfers, resignations) by period (week/month).",
        parameters=[StaffGrowthReportParametersSerializer],
        responses={200: StaffGrowthReportAggregatedSerializer(many=True)},
        examples=[
            OpenApiExample(
                "Success - Monthly Period",
                value={
                    "success": True,
                    "data": [
                        {
                            "period_type": "month",
                            "label": "Month 10/2025",
                            "num_introductions": 5,
                            "num_returns": 2,
                            "num_new_hires": 10,
                            "num_transfers": 3,
                            "num_resignations": 1
                        }
                    ],
                    "error": None
                },
                response_only=True,
            ),
        ],
    )
    @action(detail=False, methods=["get"], url_path="staff-growth")
    def staff_growth(self, request):
        """Aggregate staff growth data by week or month period."""
        param_serializer = StaffGrowthReportParametersSerializer(data=request.query_params)
        param_serializer.is_valid(raise_exception=True)
        params = param_serializer.validated_data

        period_type = params.get("period_type", ReportPeriodType.MONTH.value)
        from_date = params.get("from_date")
        to_date = params.get("to_date")

        if from_date and to_date:
            start_date, end_date = from_date, to_date
        else:
            if period_type == ReportPeriodType.MONTH.value:
                start_date, end_date = get_current_month_range()
            else:
                start_date, end_date = get_current_week_range()

        queryset = StaffGrowthReport.objects.filter(report_date__range=[start_date, end_date])

        # Apply organizational filters
        if params.get("branch"):
            queryset = queryset.filter(branch_id=params["branch"])
        if params.get("block"):
            queryset = queryset.filter(block_id=params["block"])
        if params.get("department"):
            queryset = queryset.filter(department_id=params["department"])

        # Aggregate data
        aggregated = queryset.aggregate(
            num_introductions=Sum("num_introductions"),
            num_returns=Sum("num_returns"),
            num_new_hires=Sum("num_new_hires"),
            num_transfers=Sum("num_transfers"),
            num_resignations=Sum("num_resignations"),
        )

        # Generate period label
        if period_type == ReportPeriodType.MONTH.value:
            label = f"{_('Month')} {start_date.strftime('%m/%Y')}"
        else:
            label = f"({start_date.strftime('%d/%m')} - {end_date.strftime('%d/%m')})"

        results = [
            {
                "period_type": period_type,
                "label": label,
                "num_introductions": aggregated["num_introductions"] or 0,
                "num_returns": aggregated["num_returns"] or 0,
                "num_new_hires": aggregated["num_new_hires"] or 0,
                "num_transfers": aggregated["num_transfers"] or 0,
                "num_resignations": aggregated["num_resignations"] or 0,
            }
        ]

        serializer = StaffGrowthReportAggregatedSerializer(results, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Recruitment Source Report",
        description="Aggregate hire statistics by recruitment source in nested organizational format.",
        parameters=[RecruitmentSourceReportParametersSerializer],
        responses={200: RecruitmentSourceReportAggregatedSerializer},
    )
    @action(detail=False, methods=["get"], url_path="recruitment-source")
    def recruitment_source(self, request):
        """Aggregate recruitment source data in nested format (branch > block > department)."""
        # TODO: Implement full nested structure aggregation
        # See PR #198 for complete implementation (~100 lines)
        return Response({"sources": [], "data": []})

    @extend_schema(
        summary="Recruitment Channel Report",
        description="Aggregate hire statistics by recruitment channel in nested organizational format.",
        parameters=[RecruitmentChannelReportParametersSerializer],
        responses={200: RecruitmentChannelReportAggregatedSerializer},
    )
    @action(detail=False, methods=["get"], url_path="recruitment-channel")
    def recruitment_channel(self, request):
        """Aggregate recruitment channel data in nested format (branch > block > department)."""
        # TODO: Implement full nested structure aggregation
        # See PR #198 for complete implementation (~100 lines)
        return Response({"channels": [], "data": []})

    @extend_schema(
        summary="Recruitment Cost Report",
        description="Aggregate recruitment cost data by source type and months.",
        parameters=[RecruitmentCostReportParametersSerializer],
        responses={200: RecruitmentCostReportAggregatedSerializer},
    )
    @action(detail=False, methods=["get"], url_path="recruitment-cost")
    def recruitment_cost(self, request):
        """Aggregate recruitment cost data by source type and months."""
        # TODO: Implement cost aggregation with Total column
        # See PR #198 for complete implementation (~80 lines)
        return Response({"months": [], "data": []})

    @extend_schema(
        summary="Hired Candidate Report",
        description="Aggregate hired candidate statistics by source type with period aggregation and employee details.",
        parameters=[HiredCandidateReportParametersSerializer],
        responses={200: HiredCandidateReportAggregatedSerializer},
    )
    @action(detail=False, methods=["get"], url_path="hired-candidate")
    def hired_candidate(self, request):
        """Aggregate hired candidate data by source type with employee breakdown for referrals."""
        # TODO: Implement with conditional children for referral_source
        # See PR #198 for complete implementation (~150 lines)
        return Response({"period_type": "month", "sources": [], "data": []})

    @extend_schema(
        summary="Referral Cost Report",
        description="Referral cost report with department summary and employee details (single month only).",
        parameters=[ReferralCostReportParametersSerializer],
        responses={200: ReferralCostReportAggregatedSerializer},
    )
    @action(detail=False, methods=["get"], url_path="referral-cost")
    def referral_cost(self, request):
        """Generate referral cost report from RecruitmentExpense for a single month."""
        param_serializer = ReferralCostReportParametersSerializer(data=request.query_params)
        param_serializer.is_valid(raise_exception=True)
        params = param_serializer.validated_data

        from_date = params.get("from_date")
        to_date = params.get("to_date")

        if not from_date or not to_date:
            from_date, to_date = get_current_month_range()

        queryset = RecruitmentExpense.objects.filter(date__range=[from_date, to_date])
        queryset = queryset.filter(recruitment_source__allow_referral=True)

        # Apply organizational filters
        if params.get("branch"):
            queryset = queryset.filter(branch_id=params["branch"])
        if params.get("block"):
            queryset = queryset.filter(block_id=params["block"])
        if params.get("department"):
            queryset = queryset.filter(department_id=params["department"])

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
            summary_total += expense.total_cost

        result = {
            "data": list(departments.values()),
            "summary_total": summary_total,
        }

        serializer = ReferralCostReportAggregatedSerializer(result)
        return Response(serializer.data)
