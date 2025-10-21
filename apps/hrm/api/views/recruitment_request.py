from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.audit_logging import AuditLoggingMixin
from apps.hrm.api.filtersets import RecruitmentRequestFilterSet
from apps.hrm.api.serializers import RecruitmentRequestSerializer
from apps.hrm.models import RecruitmentRequest
from libs import BaseModelViewSet


@extend_schema_view(
    list=extend_schema(
        summary="List all recruitment requests",
        description="Retrieve a paginated list of all recruitment requests with support for filtering and search",
        tags=["Recruitment Request"],
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
                                "code": "RR0001",
                                "name": "Senior Backend Developer Position",
                                "job_description": {
                                    "id": 1,
                                    "code": "JD0001",
                                    "title": "Senior Python Developer",
                                },
                                "branch": {
                                    "id": 1,
                                    "name": "Hanoi Branch",
                                    "code": "CN001",
                                },
                                "block": {
                                    "id": 1,
                                    "name": "Business Block",
                                    "code": "KH001",
                                },
                                "department": {
                                    "id": 1,
                                    "name": "IT Department",
                                    "code": "PB001",
                                },
                                "proposer": {
                                    "id": 1,
                                    "code": "MV001",
                                    "fullname": "Nguyen Van A",
                                },
                                "recruitment_type": "NEW_HIRE",
                                "status": "OPEN",
                                "colored_status": {
                                    "value": "OPEN",
                                    "variant": "green",
                                },
                                "colored_recruitment_type": {
                                    "value": "NEW_HIRE",
                                    "variant": "blue",
                                },
                                "proposed_salary": "2000-3000 USD",
                                "number_of_positions": 2,
                                "number_of_candidates": 5,
                                "number_of_hires": 2,
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
        summary="Create a new recruitment request",
        description="Create a new recruitment request. Branch and block are automatically set from the selected department (if provided).",
        tags=["Recruitment Request"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "name": "Senior Backend Developer Position",
                    "job_description_id": 1,
                    "proposer_id": 1,
                    "recruitment_type": "NEW_HIRE",
                    "status": "DRAFT",
                    "proposed_salary": "2000-3000 USD",
                    "number_of_positions": 2,
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "RR0001",
                        "name": "Senior Backend Developer Position",
                        "job_description": {
                            "id": 1,
                            "code": "JD0001",
                            "title": "Senior Python Developer",
                        },
                        "branch": None,
                        "block": None,
                        "department": None,
                        "proposer": {
                            "id": 1,
                            "code": "MV001",
                            "fullname": "Nguyen Van A",
                        },
                        "recruitment_type": "NEW_HIRE",
                        "status": "DRAFT",
                        "colored_status": {
                            "value": "DRAFT",
                            "variant": "grey",
                        },
                        "colored_recruitment_type": {
                            "value": "NEW_HIRE",
                            "variant": "blue",
                        },
                        "proposed_salary": "2000-3000 USD",
                        "number_of_positions": 2,
                        "number_of_candidates": 0,
                        "number_of_hires": 0,
                        "created_at": "2025-10-16T03:00:00Z",
                        "updated_at": "2025-10-16T03:00:00Z",
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error",
                value={"success": False, "error": {"name": ["This field is required."]}},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get recruitment request details",
        description="Retrieve detailed information about a specific recruitment request",
        tags=["Recruitment Request"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "RR0001",
                        "name": "Senior Backend Developer Position",
                        "job_description": {
                            "id": 1,
                            "code": "JD0001",
                            "title": "Senior Python Developer",
                        },
                        "branch": {
                            "id": 1,
                            "name": "Hanoi Branch",
                            "code": "CN001",
                        },
                        "block": {
                            "id": 1,
                            "name": "Business Block",
                            "code": "KH001",
                        },
                        "department": {
                            "id": 1,
                            "name": "IT Department",
                            "code": "PB001",
                        },
                        "proposer": {
                            "id": 1,
                            "code": "MV001",
                            "fullname": "Nguyen Van A",
                        },
                        "recruitment_type": "NEW_HIRE",
                        "status": "OPEN",
                        "colored_status": {
                            "value": "OPEN",
                            "variant": "green",
                        },
                        "colored_recruitment_type": {
                            "value": "NEW_HIRE",
                            "variant": "blue",
                        },
                        "proposed_salary": "2000-3000 USD",
                        "number_of_positions": 2,
                        "number_of_candidates": 5,
                        "number_of_hires": 2,
                        "created_at": "2025-10-16T03:00:00Z",
                        "updated_at": "2025-10-16T03:00:00Z",
                    },
                },
                response_only=True,
            )
        ],
    ),
    update=extend_schema(
        summary="Update recruitment request",
        description="Update recruitment request information. Branch and block are automatically updated from the department (if provided).",
        tags=["Recruitment Request"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "name": "Senior Backend Developer Position - Updated",
                    "job_description_id": 1,
                    "proposer_id": 1,
                    "recruitment_type": "NEW_HIRE",
                    "status": "OPEN",
                    "proposed_salary": "2500-3500 USD",
                    "number_of_positions": 3,
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "RR0001",
                        "name": "Senior Backend Developer Position - Updated",
                        "job_description": {
                            "id": 1,
                            "code": "JD0001",
                            "title": "Senior Python Developer",
                        },
                        "branch": {
                            "id": 1,
                            "name": "Hanoi Branch",
                            "code": "CN001",
                        },
                        "block": {
                            "id": 1,
                            "name": "Business Block",
                            "code": "KH001",
                        },
                        "department": {
                            "id": 1,
                            "name": "IT Department",
                            "code": "PB001",
                        },
                        "proposer": {
                            "id": 1,
                            "code": "MV001",
                            "fullname": "Nguyen Van A",
                        },
                        "recruitment_type": "NEW_HIRE",
                        "status": "OPEN",
                        "colored_status": {
                            "value": "OPEN",
                            "variant": "green",
                        },
                        "colored_recruitment_type": {
                            "value": "NEW_HIRE",
                            "variant": "blue",
                        },
                        "proposed_salary": "2500-3500 USD",
                        "number_of_positions": 3,
                        "number_of_candidates": 5,
                        "number_of_hires": 2,
                        "created_at": "2025-10-16T03:00:00Z",
                        "updated_at": "2025-10-16T03:05:00Z",
                    },
                },
                response_only=True,
            ),
        ],
    ),
    partial_update=extend_schema(
        summary="Partially update recruitment request",
        description="Partially update recruitment request information",
        tags=["Recruitment Request"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "status": "PAUSED",
                    "number_of_positions": 1,
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "RR0001",
                        "name": "Senior Backend Developer Position",
                        "job_description": {
                            "id": 1,
                            "code": "JD0001",
                            "title": "Senior Python Developer",
                        },
                        "branch": {
                            "id": 1,
                            "name": "Hanoi Branch",
                            "code": "CN001",
                        },
                        "block": {
                            "id": 1,
                            "name": "Business Block",
                            "code": "KH001",
                        },
                        "department": {
                            "id": 1,
                            "name": "IT Department",
                            "code": "PB001",
                        },
                        "proposer": {
                            "id": 1,
                            "code": "MV001",
                            "fullname": "Nguyen Van A",
                        },
                        "recruitment_type": "NEW_HIRE",
                        "status": "PAUSED",
                        "colored_status": {
                            "value": "PAUSED",
                            "variant": "yellow",
                        },
                        "colored_recruitment_type": {
                            "value": "NEW_HIRE",
                            "variant": "blue",
                        },
                        "proposed_salary": "2000-3000 USD",
                        "number_of_positions": 1,
                        "number_of_candidates": 5,
                        "number_of_hires": 2,
                        "created_at": "2025-10-16T03:00:00Z",
                        "updated_at": "2025-10-16T03:10:00Z",
                    },
                },
                response_only=True,
            ),
        ],
    ),
    destroy=extend_schema(
        summary="Delete recruitment request",
        description="Remove a recruitment request from the system. Only requests with DRAFT status can be deleted.",
        tags=["Recruitment Request"],
        examples=[
            OpenApiExample(
                "Success",
                value={"success": True, "data": None},
                response_only=True,
            ),
            OpenApiExample(
                "Error - Cannot delete non-draft",
                value={
                    "success": False,
                    "error": "Cannot delete recruitment request. Only requests with DRAFT status can be deleted.",
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
)
class RecruitmentRequestViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for RecruitmentRequest model"""

    queryset = RecruitmentRequest.objects.select_related(
        "job_description", "branch", "block", "department", "proposer"
    ).all()
    serializer_class = RecruitmentRequestSerializer
    filterset_class = RecruitmentRequestFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "code"]
    ordering_fields = ["code", "name", "created_at", "status"]
    ordering = ["-created_at"]

    # Permission registration attributes
    module = "HRM"
    submodule = "Recruitment"
    permission_prefix = "recruitment_request"

    def destroy(self, request, *args, **kwargs):
        """Delete recruitment request - only allowed for DRAFT status"""
        instance = self.get_object()

        if instance.status != RecruitmentRequest.Status.DRAFT:
            return Response(
                {"error": _("Cannot delete recruitment request. Only requests with DRAFT status can be deleted.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return super().destroy(request, *args, **kwargs)
