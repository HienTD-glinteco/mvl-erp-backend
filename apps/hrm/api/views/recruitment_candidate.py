from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.audit_logging import AuditLoggingMixin
from apps.audit_logging.history_mixin import HistoryMixin
from apps.hrm.api.filtersets import RecruitmentCandidateFilterSet
from apps.hrm.api.serializers import RecruitmentCandidateSerializer, UpdateReferrerSerializer
from apps.hrm.models import RecruitmentCandidate
from libs import BaseModelViewSet


@extend_schema_view(
    list=extend_schema(
        summary="List all recruitment candidates",
        description="Retrieve a paginated list of all recruitment candidates with support for filtering and search",
        tags=["Recruitment Candidate"],
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
                                "code": "RC0001",
                                "name": "Nguyen Van B",
                                "citizen_id": "123456789012",
                                "email": "nguyenvanb@example.com",
                                "phone": "0123456789",
                                "recruitment_request": {
                                    "id": 1,
                                    "code": "RR0001",
                                    "name": "Senior Backend Developer Position",
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
                                "recruitment_source": {
                                    "id": 1,
                                    "code": "RS001",
                                    "name": "LinkedIn",
                                },
                                "recruitment_channel": {
                                    "id": 1,
                                    "code": "CH001",
                                    "name": "Job Website",
                                },
                                "years_of_experience": 5,
                                "submitted_date": "2025-10-15",
                                "status": "CONTACTED",
                                "onboard_date": None,
                                "note": "Strong Python skills",
                                "referrer": None,
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
        summary="Create a new recruitment candidate",
        description="Create a new recruitment candidate. Branch, block, and department are automatically set from the recruitment request.",
        tags=["Recruitment Candidate"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "name": "Nguyen Van B",
                    "citizen_id": "123456789012",
                    "email": "nguyenvanb@example.com",
                    "phone": "0123456789",
                    "recruitment_request_id": 1,
                    "recruitment_source_id": 1,
                    "recruitment_channel_id": 1,
                    "years_of_experience": 5,
                    "submitted_date": "2025-10-15",
                    "status": "CONTACTED",
                    "note": "Strong Python skills",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "RC0001",
                        "name": "Nguyen Van B",
                        "citizen_id": "123456789012",
                        "email": "nguyenvanb@example.com",
                        "phone": "0123456789",
                        "recruitment_request": {
                            "id": 1,
                            "code": "RR0001",
                            "name": "Senior Backend Developer Position",
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
                        "recruitment_source": {
                            "id": 1,
                            "code": "RS001",
                            "name": "LinkedIn",
                        },
                        "recruitment_channel": {
                            "id": 1,
                            "code": "CH001",
                            "name": "Job Website",
                        },
                        "years_of_experience": 5,
                        "submitted_date": "2025-10-15",
                        "status": "CONTACTED",
                        "onboard_date": None,
                        "note": "Strong Python skills",
                        "referrer": None,
                        "created_at": "2025-10-16T03:00:00Z",
                        "updated_at": "2025-10-16T03:00:00Z",
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error - Invalid citizen_id",
                value={"success": False, "error": {"citizen_id": ["Citizen ID must be exactly 12 digits."]}},
                response_only=True,
                status_codes=["400"],
            ),
            OpenApiExample(
                "Error - Missing onboard_date for HIRED status",
                value={
                    "success": False,
                    "error": {"onboard_date": ["Onboard date is required when status is HIRED."]},
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get recruitment candidate details",
        description="Retrieve detailed information about a specific recruitment candidate",
        tags=["Recruitment Candidate"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "RC0001",
                        "name": "Nguyen Van B",
                        "citizen_id": "123456789012",
                        "email": "nguyenvanb@example.com",
                        "phone": "0123456789",
                        "recruitment_request": {
                            "id": 1,
                            "code": "RR0001",
                            "name": "Senior Backend Developer Position",
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
                        "recruitment_source": {
                            "id": 1,
                            "code": "RS001",
                            "name": "LinkedIn",
                        },
                        "recruitment_channel": {
                            "id": 1,
                            "code": "CH001",
                            "name": "Job Website",
                        },
                        "years_of_experience": 5,
                        "submitted_date": "2025-10-15",
                        "status": "CONTACTED",
                        "onboard_date": None,
                        "note": "Strong Python skills",
                        "referrer": None,
                        "created_at": "2025-10-16T03:00:00Z",
                        "updated_at": "2025-10-16T03:00:00Z",
                    },
                },
                response_only=True,
            )
        ],
    ),
    update=extend_schema(
        summary="Update recruitment candidate",
        description="Update recruitment candidate information. Branch, block, and department are automatically updated from the recruitment request.",
        tags=["Recruitment Candidate"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "name": "Nguyen Van B",
                    "citizen_id": "123456789012",
                    "email": "nguyenvanb@example.com",
                    "phone": "0123456789",
                    "recruitment_request_id": 1,
                    "recruitment_source_id": 1,
                    "recruitment_channel_id": 1,
                    "years_of_experience": 6,
                    "submitted_date": "2025-10-15",
                    "status": "INTERVIEWED_1",
                    "note": "Strong Python skills, good communication",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "RC0001",
                        "name": "Nguyen Van B",
                        "citizen_id": "123456789012",
                        "email": "nguyenvanb@example.com",
                        "phone": "0123456789",
                        "recruitment_request": {
                            "id": 1,
                            "code": "RR0001",
                            "name": "Senior Backend Developer Position",
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
                        "recruitment_source": {
                            "id": 1,
                            "code": "RS001",
                            "name": "LinkedIn",
                        },
                        "recruitment_channel": {
                            "id": 1,
                            "code": "CH001",
                            "name": "Job Website",
                        },
                        "years_of_experience": 6,
                        "submitted_date": "2025-10-15",
                        "status": "INTERVIEWED_1",
                        "onboard_date": None,
                        "note": "Strong Python skills, good communication",
                        "referrer": None,
                        "created_at": "2025-10-16T03:00:00Z",
                        "updated_at": "2025-10-16T03:05:00Z",
                    },
                },
                response_only=True,
            ),
        ],
    ),
    partial_update=extend_schema(
        summary="Partially update recruitment candidate",
        description="Partially update recruitment candidate information",
        tags=["Recruitment Candidate"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "status": "HIRED",
                    "onboard_date": "2025-11-01",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "RC0001",
                        "name": "Nguyen Van B",
                        "citizen_id": "123456789012",
                        "email": "nguyenvanb@example.com",
                        "phone": "0123456789",
                        "recruitment_request": {
                            "id": 1,
                            "code": "RR0001",
                            "name": "Senior Backend Developer Position",
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
                        "recruitment_source": {
                            "id": 1,
                            "code": "RS001",
                            "name": "LinkedIn",
                        },
                        "recruitment_channel": {
                            "id": 1,
                            "code": "CH001",
                            "name": "Job Website",
                        },
                        "years_of_experience": 5,
                        "submitted_date": "2025-10-15",
                        "status": "HIRED",
                        "onboard_date": "2025-11-01",
                        "note": "Strong Python skills",
                        "referrer": None,
                        "created_at": "2025-10-16T03:00:00Z",
                        "updated_at": "2025-10-16T03:10:00Z",
                    },
                },
                response_only=True,
            ),
        ],
    ),
    destroy=extend_schema(
        summary="Delete recruitment candidate",
        description="Remove a recruitment candidate from the system",
        tags=["Recruitment Candidate"],
        examples=[
            OpenApiExample(
                "Success",
                value={"success": True, "data": None},
                response_only=True,
            ),
        ],
    ),
)
class RecruitmentCandidateViewSet(HistoryMixin, AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for RecruitmentCandidate model"""

    queryset = RecruitmentCandidate.objects.select_related(
        "recruitment_request",
        "branch",
        "block",
        "department",
        "recruitment_source",
        "recruitment_channel",
        "referrer",
    ).all()
    serializer_class = RecruitmentCandidateSerializer
    filterset_class = RecruitmentCandidateFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "code", "email", "phone", "citizen_id"]
    ordering_fields = ["code", "name", "submitted_date", "status", "created_at"]
    ordering = ["-created_at"]

    # Permission registration attributes
    module = "HRM"
    submodule = "Recruitment"
    permission_prefix = "recruitment_candidate"

    @extend_schema(
        summary="Update candidate referrer",
        description="Update the referrer field for a recruitment candidate",
        tags=["Recruitment Candidate"],
        request=UpdateReferrerSerializer,
        examples=[
            OpenApiExample(
                "Request",
                value={"referrer_id": 1},
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "RC0001",
                        "name": "Nguyen Van B",
                        "citizen_id": "123456789012",
                        "email": "nguyenvanb@example.com",
                        "phone": "0123456789",
                        "recruitment_request": {
                            "id": 1,
                            "code": "RR0001",
                            "name": "Senior Backend Developer Position",
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
                        "recruitment_source": {
                            "id": 1,
                            "code": "RS001",
                            "name": "LinkedIn",
                        },
                        "recruitment_channel": {
                            "id": 1,
                            "code": "CH001",
                            "name": "Job Website",
                        },
                        "years_of_experience": 5,
                        "submitted_date": "2025-10-15",
                        "status": "CONTACTED",
                        "onboard_date": None,
                        "note": "Strong Python skills",
                        "referrer": {
                            "id": 1,
                            "code": "MV001",
                            "fullname": "Nguyen Van A",
                        },
                        "created_at": "2025-10-16T03:00:00Z",
                        "updated_at": "2025-10-16T03:15:00Z",
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error",
                value={"success": False, "error": {"referrer_id": ["Invalid pk - object does not exist."]}},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    @action(detail=True, methods=["patch"], url_path="update-referrer")
    def update_referrer(self, request, pk=None):
        """Custom action to update referrer field only"""
        instance = self.get_object()
        serializer = UpdateReferrerSerializer(data=request.data)

        if serializer.is_valid():
            referrer = serializer.validated_data.get("referrer_id")
            instance.referrer = referrer
            instance.save()
            return Response(self.get_serializer(instance).data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
