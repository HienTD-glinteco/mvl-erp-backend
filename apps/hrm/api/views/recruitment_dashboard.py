"""
Recruitment Dashboard ViewSet

This module provides 2 dashboard endpoints for real-time recruitment metrics.
"""

from datetime import datetime

from django.db.models import Coalesce, Sum
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.hrm.constants import RecruitmentSourceType
from apps.hrm.models import (
    HiredCandidateReport,
    InterviewSchedule,
    JobDescription,
    RecruitmentCandidate,
    RecruitmentCostReport,
)
from apps/hrm.utils import get_current_month_range, get_last_6_months_range

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
                "Success - Realtime KPIs",
                value={
                    "success": True,
                    "data": {
                        "open_positions": 15,
                        "applicants_today": 8,
                        "hires_today": 3,
                        "interviews_today": 12
                    },
                    "error": None
                },
                response_only=True,
            ),
        ],
    )
    @action(detail=False, methods=["get"])
    def realtime(self, request):
        """Get real-time recruitment KPIs (no filters supported)."""
        today = datetime.now().date()

        # Get KPIs
        hires_today = (
            HiredCandidateReport.objects.filter(report_date=today)
            .aggregate(total=Sum("num_candidates_hired"))["total"]
            or 0
        )
        open_positions = JobDescription.objects.filter(status="open").count()
        applicants_today = RecruitmentCandidate.objects.filter(created_at__date=today).count()
        interviews_today = InterviewSchedule.objects.filter(interview_date=today).count()

        data = {
            "open_positions": open_positions,
            "applicants_today": applicants_today,
            "hires_today": hires_today,
            "interviews_today": interviews_today,
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
                            {"label": "Experienced", "count": 45, "percentage": 75.0},
                            {"label": "Inexperienced", "count": 15, "percentage": 25.0}
                        ],
                        "branch_breakdown": [
                            {"branch_name": "Hanoi Branch", "count": 35, "percentage": 58.3}
                        ],
                        "cost_breakdown": [
                            {"source_type": "marketing_channel", "total_cost": "250000.00", "percentage": 50.0}
                        ],
                        "source_type_breakdown": [
                            {"source_type": "marketing_channel", "count": 25, "percentage": 41.7}
                        ],
                        "monthly_trends": [
                            {
                                "month": "10/2025",
                                "referral_source": 10,
                                "marketing_channel": 25,
                                "job_website_channel": 20,
                                "recruitment_department_source": 3,
                                "returning_employee": 2
                            }
                        ]
                    },
                    "error": None
                },
                response_only=True,
            ),
        ],
    )
    @action(detail=False, methods=["get"])
    def charts(self, request):
        """Get aggregated chart data for dashboard."""
        # Get date range
        filter_serializer = DashboardChartFilterSerializer(data=request.query_params)
        if filter_serializer.is_valid():
            from_date = filter_serializer.validated_data.get("from_date")
            to_date = filter_serializer.validated_data.get("to_date")
        else:
            from_date = to_date = None

        if not from_date and not to_date:
            from_date, to_date = get_current_month_range()
            monthly_chart_from_date, monthly_chart_to_date = get_last_6_months_range()
        else:
            monthly_chart_from_date = from_date
            monthly_chart_to_date = to_date

        # Get experience breakdown
        experience_data = HiredCandidateReport.objects.filter(
            report_date__range=[from_date, to_date]
        ).aggregate(
            total_hired=Sum("num_candidates_hired"),
            total_experienced=Sum(Coalesce("num_experienced", 0)),
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

        # Get branch breakdown
        hire_by_branch_data = (
            HiredCandidateReport.objects.filter(report_date__range=[from_date, to_date])
            .values("branch", "branch__name")
            .annotate(total=Sum("num_candidates_hired"))
            .order_by("-total")
        )

        total_by_branch = sum(item["total"] for item in hire_by_branch_data if item["total"])

        branch_breakdown = [
            {
                "branch_name": item["branch__name"],
                "count": item["total"],
                "percentage": round((item["total"] / total_by_branch * 100) if total_by_branch > 0 else 0, 1),
            }
            for item in hire_by_branch_data
            if item["total"]
        ]

        # Get cost breakdown
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

        cost_breakdown = [
            {
                "source_type": item["source_type"],
                "total_cost": float(item["total_cost"]) if item["total_cost"] else 0,
                "percentage": round(
                    (float(item["total_cost"]) / float(total_cost_all) * 100) if total_cost_all > 0 else 0, 1
                ),
            }
            for item in cost_by_category
        ]

        # Get source type breakdown
        source_type_breakdown_data = (
            RecruitmentCostReport.objects.filter(report_date__range=[from_date, to_date])
            .values("source_type")
            .annotate(count=Sum("num_hires"))
            .order_by("source_type")
        )

        total_hired_sources = sum(item["count"] for item in source_type_breakdown_data if item["count"])

        source_type_breakdown = [
            {
                "source_type": item["source_type"],
                "count": item["count"] if item["count"] else 0,
                "percentage": round((item["count"] / total_hired_sources * 100) if total_hired_sources > 0 else 0, 1),
            }
            for item in source_type_breakdown_data
            if item["count"]
        ]

        # Get monthly trends
        monthly_data = (
            RecruitmentCostReport.objects.filter(report_date__range=[monthly_chart_from_date, monthly_chart_to_date])
            .values("month_key", "source_type")
            .annotate(total=Sum("num_hires"))
            .order_by("month_key")
        )

        months = {}
        for item in monthly_data:
            month = item["month_key"]
            category = item["source_type"]
            value = item["total"] or 0

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
            "branch_breakdown": branch_breakdown,
            "cost_breakdown": cost_breakdown,
            "source_type_breakdown": source_type_breakdown,
            "monthly_trends": monthly_trends,
        }

        serializer = DashboardChartDataSerializer(data)
        return Response(serializer.data)
