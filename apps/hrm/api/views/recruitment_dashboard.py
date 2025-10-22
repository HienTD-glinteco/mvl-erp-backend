from datetime import date
from decimal import Decimal

from django.db import models as django_models
from django.db.models import Avg, Count, F, Sum
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.hrm.api.serializers.recruitment_dashboard import (
    DashboardChartDataSerializer,
    DashboardRealtimeDataSerializer,
)
from apps.hrm.models import (
    RecruitmentCandidate,
    RecruitmentCostReport,
    RecruitmentExpense,
    RecruitmentRequest,
)


@extend_schema(
    summary="Get recruitment dashboard realtime data",
    description="Retrieve real-time KPI data for the recruitment dashboard including open positions, "
    "today's applicants, hires, and scheduled interviews.",
    tags=["Recruitment Dashboard"],
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
@api_view(["GET"])
def dashboard_realtime_data(request):
    """Get realtime KPI data for recruitment dashboard.
    
    Returns:
        - open_positions: Number of recruitment requests with status OPEN
        - applicants_today: Number of candidates submitted today
        - hires_today: Number of candidates hired today (status changed to HIRED)
        - interviews_today: Number of candidates with interviews scheduled for today
    """
    today = date.today()

    # Count open recruitment positions
    open_positions = RecruitmentRequest.objects.filter(status=RecruitmentRequest.Status.OPEN).count()

    # Count applicants submitted today
    applicants_today = RecruitmentCandidate.objects.filter(submitted_date=today).count()

    # Count hires today (candidates with status HIRED updated today)
    hires_today = RecruitmentCandidate.objects.filter(
        status=RecruitmentCandidate.Status.HIRED, updated_at__date=today
    ).count()

    # Count interviews scheduled for today
    interviews_today = RecruitmentCandidate.objects.filter(
        status__in=[
            RecruitmentCandidate.Status.INTERVIEW_SCHEDULED_1,
            RecruitmentCandidate.Status.INTERVIEW_SCHEDULED_2,
        ]
    ).count()

    data = {
        "open_positions": open_positions,
        "applicants_today": applicants_today,
        "hires_today": hires_today,
        "interviews_today": interviews_today,
    }

    serializer = DashboardRealtimeDataSerializer(data)
    return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(
    summary="Get recruitment dashboard chart data",
    description="Retrieve comprehensive chart data for the recruitment dashboard including breakdowns by "
    "experience level, source, channel, branch, cost, and hire ratios.",
    tags=["Recruitment Dashboard"],
    responses={200: DashboardChartDataSerializer},
    examples=[
        OpenApiExample(
            "Success",
            value={
                "success": True,
                "data": {
                    "experience_breakdown": [
                        {"experience_range": "0-1 years", "count": 45},
                        {"experience_range": "1-3 years", "count": 78},
                        {"experience_range": "3-5 years", "count": 52},
                        {"experience_range": "5+ years", "count": 35},
                    ],
                    "source_breakdown": [
                        {"source_name": "LinkedIn", "count": 85},
                        {"source_name": "Employee Referral", "count": 62},
                        {"source_name": "Job Portal", "count": 53},
                    ],
                    "channel_breakdown": [
                        {"channel_name": "Job Website", "count": 95},
                        {"channel_name": "Social Media", "count": 68},
                        {"channel_name": "Direct Application", "count": 47},
                    ],
                    "branch_breakdown": [
                        {"branch_name": "Hanoi Branch", "count": 120},
                        {"branch_name": "Ho Chi Minh Branch", "count": 90},
                    ],
                    "cost_breakdown": [
                        {"source_or_channel_name": "LinkedIn", "total_cost": "50000.00", "avg_cost_per_hire": "5000.00"},
                        {"source_or_channel_name": "Job Portal", "total_cost": "30000.00", "avg_cost_per_hire": "3000.00"},
                    ],
                    "hire_ratio": {"total_applicants": 500, "total_hires": 210, "hire_ratio": 0.42},
                },
            },
            response_only=True,
        )
    ],
)
@api_view(["GET"])
def dashboard_chart_data(request):
    """Get chart data for recruitment dashboard.
    
    Returns comprehensive breakdown data including:
    - Experience level breakdown
    - Source breakdown
    - Channel breakdown
    - Branch breakdown
    - Cost breakdown
    - Hire ratio statistics
    """

    # Experience breakdown - categorize by years of experience
    def get_experience_range(years):
        if years is None:
            return "Not specified"
        if years < 1:
            return "0-1 years"
        elif years < 3:
            return "1-3 years"
        elif years < 5:
            return "3-5 years"
        else:
            return "5+ years"

    candidates = RecruitmentCandidate.objects.all()
    experience_data = {}
    for candidate in candidates:
        exp_range = get_experience_range(candidate.years_of_experience)
        experience_data[exp_range] = experience_data.get(exp_range, 0) + 1

    experience_breakdown = [{"experience_range": k, "count": v} for k, v in experience_data.items()]

    # Source breakdown
    source_breakdown_qs = (
        RecruitmentCandidate.objects.values(source_name=F("recruitment_source__name"))
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    source_breakdown = list(source_breakdown_qs)

    # Channel breakdown
    channel_breakdown_qs = (
        RecruitmentCandidate.objects.values(channel_name=F("recruitment_channel__name"))
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    channel_breakdown = list(channel_breakdown_qs)

    # Branch breakdown - based on hired candidates
    branch_breakdown_qs = (
        RecruitmentCandidate.objects.filter(status=RecruitmentCandidate.Status.HIRED)
        .values(branch_name=F("branch__name"))
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    branch_breakdown = list(branch_breakdown_qs)

    # Cost breakdown - aggregate from recruitment expenses
    cost_breakdown_data = []

    # By source
    source_costs = (
        RecruitmentExpense.objects.values(source_or_channel_name=F("recruitment_source__name"))
        .annotate(total_cost=Sum("total_cost"), num_hires=Sum("num_candidates_hired"))
        .order_by("-total_cost")
    )
    for item in source_costs:
        avg_cost = (
            Decimal(item["total_cost"]) / Decimal(item["num_hires"]) if item["num_hires"] > 0 else Decimal("0.00")
        )
        cost_breakdown_data.append(
            {
                "source_or_channel_name": item["source_or_channel_name"],
                "total_cost": str(item["total_cost"]),
                "avg_cost_per_hire": str(avg_cost.quantize(Decimal("0.01"))),
            }
        )

    # By channel
    channel_costs = (
        RecruitmentExpense.objects.values(source_or_channel_name=F("recruitment_channel__name"))
        .annotate(total_cost=Sum("total_cost"), num_hires=Sum("num_candidates_hired"))
        .order_by("-total_cost")
    )
    for item in channel_costs:
        avg_cost = (
            Decimal(item["total_cost"]) / Decimal(item["num_hires"]) if item["num_hires"] > 0 else Decimal("0.00")
        )
        cost_breakdown_data.append(
            {
                "source_or_channel_name": item["source_or_channel_name"],
                "total_cost": str(item["total_cost"]),
                "avg_cost_per_hire": str(avg_cost.quantize(Decimal("0.01"))),
            }
        )

    # Hire ratio
    total_applicants = RecruitmentCandidate.objects.count()
    total_hires = RecruitmentCandidate.objects.filter(status=RecruitmentCandidate.Status.HIRED).count()
    hire_ratio = total_hires / total_applicants if total_applicants > 0 else 0.0

    data = {
        "experience_breakdown": experience_breakdown,
        "source_breakdown": source_breakdown,
        "channel_breakdown": channel_breakdown,
        "branch_breakdown": branch_breakdown,
        "cost_breakdown": cost_breakdown_data,
        "hire_ratio": {
            "total_applicants": total_applicants,
            "total_hires": total_hires,
            "hire_ratio": round(hire_ratio, 2),
        },
    }

    serializer = DashboardChartDataSerializer(data)
    return Response(serializer.data, status=status.HTTP_200_OK)
