from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter, SearchFilter

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets import RecruitmentExpenseFilterSet
from apps.hrm.api.serializers import RecruitmentExpenseSerializer
from apps.hrm.models import RecruitmentExpense
from libs import BaseModelViewSet


@extend_schema_view(
    list=extend_schema(
        summary="List all recruitment expenses",
        description="Retrieve a list of all recruitment expenses with support for filtering and search. "
        "Pagination: 25 items per page by default (customizable via page_size parameter, e.g., ?page_size=20)",
        tags=["Recruitment Expense"],
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
                                "date": "2025-10-15",
                                "recruitment_source": {
                                    "id": 1,
                                    "code": "RS001",
                                    "name": "LinkedIn",
                                    "allow_referral": False,
                                },
                                "recruitment_channel": {
                                    "id": 1,
                                    "code": "RC001",
                                    "name": "Online Advertising",
                                },
                                "recruitment_request": {
                                    "id": 1,
                                    "code": "RR0001",
                                    "name": "Senior Backend Developer Position",
                                },
                                "num_candidates_participated": 10,
                                "total_cost": "5000.00",
                                "num_candidates_hired": 2,
                                "avg_cost": "2500.00",
                                "referee": None,
                                "referrer": None,
                                "activity": "Posted job ad on LinkedIn for 30 days",
                                "note": "Good response rate",
                                "created_at": "2025-10-16T03:00:00Z",
                                "updated_at": "2025-10-16T03:00:00Z",
                            }
                        ],
                    },
                },
                response_only=True,
            )
        ],
    ),
    create=extend_schema(
        summary="Create a new recruitment expense",
        description="Create a new recruitment expense in the system. If recruitment source allows referral, "
        "both referee_id and referrer_id are required.",
        tags=["Recruitment Expense"],
        examples=[
            OpenApiExample(
                "Request - Without Referral",
                value={
                    "date": "2025-10-15",
                    "recruitment_source_id": 1,
                    "recruitment_channel_id": 1,
                    "recruitment_request_id": 1,
                    "num_candidates_participated": 10,
                    "total_cost": "5000.00",
                    "num_candidates_hired": 2,
                    "activity": "Posted job ad on LinkedIn for 30 days",
                    "note": "Good response rate",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Request - With Referral",
                value={
                    "date": "2025-10-15",
                    "recruitment_source_id": 2,
                    "recruitment_channel_id": 2,
                    "recruitment_request_id": 1,
                    "num_candidates_participated": 3,
                    "total_cost": "1000.00",
                    "num_candidates_hired": 1,
                    "referee_id": 5,
                    "referrer_id": 10,
                    "activity": "Employee referral program",
                    "note": "High quality candidates",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "date": "2025-10-15",
                        "recruitment_source": {
                            "id": 1,
                            "code": "RS001",
                            "name": "LinkedIn",
                            "allow_referral": False,
                        },
                        "recruitment_channel": {
                            "id": 1,
                            "code": "RC001",
                            "name": "Online Advertising",
                        },
                        "recruitment_request": {
                            "id": 1,
                            "code": "RR0001",
                            "name": "Senior Backend Developer Position",
                        },
                        "num_candidates_participated": 10,
                        "total_cost": "5000.00",
                        "num_candidates_hired": 2,
                        "avg_cost": "2500.00",
                        "referee": None,
                        "referrer": None,
                        "activity": "Posted job ad on LinkedIn for 30 days",
                        "note": "Good response rate",
                        "created_at": "2025-10-16T03:00:00Z",
                        "updated_at": "2025-10-16T03:00:00Z",
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error - Referral Validation",
                value={
                    "success": False,
                    "error": {
                        "referee": ["Referee is required when recruitment source allows referral."],
                        "referrer": ["Referrer is required when recruitment source allows referral."],
                    },
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get recruitment expense details",
        description="Retrieve detailed information about a specific recruitment expense",
        tags=["Recruitment Expense"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "date": "2025-10-15",
                        "recruitment_source": {
                            "id": 1,
                            "code": "RS001",
                            "name": "LinkedIn",
                            "allow_referral": False,
                        },
                        "recruitment_channel": {
                            "id": 1,
                            "code": "RC001",
                            "name": "Online Advertising",
                        },
                        "recruitment_request": {
                            "id": 1,
                            "code": "RR0001",
                            "name": "Senior Backend Developer Position",
                        },
                        "num_candidates_participated": 10,
                        "total_cost": "5000.00",
                        "num_candidates_hired": 2,
                        "avg_cost": "2500.00",
                        "referee": None,
                        "referrer": None,
                        "activity": "Posted job ad on LinkedIn for 30 days",
                        "note": "Good response rate",
                        "created_at": "2025-10-16T03:00:00Z",
                        "updated_at": "2025-10-16T03:00:00Z",
                    },
                },
                response_only=True,
            )
        ],
    ),
    update=extend_schema(
        summary="Update recruitment expense",
        description="Update recruitment expense information",
        tags=["Recruitment Expense"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "date": "2025-10-15",
                    "recruitment_source_id": 1,
                    "recruitment_channel_id": 1,
                    "recruitment_request_id": 1,
                    "num_candidates_participated": 12,
                    "total_cost": "6000.00",
                    "num_candidates_hired": 3,
                    "activity": "Extended job ad on LinkedIn for 45 days",
                    "note": "Increased budget for better reach",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "date": "2025-10-15",
                        "recruitment_source": {
                            "id": 1,
                            "code": "RS001",
                            "name": "LinkedIn",
                            "allow_referral": False,
                        },
                        "recruitment_channel": {
                            "id": 1,
                            "code": "RC001",
                            "name": "Online Advertising",
                        },
                        "recruitment_request": {
                            "id": 1,
                            "code": "RR0001",
                            "name": "Senior Backend Developer Position",
                        },
                        "num_candidates_participated": 12,
                        "total_cost": "6000.00",
                        "num_candidates_hired": 3,
                        "avg_cost": "2000.00",
                        "referee": None,
                        "referrer": None,
                        "activity": "Extended job ad on LinkedIn for 45 days",
                        "note": "Increased budget for better reach",
                        "created_at": "2025-10-16T03:00:00Z",
                        "updated_at": "2025-10-16T03:05:00Z",
                    },
                },
                response_only=True,
            ),
        ],
    ),
    partial_update=extend_schema(
        summary="Partially update recruitment expense",
        description="Partially update recruitment expense information",
        tags=["Recruitment Expense"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "num_candidates_hired": 3,
                    "note": "Additional candidate hired",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "date": "2025-10-15",
                        "recruitment_source": {
                            "id": 1,
                            "code": "RS001",
                            "name": "LinkedIn",
                            "allow_referral": False,
                        },
                        "recruitment_channel": {
                            "id": 1,
                            "code": "RC001",
                            "name": "Online Advertising",
                        },
                        "recruitment_request": {
                            "id": 1,
                            "code": "RR0001",
                            "name": "Senior Backend Developer Position",
                        },
                        "num_candidates_participated": 10,
                        "total_cost": "5000.00",
                        "num_candidates_hired": 3,
                        "avg_cost": "1666.67",
                        "referee": None,
                        "referrer": None,
                        "activity": "Posted job ad on LinkedIn for 30 days",
                        "note": "Additional candidate hired",
                        "created_at": "2025-10-16T03:00:00Z",
                        "updated_at": "2025-10-16T03:10:00Z",
                    },
                },
                response_only=True,
            ),
        ],
    ),
    destroy=extend_schema(
        summary="Delete recruitment expense",
        description="Remove a recruitment expense from the system",
        tags=["Recruitment Expense"],
        examples=[
            OpenApiExample(
                "Success",
                value={"success": True, "data": None},
                response_only=True,
            )
        ],
    ),
)
class RecruitmentExpenseViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for RecruitmentExpense model"""

    queryset = RecruitmentExpense.objects.all()
    serializer_class = RecruitmentExpenseSerializer
    filterset_class = RecruitmentExpenseFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["activity", "note"]
    ordering_fields = ["date", "total_cost", "created_at"]
    ordering = ["-created_at"]

    # Permission registration attributes
    module = "HRM"
    submodule = "Recruitment"
    permission_prefix = "recruitment_expense"
