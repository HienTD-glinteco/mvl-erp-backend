from datetime import datetime

from django.db.models import Count, F, Q, Sum
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.hrm.models import HiredCandidateReport, RecruitmentCostReport
from apps.hrm.utils import get_current_month_range, get_experience_category

from ..serializers.recruitment_dashboard import ChartDataSerializer, RealtimeDataSerializer


class RecruitmentDashboardViewSet(viewsets.ViewSet):
    """ViewSet for recruitment dashboard metrics.
    
    Provides real-time KPIs and chart data for recruitment analytics.
    All data sourced from flat report models for performance.
    """

    @extend_schema(
        summary="Realtime Dashboard KPIs",
        description="Get real-time recruitment KPIs: open positions, applicants today, hires today, interviews today.",
        parameters=[
            OpenApiParameter("from_date", str, description="Start date (YYYY-MM-DD). Default: first day of current month"),
            OpenApiParameter("to_date", str, description="End date (YYYY-MM-DD). Default: last day of current month"),
        ],
        responses={200: RealtimeDataSerializer},
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
        start_date, end_date = self._get_date_range(request)

        # Get today's hires from HiredCandidateReport
        today = datetime.now().date()
        hires_today = (
            HiredCandidateReport.objects.filter(report_date=today)
            .aggregate(total=Sum("num_candidates_hired"))["total"]
            or 0
        )

        # Get applicants and interviews from recruitment request/candidate models
        # TODO: Implement these metrics from appropriate flat models when available
        # For now, returning placeholders
        
        data = {
            "open_positions": 0,  # TODO: Implement from JobDescription or similar
            "applicants_today": 0,  # TODO: Implement from candidate applications
            "hires_today": hires_today,
            "interviews_today": 0,  # TODO: Implement from interview schedules
        }

        serializer = RealtimeDataSerializer(data)
        return Response(serializer.data)

    @extend_schema(
        summary="Dashboard Chart Data",
        description="Get aggregated data for dashboard charts: experience breakdown, source/channel distribution, branch breakdown, cost analysis, and monthly trends.",
        parameters=[
            OpenApiParameter("from_date", str, description="Start date (YYYY-MM-DD). Default: first day of current month"),
            OpenApiParameter("to_date", str, description="End date (YYYY-MM-DD). Default: last day of current month"),
        ],
        responses={200: ChartDataSerializer},
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "experience_breakdown": [
                            {"label": "0-1 years", "value": 25, "percentage": 30.5},
                            {"label": "1-3 years", "value": 35, "percentage": 42.7},
                        ],
                        "hire_by_source": [
                            {"category": "referral_source", "label": "Referral Source", "value": 30, "percentage": 40.0},
                            {"category": "marketing_channel", "label": "Marketing Channel", "value": 45, "percentage": 60.0},
                        ],
                        "hire_by_channel": [
                            {"category": "marketing_channel", "label": "Marketing Channel", "value": 25, "percentage": 50.0},
                            {"category": "job_website_channel", "label": "Job Website", "value": 25, "percentage": 50.0},
                        ],
                        "hire_by_branch": [
                            {"branch_id": 1, "branch_name": "Hanoi", "value": 50, "percentage": 55.6},
                            {"branch_id": 2, "branch_name": "HCMC", "value": 40, "percentage": 44.4},
                        ],
                        "cost_analysis": [
                            {"category": "job_website_channel", "label": "Job Websites", "value": 50000000, "percentage": 45.5},
                            {"category": "marketing_channel", "label": "Marketing", "value": 40000000, "percentage": 36.4},
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
        start_date, end_date = self._get_date_range(request)

        # 1. Experience breakdown from HiredCandidateReport
        experience_data = HiredCandidateReport.objects.filter(
            report_date__range=[start_date, end_date]
        ).aggregate(
            total_hired=Sum("num_candidates_hired"),
            total_experienced=Sum("num_experienced"),
        )

        total_hired = experience_data["total_hired"] or 0
        total_experienced = experience_data["total_experienced"] or 0
        total_inexperienced = total_hired - total_experienced

        experience_breakdown = [
            {
                "label": _("Experienced"),
                "value": total_experienced,
                "percentage": round((total_experienced / total_hired * 100) if total_hired > 0 else 0, 1),
            },
            {
                "label": _("Inexperienced"),
                "value": total_inexperienced,
                "percentage": round((total_inexperienced / total_hired * 100) if total_hired > 0 else 0, 1),
            },
        ]

        # 2. Hire by source/channel from RecruitmentCostReport
        hire_by_category = (
            RecruitmentCostReport.objects.filter(report_date__range=[start_date, end_date])
            .values("source_type")
            .annotate(total=Sum("num_hires"))
            .order_by("-total")
        )

        total_hires_all = sum(item["total"] for item in hire_by_category)

        hire_by_source = []
        hire_by_channel = []
        
        for item in hire_by_category:
            category = item["source_type"]
            value = item["total"]
            percentage = round((value / total_hires_all * 100) if total_hires_all > 0 else 0, 1)
            
            category_display = dict(RecruitmentCostReport.SourceType.choices).get(category, category)
            
            data_item = {
                "category": category,
                "label": category_display,
                "value": value,
                "percentage": percentage,
            }
            
            # Categorize into source vs channel
            if category in ["referral_source", "recruitment_department_source", "returning_employee"]:
                hire_by_source.append(data_item)
            else:
                hire_by_channel.append(data_item)

        # 3. Hire by branch from HiredCandidateReport
        hire_by_branch_data = (
            HiredCandidateReport.objects.filter(report_date__range=[start_date, end_date])
            .values("branch", "branch__name")
            .annotate(total=Sum("num_candidates_hired"))
            .order_by("-total")
        )

        total_by_branch = sum(item["total"] for item in hire_by_branch_data)

        hire_by_branch = [
            {
                "branch_id": item["branch"],
                "branch_name": item["branch__name"],
                "value": item["total"],
                "percentage": round((item["total"] / total_by_branch * 100) if total_by_branch > 0 else 0, 1),
            }
            for item in hire_by_branch_data
        ]

        # 4. Cost analysis from RecruitmentCostReport
        cost_by_category = (
            RecruitmentCostReport.objects.filter(report_date__range=[start_date, end_date])
            .values("source_type")
            .annotate(total_cost=Sum("total_cost"))
            .order_by("-total_cost")
        )

        total_cost_all = sum(item["total_cost"] for item in cost_by_category if item["total_cost"])

        cost_analysis = [
            {
                "category": item["source_type"],
                "label": dict(RecruitmentCostReport.SourceType.choices).get(item["source_type"], item["source_type"]),
                "value": float(item["total_cost"]) if item["total_cost"] else 0,
                "percentage": round(
                    (float(item["total_cost"]) / float(total_cost_all) * 100) if total_cost_all > 0 else 0, 1
                ),
            }
            for item in cost_by_category
        ]

        # 5. Monthly trends from RecruitmentCostReport
        monthly_data = (
            RecruitmentCostReport.objects.filter(report_date__range=[start_date, end_date])
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
            "hire_by_source": hire_by_source,
            "hire_by_channel": hire_by_channel,
            "hire_by_branch": hire_by_branch,
            "cost_analysis": cost_analysis,
            "monthly_trends": monthly_trends,
        }

        serializer = ChartDataSerializer(data)
        return Response(serializer.data)

    def _get_date_range(self, request):
        """Extract date range from request or use current month as default."""
        from_date = request.query_params.get("from_date")
        to_date = request.query_params.get("to_date")

        if from_date and to_date:
            try:
                start_date = datetime.strptime(from_date, "%Y-%m-%d").date()
                end_date = datetime.strptime(to_date, "%Y-%m-%d").date()
            except ValueError:
                start_date, end_date = get_current_month_range()
        else:
            start_date, end_date = get_current_month_range()

        return start_date, end_date
