from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

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
    RecruitmentChannelReportAggregatedSerializer,
    RecruitmentCostReportAggregatedSerializer,
    RecruitmentSourceReportAggregatedSerializer,
    StaffGrowthReportAggregatedSerializer,
)


class RecruitmentReportsViewSet(viewsets.GenericViewSet):
    """ViewSet for recruitment reports with aggregated data.

    All reports aggregate daily flat model data by week/month periods.
    No pagination except for referral cost report.
    Default period: current month if no date range specified.
    """

    @extend_schema(
        summary="Staff Growth Report",
        description="Aggregate staff changes (introductions, returns, new hires, transfers, resignations) by period.",
        parameters=[
            OpenApiParameter("period", str, description="Period type: 'week' or 'month' (default: month)"),
            OpenApiParameter(
                "from_date", str, description="Start date (YYYY-MM-DD). Default: first day of current month/week"
            ),
            OpenApiParameter(
                "to_date", str, description="End date (YYYY-MM-DD). Default: last day of current month/week"
            ),
            OpenApiParameter("branch", int, description="Filter by branch ID"),
            OpenApiParameter("block", int, description="Filter by block ID"),
            OpenApiParameter("department", int, description="Filter by department ID"),
        ],
        responses={200: StaffGrowthReportAggregatedSerializer(many=True)},
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": [
                        {
                            "period_type": "month",
                            "start_date": "2025-10-01",
                            "end_date": "2025-10-31",
                            "branch": 1,
                            "branch_name": "Hanoi Branch",
                            "block": None,
                            "block_name": None,
                            "department": None,
                            "department_name": None,
                            "num_introductions": 15,
                            "num_returns": 3,
                            "num_new_hires": 10,
                            "num_transfers": 5,
                            "num_resignations": 2,
                        }
                    ],
                },
                response_only=True,
            )
        ],
    )
    @action(detail=False, methods=["get"], url_path="staff-growth")
    def staff_growth(self, request):
        """Aggregate staff growth data by period."""
        period_type, start_date, end_date = self._get_period_params(request)

        queryset = StaffGrowthReport.objects.filter(report_date__range=[start_date, end_date])
        queryset = self._apply_org_filters(queryset, request)

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
                "start_date": start_date,
                "end_date": end_date,
                "branch": item["branch"],
                "branch_name": item["branch__name"],
                "block": item["block"],
                "block_name": item["block__name"],
                "department": item["department"],
                "department_name": item["department__name"],
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
        description="Aggregate hire statistics by recruitment source in nested format (sources as columns, org units as rows).",
        parameters=[
            OpenApiParameter("period", str, description="Period type: 'week' or 'month' (default: month)"),
            OpenApiParameter("from_date", str, description="Start date (YYYY-MM-DD)"),
            OpenApiParameter("to_date", str, description="End date (YYYY-MM-DD)"),
            OpenApiParameter("branch", int, description="Filter by branch ID"),
            OpenApiParameter("block", int, description="Filter by block ID"),
            OpenApiParameter("department", int, description="Filter by department ID"),
        ],
        responses={200: RecruitmentSourceReportAggregatedSerializer},
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "period_type": "month",
                        "start_date": "2025-10-01",
                        "end_date": "2025-10-31",
                        "sources": [
                            {"id": 1, "name": "Employee Referral"},
                            {"id": 2, "name": "LinkedIn"},
                        ],
                        "data": [
                            {
                                "org_unit_type": "branch",
                                "org_unit_id": 1,
                                "org_unit_name": "Hanoi Branch",
                                "hires": [8, 12],
                                "children": [
                                    {
                                        "org_unit_type": "block",
                                        "org_unit_id": 1,
                                        "org_unit_name": "Block A",
                                        "hires": [5, 7],
                                        "children": [],
                                    }
                                ],
                            }
                        ],
                    },
                },
                response_only=True,
            )
        ],
    )
    @action(detail=False, methods=["get"], url_path="recruitment-source")
    def recruitment_source(self, request):
        """Aggregate recruitment source data in nested format."""
        period_type, start_date, end_date = self._get_period_params(request)

        queryset = RecruitmentSourceReport.objects.filter(report_date__range=[start_date, end_date])
        queryset = self._apply_org_filters(queryset, request)
        queryset = queryset.select_related("recruitment_source", "branch", "block", "department")

        # Get unique sources
        sources = (
            queryset.values("recruitment_source", "recruitment_source__name").distinct().order_by("recruitment_source")
        )
        sources_list = [{"id": s["recruitment_source"], "name": s["recruitment_source__name"]} for s in sources]

        # Build nested structure
        data = self._build_nested_org_structure(queryset, sources_list, "num_hires")

        result = {
            "period_type": period_type,
            "start_date": start_date,
            "end_date": end_date,
            "sources": sources_list,
            "data": data,
        }

        serializer = RecruitmentSourceReportAggregatedSerializer(result)
        return Response(serializer.data)

    @extend_schema(
        summary="Recruitment Channel Report",
        description="Aggregate hire statistics by recruitment channel in nested format (channels as columns, org units as rows).",
        parameters=[
            OpenApiParameter("period", str, description="Period type: 'week' or 'month' (default: month)"),
            OpenApiParameter("from_date", str, description="Start date (YYYY-MM-DD)"),
            OpenApiParameter("to_date", str, description="End date (YYYY-MM-DD)"),
            OpenApiParameter("branch", int, description="Filter by branch ID"),
            OpenApiParameter("block", int, description="Filter by block ID"),
            OpenApiParameter("department", int, description="Filter by department ID"),
        ],
        responses={200: RecruitmentChannelReportAggregatedSerializer},
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "period_type": "month",
                        "start_date": "2025-10-01",
                        "end_date": "2025-10-31",
                        "channels": [
                            {"id": 1, "name": "Facebook Ads"},
                            {"id": 2, "name": "JobStreet"},
                        ],
                        "data": [
                            {
                                "org_unit_type": "branch",
                                "org_unit_id": 1,
                                "org_unit_name": "Hanoi Branch",
                                "hires": [15, 20],
                                "children": [],
                            }
                        ],
                    },
                },
                response_only=True,
            )
        ],
    )
    @action(detail=False, methods=["get"], url_path="recruitment-channel")
    def recruitment_channel(self, request):
        """Aggregate recruitment channel data in nested format."""
        period_type, start_date, end_date = self._get_period_params(request)

        queryset = RecruitmentChannelReport.objects.filter(report_date__range=[start_date, end_date])
        queryset = self._apply_org_filters(queryset, request)
        queryset = queryset.select_related("recruitment_channel", "branch", "block", "department")

        # Get unique channels
        channels = (
            queryset.values("recruitment_channel", "recruitment_channel__name")
            .distinct()
            .order_by("recruitment_channel")
        )
        channels_list = [{"id": c["recruitment_channel"], "name": c["recruitment_channel__name"]} for c in channels]

        # Build nested structure
        data = self._build_nested_org_structure(queryset, channels_list, "num_hires")

        result = {
            "period_type": period_type,
            "start_date": start_date,
            "end_date": end_date,
            "channels": channels_list,
            "data": data,
        }

        serializer = RecruitmentChannelReportAggregatedSerializer(result)
        return Response(serializer.data)

    @extend_schema(
        summary="Recruitment Cost Report",
        description="Aggregate recruitment cost data by category (referral, marketing, job boards, etc.).",
        parameters=[
            OpenApiParameter("period", str, description="Period type: 'week' or 'month' (default: month)"),
            OpenApiParameter("from_date", str, description="Start date (YYYY-MM-DD)"),
            OpenApiParameter("to_date", str, description="End date (YYYY-MM-DD)"),
            OpenApiParameter("branch", int, description="Filter by branch ID"),
            OpenApiParameter("block", int, description="Filter by block ID"),
            OpenApiParameter("department", int, description="Filter by department ID"),
            OpenApiParameter(
                "category", str, description="Filter by category (referral_source, marketing_channel, etc.)"
            ),
        ],
        responses={200: RecruitmentCostReportAggregatedSerializer(many=True)},
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": [
                        {
                            "period_type": "month",
                            "start_date": "2025-10-01",
                            "end_date": "2025-10-31",
                            "branch": 1,
                            "branch_name": "Hanoi Branch",
                            "block": None,
                            "block_name": None,
                            "department": None,
                            "department_name": None,
                            "category": "marketing_channel",
                            "category_display": "Marketing Channel",
                            "total_cost": "15000000.00",
                            "num_hired": 25,
                            "avg_cost_per_hire": "600000.00",
                        }
                    ],
                },
                response_only=True,
            )
        ],
    )
    @action(detail=False, methods=["get"], url_path="recruitment-cost")
    def recruitment_cost(self, request):
        """Aggregate recruitment cost data by period."""
        period_type, start_date, end_date = self._get_period_params(request)

        queryset = RecruitmentCostReport.objects.filter(report_date__range=[start_date, end_date])
        queryset = self._apply_org_filters(queryset, request)

        category = request.query_params.get("category")
        if category:
            queryset = queryset.filter(source_type=category)

        aggregated = (
            queryset.values(
                "branch",
                "branch__name",
                "block",
                "block__name",
                "department",
                "department__name",
                "source_type",
            )
            .annotate(
                total_cost=Sum("total_cost"),
                num_hired=Sum("num_hires"),
            )
            .order_by("branch", "block", "department", "source_type")
        )

        results = []
        for item in aggregated:
            avg_cost = Decimal("0")
            if item["num_hired"] and item["num_hired"] > 0:
                avg_cost = item["total_cost"] / item["num_hired"]

            results.append(
                {
                    "period_type": period_type,
                    "start_date": start_date,
                    "end_date": end_date,
                    "branch": item["branch"],
                    "branch_name": item["branch__name"],
                    "block": item["block"],
                    "block_name": item["block__name"],
                    "department": item["department"],
                    "department_name": item["department__name"],
                    "category": item["source_type"],
                    "category_display": dict(RecruitmentCostReport.SourceType.choices).get(
                        item["source_type"], item["source_type"]
                    ),
                    "total_cost": item["total_cost"] or Decimal("0"),
                    "num_hired": item["num_hired"] or 0,
                    "avg_cost_per_hire": avg_cost,
                }
            )

        serializer = RecruitmentCostReportAggregatedSerializer(results, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Hired Candidate Report",
        description="Aggregate hired candidate statistics by source type with experience breakdown.",
        parameters=[
            OpenApiParameter("period", str, description="Period type: 'week' or 'month' (default: month)"),
            OpenApiParameter("from_date", str, description="Start date (YYYY-MM-DD)"),
            OpenApiParameter("to_date", str, description="End date (YYYY-MM-DD)"),
            OpenApiParameter("branch", int, description="Filter by branch ID"),
            OpenApiParameter("block", int, description="Filter by block ID"),
            OpenApiParameter("department", int, description="Filter by department ID"),
            OpenApiParameter("source_type", str, description="Filter by source type"),
        ],
        responses={200: HiredCandidateReportAggregatedSerializer(many=True)},
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": [
                        {
                            "period_type": "month",
                            "start_date": "2025-10-01",
                            "end_date": "2025-10-31",
                            "branch": 1,
                            "branch_name": "Hanoi Branch",
                            "block": None,
                            "block_name": None,
                            "department": None,
                            "department_name": None,
                            "source_type": "referral_source",
                            "source_type_display": "Referral Source",
                            "num_candidates_hired": 15,
                            "num_experienced": 10,
                            "num_no_experience": 5,
                            "children": [
                                {
                                    "employee_code": "EMP001",
                                    "employee_name": "Nguyen Van A",
                                    "num_candidates_hired": 3,
                                }
                            ],
                        }
                    ],
                },
                response_only=True,
            )
        ],
    )
    @action(detail=False, methods=["get"], url_path="hired-candidate")
    def hired_candidate(self, request):
        """Aggregate hired candidate data by period with conditional employee details."""
        period_type, start_date, end_date = self._get_period_params(request)

        queryset = HiredCandidateReport.objects.filter(report_date__range=[start_date, end_date])
        queryset = self._apply_org_filters(queryset, request)

        source_type_param = request.query_params.get("source_type")
        if source_type_param:
            queryset = queryset.filter(source_type=source_type_param)

        # Aggregate by org unit and source type
        aggregated = (
            queryset.values(
                "branch",
                "branch__name",
                "block",
                "block__name",
                "department",
                "department__name",
                "source_type",
            )
            .annotate(
                num_candidates_hired=Sum("num_candidates_hired"),
                num_experienced=Sum("num_experienced"),
            )
            .order_by("branch", "block", "department", "source_type")
        )

        results = []
        for item in aggregated:
            num_no_experience = (item["num_candidates_hired"] or 0) - (item["num_experienced"] or 0)

            result_item = {
                "period_type": period_type,
                "start_date": start_date,
                "end_date": end_date,
                "branch": item["branch"],
                "branch_name": item["branch__name"],
                "block": item["block"],
                "block_name": item["block__name"],
                "department": item["department"],
                "department_name": item["department__name"],
                "source_type": item["source_type"],
                "source_type_display": dict(HiredCandidateReport.SourceType.choices).get(
                    item["source_type"], item["source_type"]
                ),
                "num_candidates_hired": item["num_candidates_hired"] or 0,
                "num_experienced": item["num_experienced"] or 0,
                "num_no_experience": num_no_experience,
            }

            # Add children only for referral_source type
            if item["source_type"] == "referral_source":
                children_qs = queryset.filter(
                    branch=item["branch"],
                    block=item["block"],
                    department=item["department"],
                    source_type="referral_source",
                    employee__isnull=False,
                )
                children_agg = (
                    children_qs.values("employee", "employee__code", "employee__fullname")
                    .annotate(num_candidates_hired=Sum("num_candidates_hired"))
                    .order_by("employee")
                )

                result_item["children"] = [
                    {
                        "employee_code": child["employee__code"],
                        "employee_name": child["employee__fullname"],
                        "num_candidates_hired": child["num_candidates_hired"] or 0,
                    }
                    for child in children_agg
                ]

            results.append(result_item)

        serializer = HiredCandidateReportAggregatedSerializer(results, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Referral Cost Report",
        description="Referral cost report with summary and detail breakdown by department and employee. Queries RecruitmentExpense directly.",
        parameters=[
            OpenApiParameter("month", str, description="Month in YYYY-MM format (default: current month)"),
        ],
        responses={200: ReferralCostSummarySerializer(many=True)},  # TODO: change to correct serializer
        examples=[
            OpenApiExample(  # TODO: update the example
                "Success",
                value={
                    "success": True,
                    "data": [
                        {
                            "month": "2025-10",
                            "department_name": "IT Department",
                            "total_referrals": 15,
                            "total_cost": "30000000.00",
                            "details": [
                                {
                                    "month": "2025-10",
                                    "department_name": "IT Department",
                                    "employee_code": "EMP001",
                                    "employee_name": "Nguyen Van A",
                                    "num_referrals": 5,
                                    "total_cost": "10000000.00",
                                }
                            ],
                        }
                    ],
                },
                response_only=True,
            )
        ],
    )
    @action(detail=False, methods=["get"], url_path="referral-cost")
    def referral_cost(self, request):
        """Generate referral cost report from RecruitmentExpense."""
        month_param = request.query_params.get("month")
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

        month_key = start_date.strftime("%Y-%m")

        # Query RecruitmentExpense for referral expenses
        expenses = RecruitmentExpense.objects.filter(
            expense_date__range=[start_date, end_date],
            recruitment_source__allow_referral=True,  # Only referral sources
        ).select_related("employee", "employee__department", "recruitment_source")

        # Group by department
        departments = {}
        for expense in expenses:
            dept_name = (
                expense.employee.department.name
                if expense.employee and expense.employee.department
                else _("No Department")
            )
            emp_code = expense.employee.code if expense.employee else _("No Employee")
            emp_name = expense.employee.fullname if expense.employee else _("No Employee")

            if dept_name not in departments:
                departments[dept_name] = {
                    "month": month_key,
                    "department_name": dept_name,
                    "total_referrals": 0,
                    "total_cost": Decimal("0"),
                    "details": {},
                }

            emp_key = (emp_code, emp_name)
            if emp_key not in departments[dept_name]["details"]:
                departments[dept_name]["details"][emp_key] = {
                    "month": month_key,
                    "department_name": dept_name,
                    "employee_code": emp_code,
                    "employee_name": emp_name,
                    "num_referrals": 0,
                    "total_cost": Decimal("0"),
                }

            departments[dept_name]["total_referrals"] += 1
            departments[dept_name]["total_cost"] += expense.amount
            departments[dept_name]["details"][emp_key]["num_referrals"] += 1
            departments[dept_name]["details"][emp_key]["total_cost"] += expense.amount

        # Convert to list format
        results = []
        for dept_data in departments.values():
            dept_data["details"] = list(dept_data["details"].values())
            results.append(dept_data)

        serializer = ReferralCostSummarySerializer(
            results, many=True
        )  # TODO: update logic prepare report data, then change this serializer to ReferralCostReportAggregatedSerializer
        return Response(serializer.data)

    def _get_period_params(self, request):
        """Extract and validate period parameters from request."""
        period = request.query_params.get("period", "month")
        from_date = request.query_params.get("from_date")
        to_date = request.query_params.get("to_date")

        if from_date and to_date:
            try:
                start_date = datetime.strptime(from_date, "%Y-%m-%d").date()
                end_date = datetime.strptime(to_date, "%Y-%m-%d").date()
            except ValueError:
                if period == "week":
                    start_date, end_date = get_current_week_range()
                else:
                    start_date, end_date = get_current_month_range()
        else:
            if period == "week":
                start_date, end_date = get_current_week_range()
            else:
                start_date, end_date = get_current_month_range()

        return period, start_date, end_date

    def _apply_org_filters(self, queryset, request):
        """Apply organizational unit filters to queryset."""
        branch = request.query_params.get("branch")
        if branch:
            queryset = queryset.filter(branch_id=branch)

        block = request.query_params.get("block")
        if block:
            queryset = queryset.filter(block_id=block)

        department = request.query_params.get("department")
        if department:
            queryset = queryset.filter(department_id=department)

        return queryset

    def _build_nested_org_structure(self, queryset, sources_or_channels, value_field):
        """Build nested organizational structure for source/channel reports."""
        # This is a simplified implementation - in production, you'd want to
        # properly handle the full branch > block > department hierarchy

        # Get all branches
        branches = queryset.values("branch", "branch__name").distinct().order_by("branch")

        data = []
        for branch in branches:
            if branch["branch"] is None:
                continue

            branch_data = {
                "org_unit_type": "branch",
                "org_unit_id": branch["branch"],
                "org_unit_name": branch["branch__name"],
                "hires": [],
                "children": [],
            }

            # Calculate hires for each source/channel in this branch
            for item in sources_or_channels:
                item_id = item["id"]
                source_field = (
                    "recruitment_source"
                    if "recruitment_source" in queryset.model._meta.get_fields()
                    else "recruitment_channel"
                )

                total = (
                    queryset.filter(branch=branch["branch"], **{source_field: item_id}).aggregate(
                        total=Sum(value_field)
                    )["total"]
                    or 0
                )

                branch_data["hires"].append(total)

            data.append(branch_data)

        return data
