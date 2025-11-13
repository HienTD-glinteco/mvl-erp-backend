from datetime import datetime

from django.db.models import Case, DecimalField, F, Sum, When
from django.db.models.functions import Coalesce
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.hrm.constants import RecruitmentSourceType
from apps.hrm.models import (
    Employee,
    HiredCandidateReport,
    InterviewSchedule,
    RecruitmentCandidate,
    RecruitmentCostReport,
    RecruitmentRequest,
)
from apps.hrm.utils import get_current_month_range, get_last_6_months_range

from ..serializers import (
    DashboardChartDataSerializer,
    DashboardChartFilterSerializer,
    DashboardRealtimeDataSerializer,
)


class RecruitmentDashboardViewSet(viewsets.ViewSet):
    """ViewSet for recruitment dashboard metrics.

    Provides real-time KPIs and chart data for recruitment analytics.
    All data sourced from flat report models for performance.
    """

    @extend_schema(
        summary="Realtime Dashboard KPIs",
        description="Get real-time recruitment KPIs: open positions, applicants today, hires today, interviews today, total employees except resigned.",
        responses={200: DashboardRealtimeDataSerializer},
        examples=[
            OpenApiExample(
                "Success - Realtime KPIs",
                value={
                    "success": True,
                    "data": {
                        "open_positions": 15,
                        "applicants_today": 8,
                        "hires_today": 3,
                        "interviews_today": 5,
                        "employees_today": 120,
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    )
    @action(detail=False, methods=["get"])
    def realtime(self, request):
        """Get real-time recruitment KPIs (no filters supported)."""
        today = datetime.now().date()

        hires_today = self._get_hires_today(today)
        open_positions = self._get_open_positions()
        applicants_today = self._get_applicants_today(today)
        interviews_today = self._get_interviews_today(today)
        total_employees = self._get_total_employees()

        data = {
            "open_positions": open_positions,
            "applicants_today": applicants_today,
            "hires_today": hires_today,
            "interviews_today": interviews_today,
            "employees_today": total_employees,
        }

        serializer = DashboardRealtimeDataSerializer(data)
        return Response(serializer.data)

    @extend_schema(
        summary="Dashboard Chart Data",
        description="Get aggregated data for dashboard charts.",
        parameters=[DashboardChartFilterSerializer],
        responses={200: DashboardChartDataSerializer},
        examples=[
            OpenApiExample(
                "Success - Chart Data",
                value={
                    "success": True,
                    "data": {
                        "experience_breakdown": [
                            {"label": "Experienced", "count": 45, "percentage": 60.0},
                            {"label": "Inexperienced", "count": 30, "percentage": 40.0},
                        ],
                        "branch_breakdown": [
                            {"branch_name": "Hanoi Branch", "count": 40, "percentage": 53.3},
                            {"branch_name": "HCMC Branch", "count": 35, "percentage": 46.7},
                        ],
                        "cost_breakdown": [
                            {
                                "source_type": "referral_source",
                                "total_cost": 50000000.0,
                                "percentage": 35.7,
                            },
                            {
                                "source_type": "marketing_channel",
                                "total_cost": 90000000.0,
                                "percentage": 64.3,
                            },
                        ],
                        "cost_by_branches": {
                            "months": ["10/2025", "11/2025"],
                            "branch_names": ["Hanoi Branch", "HCMC Branch"],
                            "data": [
                                {
                                    "name": "Hanoi Branch",
                                    "type": "branch",
                                    "statistics": [
                                        {
                                            "total_cost": 25000000.0,
                                            "total_hires": 5,
                                            "avg_cost": 5000000.0,
                                        },
                                        {
                                            "total_cost": 21000000.0,
                                            "total_hires": 3,
                                            "avg_cost": 7000000.0,
                                        },
                                    ],
                                },
                                {
                                    "name": "HCMC Branch",
                                    "type": "branch",
                                    "statistics": [
                                        {
                                            "total_cost": 25000000.0,
                                            "total_hires": 5,
                                            "avg_cost": 5000000.0,
                                        },
                                        {
                                            "total_cost": 21000000.0,
                                            "total_hires": 3,
                                            "avg_cost": 7000000.0,
                                        },
                                    ],
                                },
                            ],
                        },
                        "source_type_breakdown": [
                            {"source_type": "referral_source", "count": 25, "percentage": 33.3},
                            {"source_type": "marketing_channel", "count": 30, "percentage": 40.0},
                            {"source_type": "job_website_channel", "count": 20, "percentage": 26.7},
                        ],
                        "monthly_trends": {
                            "months": ["09/2025", "10/2025"],
                            "source_type_names": [
                                "Referral Source",
                                "Marketing Channel",
                                "Job Website Channel",
                                "Recruitment Department Source",
                                "Returning Employee",
                            ],
                            "data": [
                                {"type": "source_type", "name": "Referral Source", "statistics": [10, 20]},
                                {"type": "source_type", "name": "Marketing Channel", "statistics": [10, 20]},
                                {"type": "source_type", "name": "Job Website Channel", "statistics": [10, 20]},
                                {
                                    "type": "source_type",
                                    "name": "Recruitment Department Source",
                                    "statistics": [10, 20],
                                },
                                {"type": "source_type", "name": "Returning Employee", "statistics": [10, 20]},
                            ],
                        },
                    },
                    "error": None,
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Error - Invalid Date Range",
                value={
                    "success": False,
                    "data": None,
                    "error": {"from_date": ["Invalid date format"]},
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    @action(detail=False, methods=["get"])
    def charts(self, request):
        """Get aggregated chart data for dashboard."""
        from_date, to_date, monthly_chart_from_date, monthly_chart_to_date = self._get_date_range(request)

        experience_breakdown = self._get_experience_breakdown(from_date, to_date)
        branch_breakdown = self._get_branch_breakdown(from_date, to_date)
        cost_by_categories = self._get_cost_breakdown_by_categories(from_date, to_date)
        cost_by_branches = self._get_average_cost_breakdown_by_branches(from_date, to_date)
        source_type_breakdown = self._get_source_type_breakdown(from_date, to_date)
        monthly_trends = self._get_monthly_trends(monthly_chart_from_date, monthly_chart_to_date)

        data = {
            "experience_breakdown": experience_breakdown,
            "branch_breakdown": branch_breakdown,
            "cost_breakdown": cost_by_categories,
            "cost_by_branches": cost_by_branches,
            "source_type_breakdown": source_type_breakdown,
            "monthly_trends": monthly_trends,
        }

        serializer = DashboardChartDataSerializer(data)
        return Response(serializer.data)

    def _get_hires_today(self, today):
        """Get number of hires today from HiredCandidateReport."""
        return (
            HiredCandidateReport.objects.filter(report_date=today).aggregate(total=Sum("num_candidates_hired"))[
                "total"
            ]
            or 0
        )

    def _get_open_positions(self):
        """Get number of open positions."""
        return RecruitmentRequest.objects.filter(status=RecruitmentRequest.Status.OPEN).count()

    def _get_applicants_today(self, today):
        """Get number of applicants today."""
        return RecruitmentCandidate.objects.filter(created_at__date=today).count()

    def _get_interviews_today(self, today):
        """Get number of interviews today."""
        return InterviewSchedule.objects.filter(time__date=today).count()

    def _get_total_employees(self):
        """Get total of employees except Resigned."""
        return Employee.objects.exclude(status=Employee.Status.RESIGNED).count()

    def _get_experience_breakdown(self, from_date, to_date):
        """Get experience breakdown from HiredCandidateReport."""
        experience_data = HiredCandidateReport.objects.filter(report_date__range=[from_date, to_date]).aggregate(
            total_hired=Sum("num_candidates_hired"),
            total_experienced=Sum("num_experienced"),
        )

        total_hired = experience_data["total_hired"] or 0
        total_experienced = experience_data["total_experienced"] or 0
        total_inexperienced = total_hired - total_experienced

        return [
            {
                "label": _("Experienced"),
                "count": total_experienced,
                "percentage": round((total_experienced / total_hired * 100) if total_hired > 0 else 0, 1),
            },
            {
                "label": _("Inexperienced"),
                "count": total_inexperienced,
                "percentage": round((total_inexperienced / total_hired * 100) if total_hired > 0 else 0, 1),
            },
        ]

    def _get_branch_breakdown(self, from_date, to_date):
        """Get branch breakdown from HiredCandidateReport."""
        hire_by_branch_data = (
            HiredCandidateReport.objects.filter(report_date__range=[from_date, to_date])
            .values("branch", "branch__name")
            .annotate(total=Sum("num_candidates_hired"))
            .order_by("-total")
        )

        total_by_branch = sum(item["total"] for item in hire_by_branch_data if item["total"])

        return [
            {
                "branch_name": item["branch__name"],
                "count": item["total"],
                "percentage": round((item["total"] / total_by_branch * 100) if total_by_branch > 0 else 0, 1),
            }
            for item in hire_by_branch_data
            if item["total"]
        ]

    def _get_cost_breakdown_by_categories(self, from_date, to_date):
        """Get cost breakdown by cateogries from RecruitmentCostReport."""
        cost_by_categories = (
            RecruitmentCostReport.objects.filter(
                report_date__range=[from_date, to_date],
                source_type__in=[
                    RecruitmentSourceType.REFERRAL_SOURCE.value,
                    RecruitmentSourceType.JOB_WEBSITE_CHANNEL.value,
                    RecruitmentSourceType.MARKETING_CHANNEL.value,
                ],
            )
            .values("source_type")
            .annotate(total_cost=Sum("total_cost"))
            .order_by("-total_cost")
        )

        total_cost_all = sum(item["total_cost"] for item in cost_by_categories if item["total_cost"])

        return [
            {
                "source_type": item["source_type"],
                "total_cost": float(item["total_cost"]) if item["total_cost"] else 0,
                "percentage": round(
                    (float(item["total_cost"]) / float(total_cost_all) * 100) if total_cost_all > 0 else 0, 1
                ),
            }
            for item in cost_by_categories
        ]

    def _get_average_cost_breakdown_by_branches(self, from_date, to_date):
        """Get average cost breakdown by branches from RecruitmentCostReport."""
        cost_by_branches = (
            RecruitmentCostReport.objects.filter(
                report_date__range=[from_date, to_date],
            )
            .values("month_key", "branch__name", "branch")
            .annotate(
                total_cost=Coalesce(
                    Sum("total_cost"),
                    0,
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                ),
                total_hires=Coalesce(
                    Sum("num_hires"),
                    0,
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                ),
            )
            .annotate(
                avg_cost=Case(
                    When(
                        total_hires=0,
                        then=0,
                    ),
                    default=F("total_cost") / F("total_hires"),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            )
            .order_by("month_key", "branch__name")
        )

        # Get all unique month keys and branches
        all_month_keys = sorted({item["month_key"] for item in cost_by_branches})
        all_branches = {}
        for item in cost_by_branches:
            branch_id = item["branch"]
            branch_name = item["branch__name"]
            if branch_id and branch_name:
                all_branches[branch_id] = branch_name

        # Build lookup dict for actual data
        data_lookup = {}
        for item in cost_by_branches:
            key = (item["month_key"], item["branch"])
            data_lookup[key] = {
                "total_cost": float(item["total_cost"]),
                "total_hires": int(item["total_hires"]),
                "avg_cost": float(item["avg_cost"]),
            }

        # Build result list with default values for all combinations
        result = []
        for branch_id, branch_name in sorted(all_branches.items(), key=lambda x: x[1]):
            statistics = []
            for month_key in all_month_keys:
                key = (month_key, branch_id)
                if key in data_lookup:
                    statistics.append(data_lookup[key])
                else:
                    # Default values when no data for this month-branch combination
                    statistics.append(
                        {
                            "total_cost": 0.0,
                            "total_hires": 0,
                            "avg_cost": 0.0,
                        }
                    )

            result.append(
                {
                    "type": "branch",
                    "name": branch_name,
                    "statistics": statistics,
                }
            )

        return {"data": result, "months": all_month_keys, "branch_names": all_branches}

    def _get_source_type_breakdown(self, from_date, to_date):
        """Get source type breakdown from RecruitmentCostReport."""
        source_type_breakdown_data = (
            RecruitmentCostReport.objects.filter(report_date__range=[from_date, to_date])
            .values("source_type")
            .annotate(count=Sum("num_hires"))
            .order_by("source_type")
        )

        total_hired = sum(item["count"] for item in source_type_breakdown_data if item["count"])

        return [
            {
                "source_type": item["source_type"],
                "count": item["count"] if item["count"] else 0,
                "percentage": round((item["count"] / total_hired * 100) if total_hired > 0 else 0, 1),
            }
            for item in source_type_breakdown_data
            if item["count"]
        ]

    def _get_monthly_trends(self, from_date, to_date):
        """Get monthly trends from RecruitmentCostReport."""
        monthly_data = (
            RecruitmentCostReport.objects.filter(report_date__range=[from_date, to_date])
            .values("month_key", "source_type")
            .annotate(total=Sum("num_hires"))
            .order_by("month_key", "source_type")
        )

        # Get all unique month keys and source types
        all_month_keys = sorted({item["month_key"] for item in monthly_data})
        all_source_types = [
            RecruitmentSourceType.REFERRAL_SOURCE.value,
            RecruitmentSourceType.MARKETING_CHANNEL.value,
            RecruitmentSourceType.JOB_WEBSITE_CHANNEL.value,
            RecruitmentSourceType.RECRUITMENT_DEPARTMENT_SOURCE.value,
            RecruitmentSourceType.RETURNING_EMPLOYEE.value,
        ]

        # Build source names list
        source_type_names = [RecruitmentSourceType.get_label(source_type) for source_type in all_source_types]

        # Return empty structure if no data
        if not all_month_keys:
            return {
                "months": [],
                "source_type_names": source_type_names,
                "data": [],
            }

        # Build lookup dict for actual data
        data_lookup = {}
        for item in monthly_data:
            key = (item["month_key"], item["source_type"])
            data_lookup[key] = item["total"] or 0

        # Build result: one item per source type, with statistics across all months
        result = []
        for source_type in all_source_types:
            statistics = []
            for month_key in all_month_keys:
                key = (month_key, source_type)
                count = data_lookup.get(key, 0)
                statistics.append(count)

            result.append(
                {
                    "type": "source_type",
                    "name": RecruitmentSourceType.get_label(source_type),
                    "statistics": statistics,
                }
            )

        return {
            "months": all_month_keys,
            "source_type_names": source_type_names,
            "data": result,
        }

    def _get_date_range(self, request):
        """Extract date range from request or use defaults."""
        from_date = None
        to_date = None
        monthly_chart_from_date = None
        monthly_chart_to_date = None

        filter_serializer = DashboardChartFilterSerializer(data=request.query_params)
        if filter_serializer.is_valid():
            from_date = filter_serializer.validated_data.get("from_date")
            to_date = filter_serializer.validated_data.get("to_date")

        if not from_date and not to_date:
            from_date, to_date = get_current_month_range()
            monthly_chart_from_date, monthly_chart_to_date = get_last_6_months_range()
        else:
            monthly_chart_from_date = from_date
            monthly_chart_to_date = to_date

        return from_date, to_date, monthly_chart_from_date, monthly_chart_to_date
