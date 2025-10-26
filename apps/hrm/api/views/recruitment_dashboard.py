from datetime import datetime

from django.db.models import Sum
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
                "Success - Realtime KPIs",
                value={
                    "success": True,
                    "data": {
                        "open_positions": 15,
                        "applicants_today": 8,
                        "hires_today": 3,
                        "interviews_today": 5,
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
                        "source_type_breakdown": [
                            {"source_type": "referral_source", "count": 25, "percentage": 33.3},
                            {"source_type": "marketing_channel", "count": 30, "percentage": 40.0},
                            {"source_type": "job_website_channel", "count": 20, "percentage": 26.7},
                        ],
                        "monthly_trends": [
                            {
                                "month": "09/2025",
                                "referral_source": 8,
                                "marketing_channel": 10,
                                "job_website_channel": 7,
                                "recruitment_department_source": 5,
                                "returning_employee": 2,
                            },
                            {
                                "month": "10/2025",
                                "referral_source": 10,
                                "marketing_channel": 12,
                                "job_website_channel": 8,
                                "recruitment_department_source": 6,
                                "returning_employee": 3,
                            },
                        ],
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
        cost_breakdown = self._get_cost_breakdown(from_date, to_date)
        source_type_breakdown = self._get_source_type_breakdown(from_date, to_date)
        monthly_trends = self._get_monthly_trends(monthly_chart_from_date, monthly_chart_to_date)

        data = {
            "experience_breakdown": experience_breakdown,
            "branch_breakdown": branch_breakdown,
            "cost_breakdown": cost_breakdown,
            "source_type_breakdown": source_type_breakdown,
            "monthly_trends": monthly_trends,
        }

        serializer = DashboardChartDataSerializer(data)
        return Response(serializer.data)

    def _get_hires_today(self, today):
        """Get number of hires today from HiredCandidateReport."""
        return (
            HiredCandidateReport.objects.filter(report_date=today)
            .aggregate(total=Sum("num_candidates_hired"))["total"]
            or 0
        )

    def _get_open_positions(self):
        """Get number of open positions."""
        return JobDescription.objects.filter(status="open").count()

    def _get_applicants_today(self, today):
        """Get number of applicants today."""
        return RecruitmentCandidate.objects.filter(created_at__date=today).count()

    def _get_interviews_today(self, today):
        """Get number of interviews today."""
        return InterviewSchedule.objects.filter(interview_date=today).count()

    def _get_experience_breakdown(self, from_date, to_date):
        """Get experience breakdown from HiredCandidateReport."""
        experience_data = HiredCandidateReport.objects.filter(
            report_date__range=[from_date, to_date]
        ).aggregate(
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

    def _get_cost_breakdown(self, from_date, to_date):
        """Get cost breakdown from RecruitmentCostReport."""
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

        return [
            {
                "source_type": item["source_type"],
                "total_cost": float(item["total_cost"]) if item["total_cost"] else 0,
                "percentage": round(
                    (float(item["total_cost"]) / float(total_cost_all) * 100) if total_cost_all > 0 else 0, 1
                ),
            }
            for item in cost_by_category
        ]

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

        return list(months.values())

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
