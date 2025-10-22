from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets.recruitment_reports import (
    HiredCandidateReportFilterSet,
    RecruitmentChannelReportFilterSet,
    RecruitmentCostReportFilterSet,
    RecruitmentSourceReportFilterSet,
    ReferralCostReportFilterSet,
    StaffGrowthReportFilterSet,
)
from apps.hrm.api.serializers.recruitment_reports import (
    HiredCandidateReportSerializer,
    RecruitmentChannelReportSerializer,
    RecruitmentCostReportSerializer,
    RecruitmentSourceReportSerializer,
    ReferralCostReportSerializer,
    StaffGrowthReportSerializer,
)
from apps.hrm.models import (
    HiredCandidateReport,
    RecruitmentChannelReport,
    RecruitmentCostReport,
    RecruitmentSourceReport,
    ReferralCostReport,
    StaffGrowthReport,
)
from libs import BaseModelViewSet


@extend_schema_view(
    list=extend_schema(
        summary="List staff growth reports",
        description="Retrieve staff growth statistics including introductions, returns, new hires, transfers, and resignations. "
        "Supports filtering by date range, period type, and organizational units.",
        tags=["Recruitment Reports"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "count": 1,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": 1,
                                "report_date": "2025-10-01",
                                "period_type": "monthly",
                                "branch": 1,
                                "branch_name": "Hanoi Branch",
                                "block": 2,
                                "block_name": "Business Block",
                                "department": 3,
                                "department_name": "Sales Department",
                                "num_introductions": 5,
                                "num_returns": 2,
                                "num_new_hires": 10,
                                "num_transfers": 3,
                                "num_resignations": 1,
                                "created_at": "2025-10-15T10:00:00Z",
                                "updated_at": "2025-10-15T10:00:00Z",
                            }
                        ],
                    },
                },
                response_only=True,
            )
        ],
    ),
    retrieve=extend_schema(
        summary="Retrieve a staff growth report",
        description="Get detailed information about a specific staff growth report.",
        tags=["Recruitment Reports"],
    ),
    create=extend_schema(
        summary="Create a staff growth report",
        description="Create a new staff growth report record.",
        tags=["Recruitment Reports"],
    ),
    update=extend_schema(
        summary="Update a staff growth report",
        description="Update an existing staff growth report.",
        tags=["Recruitment Reports"],
    ),
    partial_update=extend_schema(
        summary="Partially update a staff growth report",
        description="Partially update an existing staff growth report.",
        tags=["Recruitment Reports"],
    ),
    destroy=extend_schema(
        summary="Delete a staff growth report",
        description="Delete a staff growth report.",
        tags=["Recruitment Reports"],
    ),
)
class StaffGrowthReportViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for StaffGrowthReport model."""

    queryset = StaffGrowthReport.objects.select_related("branch", "block", "department").all()
    serializer_class = StaffGrowthReportSerializer
    filterset_class = StaffGrowthReportFilterSet
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = ["report_date", "created_at"]
    ordering = ["-report_date"]


@extend_schema_view(
    list=extend_schema(
        summary="List recruitment source reports",
        description="Retrieve nested hire statistics by recruitment source. "
        "Data is organized with sources as columns and organizational units (branch > block > department) as rows.",
        tags=["Recruitment Reports"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "count": 2,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": 1,
                                "report_date": "2025-10-01",
                                "period_type": "monthly",
                                "branch": 1,
                                "branch_name": "Hanoi Branch",
                                "block": None,
                                "block_name": None,
                                "department": None,
                                "department_name": None,
                                "recruitment_source": 1,
                                "source_name": "LinkedIn",
                                "org_unit_name": "Hanoi Branch",
                                "org_unit_type": "branch",
                                "num_hires": 15,
                                "created_at": "2025-10-15T10:00:00Z",
                                "updated_at": "2025-10-15T10:00:00Z",
                            },
                            {
                                "id": 2,
                                "report_date": "2025-10-01",
                                "period_type": "monthly",
                                "branch": 1,
                                "branch_name": "Hanoi Branch",
                                "block": 2,
                                "block_name": "Business Block",
                                "department": None,
                                "department_name": None,
                                "recruitment_source": 1,
                                "source_name": "LinkedIn",
                                "org_unit_name": "Business Block",
                                "org_unit_type": "block",
                                "num_hires": 10,
                                "created_at": "2025-10-15T10:00:00Z",
                                "updated_at": "2025-10-15T10:00:00Z",
                            },
                        ],
                    },
                },
                response_only=True,
            )
        ],
    ),
    retrieve=extend_schema(
        summary="Retrieve a recruitment source report",
        description="Get detailed information about a specific recruitment source report.",
        tags=["Recruitment Reports"],
    ),
    create=extend_schema(
        summary="Create a recruitment source report",
        description="Create a new recruitment source report record.",
        tags=["Recruitment Reports"],
    ),
    update=extend_schema(
        summary="Update a recruitment source report",
        description="Update an existing recruitment source report.",
        tags=["Recruitment Reports"],
    ),
    partial_update=extend_schema(
        summary="Partially update a recruitment source report",
        description="Partially update an existing recruitment source report.",
        tags=["Recruitment Reports"],
    ),
    destroy=extend_schema(
        summary="Delete a recruitment source report",
        description="Delete a recruitment source report.",
        tags=["Recruitment Reports"],
    ),
)
class RecruitmentSourceReportViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for RecruitmentSourceReport model."""

    queryset = RecruitmentSourceReport.objects.select_related(
        "branch", "block", "department", "recruitment_source"
    ).all()
    serializer_class = RecruitmentSourceReportSerializer
    filterset_class = RecruitmentSourceReportFilterSet
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = ["report_date", "created_at"]
    ordering = ["-report_date"]


@extend_schema_view(
    list=extend_schema(
        summary="List recruitment channel reports",
        description="Retrieve nested hire statistics by recruitment channel. "
        "Data is organized with channels as columns and organizational units (branch > block > department) as rows.",
        tags=["Recruitment Reports"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "count": 2,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": 1,
                                "report_date": "2025-10-01",
                                "period_type": "monthly",
                                "branch": 1,
                                "branch_name": "Hanoi Branch",
                                "block": None,
                                "block_name": None,
                                "department": None,
                                "department_name": None,
                                "recruitment_channel": 1,
                                "channel_name": "Job Website",
                                "org_unit_name": "Hanoi Branch",
                                "org_unit_type": "branch",
                                "num_hires": 20,
                                "created_at": "2025-10-15T10:00:00Z",
                                "updated_at": "2025-10-15T10:00:00Z",
                            },
                            {
                                "id": 2,
                                "report_date": "2025-10-01",
                                "period_type": "monthly",
                                "branch": 1,
                                "branch_name": "Hanoi Branch",
                                "block": 2,
                                "block_name": "Business Block",
                                "department": None,
                                "department_name": None,
                                "recruitment_channel": 1,
                                "channel_name": "Job Website",
                                "org_unit_name": "Business Block",
                                "org_unit_type": "block",
                                "num_hires": 15,
                                "created_at": "2025-10-15T10:00:00Z",
                                "updated_at": "2025-10-15T10:00:00Z",
                            },
                        ],
                    },
                },
                response_only=True,
            )
        ],
    ),
    retrieve=extend_schema(
        summary="Retrieve a recruitment channel report",
        description="Get detailed information about a specific recruitment channel report.",
        tags=["Recruitment Reports"],
    ),
    create=extend_schema(
        summary="Create a recruitment channel report",
        description="Create a new recruitment channel report record.",
        tags=["Recruitment Reports"],
    ),
    update=extend_schema(
        summary="Update a recruitment channel report",
        description="Update an existing recruitment channel report.",
        tags=["Recruitment Reports"],
    ),
    partial_update=extend_schema(
        summary="Partially update a recruitment channel report",
        description="Partially update an existing recruitment channel report.",
        tags=["Recruitment Reports"],
    ),
    destroy=extend_schema(
        summary="Delete a recruitment channel report",
        description="Delete a recruitment channel report.",
        tags=["Recruitment Reports"],
    ),
)
class RecruitmentChannelReportViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for RecruitmentChannelReport model."""

    queryset = RecruitmentChannelReport.objects.select_related(
        "branch", "block", "department", "recruitment_channel"
    ).all()
    serializer_class = RecruitmentChannelReportSerializer
    filterset_class = RecruitmentChannelReportFilterSet
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = ["report_date", "created_at"]
    ordering = ["-report_date"]


@extend_schema_view(
    list=extend_schema(
        summary="List recruitment cost reports",
        description="Retrieve flat cost data per source/channel with metrics including total cost, hire count, and average cost per hire.",
        tags=["Recruitment Reports"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "count": 1,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": 1,
                                "report_date": "2025-10-01",
                                "period_type": "monthly",
                                "branch": 1,
                                "branch_name": "Hanoi Branch",
                                "block": None,
                                "block_name": None,
                                "department": None,
                                "department_name": None,
                                "recruitment_source": 1,
                                "source_name": "LinkedIn",
                                "recruitment_channel": None,
                                "channel_name": None,
                                "total_cost": "50000.00",
                                "num_hires": 10,
                                "avg_cost_per_hire": "5000.00",
                                "created_at": "2025-10-15T10:00:00Z",
                                "updated_at": "2025-10-15T10:00:00Z",
                            }
                        ],
                    },
                },
                response_only=True,
            )
        ],
    ),
    retrieve=extend_schema(
        summary="Retrieve a recruitment cost report",
        description="Get detailed information about a specific recruitment cost report.",
        tags=["Recruitment Reports"],
    ),
    create=extend_schema(
        summary="Create a recruitment cost report",
        description="Create a new recruitment cost report record.",
        tags=["Recruitment Reports"],
    ),
    update=extend_schema(
        summary="Update a recruitment cost report",
        description="Update an existing recruitment cost report.",
        tags=["Recruitment Reports"],
    ),
    partial_update=extend_schema(
        summary="Partially update a recruitment cost report",
        description="Partially update an existing recruitment cost report.",
        tags=["Recruitment Reports"],
    ),
    destroy=extend_schema(
        summary="Delete a recruitment cost report",
        description="Delete a recruitment cost report.",
        tags=["Recruitment Reports"],
    ),
)
class RecruitmentCostReportViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for RecruitmentCostReport model."""

    queryset = RecruitmentCostReport.objects.select_related(
        "branch", "block", "department", "recruitment_source", "recruitment_channel"
    ).all()
    serializer_class = RecruitmentCostReportSerializer
    filterset_class = RecruitmentCostReportFilterSet
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = ["report_date", "created_at"]
    ordering = ["-report_date"]


@extend_schema_view(
    list=extend_schema(
        summary="List hired candidate reports",
        description="Retrieve statistics of candidates who accepted offers, separated by source type (introduction, recruitment, return). "
        "For 'introduction' source, employee details are included; for others, only summary statistics.",
        tags=["Recruitment Reports"],
        examples=[
            OpenApiExample(
                "Success - Introduction Source with Employee Details",
                value={
                    "success": True,
                    "data": {
                        "count": 2,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": 1,
                                "report_date": "2025-10-01",
                                "period_type": "monthly",
                                "branch": 1,
                                "branch_name": "Hanoi Branch",
                                "block": 2,
                                "block_name": "Business Block",
                                "department": 3,
                                "department_name": "Sales Department",
                                "source_type": "introduction",
                                "employee": 5,
                                "employee_name": "John Doe",
                                "employee_code": "MV001",
                                "num_candidates_hired": 3,
                                "created_at": "2025-10-15T10:00:00Z",
                                "updated_at": "2025-10-15T10:00:00Z",
                            },
                            {
                                "id": 2,
                                "report_date": "2025-10-01",
                                "period_type": "monthly",
                                "branch": 1,
                                "branch_name": "Hanoi Branch",
                                "block": None,
                                "block_name": None,
                                "department": None,
                                "department_name": None,
                                "source_type": "recruitment",
                                "employee": None,
                                "employee_name": None,
                                "employee_code": None,
                                "num_candidates_hired": 15,
                                "created_at": "2025-10-15T10:00:00Z",
                                "updated_at": "2025-10-15T10:00:00Z",
                            },
                        ],
                    },
                },
                response_only=True,
            )
        ],
    ),
    retrieve=extend_schema(
        summary="Retrieve a hired candidate report",
        description="Get detailed information about a specific hired candidate report.",
        tags=["Recruitment Reports"],
    ),
    create=extend_schema(
        summary="Create a hired candidate report",
        description="Create a new hired candidate report record.",
        tags=["Recruitment Reports"],
    ),
    update=extend_schema(
        summary="Update a hired candidate report",
        description="Update an existing hired candidate report.",
        tags=["Recruitment Reports"],
    ),
    partial_update=extend_schema(
        summary="Partially update a hired candidate report",
        description="Partially update an existing hired candidate report.",
        tags=["Recruitment Reports"],
    ),
    destroy=extend_schema(
        summary="Delete a hired candidate report",
        description="Delete a hired candidate report.",
        tags=["Recruitment Reports"],
    ),
)
class HiredCandidateReportViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for HiredCandidateReport model."""

    queryset = HiredCandidateReport.objects.select_related("branch", "block", "department", "employee").all()
    serializer_class = HiredCandidateReportSerializer
    filterset_class = HiredCandidateReportFilterSet
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = ["report_date", "created_at"]
    ordering = ["-report_date"]


@extend_schema_view(
    list=extend_schema(
        summary="List referral cost reports",
        description="Retrieve referral cost summary and detailed breakdown by department and employee. "
        "Summary records have no employee (employee=null), detail records include employee information.",
        tags=["Recruitment Reports"],
        examples=[
            OpenApiExample(
                "Success - Summary and Detail Records",
                value={
                    "success": True,
                    "data": {
                        "count": 3,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": 1,
                                "report_date": "2025-10-01",
                                "period_type": "monthly",
                                "department": 3,
                                "department_name": "Sales Department",
                                "employee": None,
                                "employee_name": None,
                                "employee_code": None,
                                "total_referral_cost": "15000.00",
                                "num_referrals": 5,
                                "created_at": "2025-10-15T10:00:00Z",
                                "updated_at": "2025-10-15T10:00:00Z",
                            },
                            {
                                "id": 2,
                                "report_date": "2025-10-01",
                                "period_type": "monthly",
                                "department": 3,
                                "department_name": "Sales Department",
                                "employee": 5,
                                "employee_name": "John Doe",
                                "employee_code": "MV001",
                                "total_referral_cost": "9000.00",
                                "num_referrals": 3,
                                "created_at": "2025-10-15T10:00:00Z",
                                "updated_at": "2025-10-15T10:00:00Z",
                            },
                            {
                                "id": 3,
                                "report_date": "2025-10-01",
                                "period_type": "monthly",
                                "department": 3,
                                "department_name": "Sales Department",
                                "employee": 8,
                                "employee_name": "Jane Smith",
                                "employee_code": "MV002",
                                "total_referral_cost": "6000.00",
                                "num_referrals": 2,
                                "created_at": "2025-10-15T10:00:00Z",
                                "updated_at": "2025-10-15T10:00:00Z",
                            },
                        ],
                    },
                },
                response_only=True,
            )
        ],
    ),
    retrieve=extend_schema(
        summary="Retrieve a referral cost report",
        description="Get detailed information about a specific referral cost report.",
        tags=["Recruitment Reports"],
    ),
    create=extend_schema(
        summary="Create a referral cost report",
        description="Create a new referral cost report record.",
        tags=["Recruitment Reports"],
    ),
    update=extend_schema(
        summary="Update a referral cost report",
        description="Update an existing referral cost report.",
        tags=["Recruitment Reports"],
    ),
    partial_update=extend_schema(
        summary="Partially update a referral cost report",
        description="Partially update an existing referral cost report.",
        tags=["Recruitment Reports"],
    ),
    destroy=extend_schema(
        summary="Delete a referral cost report",
        description="Delete a referral cost report.",
        tags=["Recruitment Reports"],
    ),
)
class ReferralCostReportViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for ReferralCostReport model."""

    queryset = ReferralCostReport.objects.select_related("department", "employee").all()
    serializer_class = ReferralCostReportSerializer
    filterset_class = ReferralCostReportFilterSet
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = ["report_date", "created_at"]
    ordering = ["-report_date"]
