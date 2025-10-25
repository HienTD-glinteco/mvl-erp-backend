import random
from datetime import datetime

from django.db.models import Sum
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.hrm.constants import RecruitmentSourceType
from apps.hrm.models import HiredCandidateReport, RecruitmentCostReport
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
        description="Get real-time recruitment KPIs: open positions, applicants today, hires today, interviews today.",
        responses={200: DashboardRealtimeDataSerializer},
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "open_positions": 25,
                        "applicants_today": 12,
                        "hires_today": 3,
                        "interviews_today": 8,
                    },
                },
                response_only=True,
            )
        ],
    )
    @action(detail=False, methods=["get"])
    def realtime(self, request):
        """Get real-time recruitment KPIs."""
        # Get today's hires from HiredCandidateReport
        today = datetime.now().date()
        hires_today = (
            HiredCandidateReport.objects.filter(report_date=today).aggregate(total=Sum("num_candidates_hired"))[
                "total"
            ]
            or 0
        )

        # Get applicants and interviews from recruitment request/candidate models
        # TODO: Implement these metrics from appropriate flat models when available
        # For now, returning placeholders

        data = {
            "open_positions": random.randint(0, 100),  # TODO: Implement from JobDescription or similar
            "applicants_today": random.randint(0, 100),  # TODO: Implement from candidate applications
            "hires_today": hires_today,
            "interviews_today": random.randint(0, 100),  # TODO: Implement from interview schedules
        }

        serializer = DashboardRealtimeDataSerializer(data)
        return Response(serializer.data)

    @extend_schema(
        summary="Dashboard Chart Data",
        description="Get aggregated data for dashboard charts: experience breakdown, source/channel distribution, branch breakdown, cost analysis, and monthly trends.",
        parameters=[DashboardChartFilterSerializer],
        responses={200: DashboardChartDataSerializer},
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "experience_breakdown": [
                            {"label": "Has experience", "count": 25, "percentage": 30.5},
                            {"label": "No experience", "count": 35, "percentage": 42.7},
                        ],
                        "branch_breakdown": [
                            {"branch_name": "Hanoi", "count": 50, "percentage": 55.6},
                            {"branch_name": "HCMC", "count": 40, "percentage": 44.4},
                        ],
                        "cost_breakdown": [
                            {
                                "source_type": "Job Websites",
                                "total_cost": 50000000,
                                "percentage": 45.5,
                            },
                            {
                                "source_type": "Marketing",
                                "total_cost": 40000000,
                                "percentage": 36.4,
                            },
                        ],
                        "source_type_breakdown": [
                            {
                                "source_type": "Referral Source",
                                "count": 30,
                                "percentage": 40.0,
                            },
                            {
                                "source_type": "Marketing Channel",
                                "count": 45,
                                "percentage": 60.0,
                            },
                        ],
                        "monthly_trends": [
                            {
                                "month": "2025-10",
                                "referral_source": 10,
                                "marketing_channel": 15,
                                "job_website_channel": 20,
                                "recruitment_department_source": 5,
                                "returning_employee": 2,
                            }
                        ],
                    },
                },
                response_only=True,
            )
        ],
    )
    @action(detail=False, methods=["get"])
    def charts(self, request):
        """Get aggregated chart data for dashboard."""
        from_date, to_date, monthly_chart_from_date, monthly_chart_to_date = self._get_date_range(request)

        # 1. Experience breakdown from HiredCandidateReport
        experience_data = HiredCandidateReport.objects.filter(report_date__range=[from_date, to_date]).aggregate(
            total_hired=Sum("num_candidates_hired"),
            total_experienced=Sum("num_experienced"),
        )

        total_hired = experience_data["total_hired"] or 0
        total_experienced = experience_data["total_experienced"] or 0
        total_inexperienced = total_hired - total_experienced

        experience_breakdown = [
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

        # 2. Hire by branch from HiredCandidateReport
        hire_by_branch_data = (
            HiredCandidateReport.objects.filter(report_date__range=[from_date, to_date])
            .values("branch", "branch__name")
            .annotate(total=Sum("num_candidates_hired"))
            .order_by("-total")
        )

        total_by_branch = sum(item["total"] for item in hire_by_branch_data)

        hire_by_branch = [
            {
                "branch_name": item["branch__name"],
                "count": item["total"],
                "percentage": round((item["total"] / total_by_branch * 100) if total_by_branch > 0 else 0, 1),
            }
            for item in hire_by_branch_data
        ]

        # 3. Cost analysis from RecruitmentCostReport
        cost_by_category = (
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

        total_cost_all = sum(item["total_cost"] for item in cost_by_category if item["total_cost"])

        cost_analysis = [
            {
                "source_type": RecruitmentSourceType.get_label(item["source_type"]),
                "total_cost": float(item["total_cost"]) if item["total_cost"] else 0,
                "percentage": round(
                    (float(item["total_cost"]) / float(total_cost_all) * 100) if total_cost_all > 0 else 0, 1
                ),
            }
            for item in cost_by_category
        ]

        # 4. source_type_breakdown
        source_type_breakdown_data = (
            RecruitmentCostReport.objects.filter(
                report_date__range=[from_date, to_date],
            )
            .values("source_type")
            .annotate(count=Sum("num_hires"))
            .order_by("source_type")
        )

        total_hired = sum(item["count"] for item in source_type_breakdown_data if item["count"])

        source_type_breakdown = [
            {
                "source_type": RecruitmentSourceType.get_label(item["source_type"]),
                "count": float(item["count"]) if item["count"] else 0,
                "percentage": round((float(item["count"]) / float(total_hired) * 100) if total_hired > 0 else 0, 1),
            }
            for item in source_type_breakdown_data
        ]

        # 5. Monthly trends from RecruitmentCostReport
        monthly_data = (
            RecruitmentCostReport.objects.filter(report_date__range=[monthly_chart_from_date, monthly_chart_to_date])
            .values("month_key", "source_type")
            .annotate(total=Sum("num_hires"))
            .order_by("month_key")
        )

        # Group by month
        months = {}
        for item in monthly_data:
            month = item["month_key"]
            category = item["source_type"]
            value = item["total"]

            if month not in months:
                months[month] = {
                    "month": month,
                    "referral_source": 0,
                    "marketing_channel": 0,
                    "job_website_channel": 0,
                    "recruitment_department_source": 0,
                    "returning_employee": 0,
                }

            months[month][category] = value

        monthly_trends = list(months.values())

        data = {
            "experience_breakdown": experience_breakdown,
            "branch_breakdown": hire_by_branch,
            "cost_breakdown": cost_analysis,
            "source_type_breakdown": source_type_breakdown,
            "monthly_trends": monthly_trends,
        }

        serializer = DashboardChartDataSerializer(data)
        return Response(serializer.data)

    def _get_date_range(self, request):
        """Extract date range from request or use current month as default."""
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
