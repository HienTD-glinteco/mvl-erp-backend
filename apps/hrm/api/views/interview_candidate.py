from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets import InterviewCandidateFilterSet
from apps.hrm.api.serializers import InterviewCandidateSerializer
from apps.hrm.models import InterviewCandidate
from libs import BaseModelViewSet


@extend_schema_view(
    list=extend_schema(
        summary="List all interview candidates",
        description="Retrieve a paginated list of all interview candidates with support for filtering",
        tags=["Interview Candidate"],
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
                                "recruitment_candidate": {
                                    "id": 1,
                                    "code": "UV0001",
                                    "name": "Nguyen Van B",
                                    "citizen_id": "123456789012",
                                    "email": "nguyenvanb@example.com",
                                    "phone": "0123456789",
                                },
                                "interview_schedule": {
                                    "id": 1,
                                    "title": "First Round Interview",
                                    "interview_type": "IN_PERSON",
                                    "location": "Office Meeting Room A",
                                    "time": "2025-10-25T10:00:00Z",
                                },
                                "interview_time": "2025-10-25T10:00:00Z",
                                "email_sent_at": "2025-10-24T09:00:00Z",
                                "created_at": "2025-10-22T03:00:00Z",
                                "updated_at": "2025-10-22T03:00:00Z",
                            }
                        ],
                    },
                },
                response_only=True,
            )
        ],
    ),
    create=extend_schema(
        summary="Create a new interview candidate",
        description="Link a recruitment candidate to an interview schedule",
        tags=["Interview Candidate"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "recruitment_candidate_id": 1,
                    "interview_schedule_id": 1,
                    "interview_time": "2025-10-25T10:00:00Z",
                    "email_sent_at": None,
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "recruitment_candidate": {
                            "id": 1,
                            "code": "UV0001",
                            "name": "Nguyen Van B",
                            "citizen_id": "123456789012",
                            "email": "nguyenvanb@example.com",
                            "phone": "0123456789",
                        },
                        "interview_schedule": {
                            "id": 1,
                            "title": "First Round Interview",
                            "interview_type": "IN_PERSON",
                            "location": "Office Meeting Room A",
                            "time": "2025-10-25T10:00:00Z",
                        },
                        "interview_time": "2025-10-25T10:00:00Z",
                        "email_sent_at": None,
                        "created_at": "2025-10-22T03:00:00Z",
                        "updated_at": "2025-10-22T03:00:00Z",
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error - Missing required field",
                value={"success": False, "error": {"interview_time": ["This field is required."]}},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get interview candidate details",
        description="Retrieve detailed information about a specific interview candidate",
        tags=["Interview Candidate"],
    ),
    update=extend_schema(
        summary="Update interview candidate",
        description="Update interview candidate information",
        tags=["Interview Candidate"],
    ),
    partial_update=extend_schema(
        summary="Partially update interview candidate",
        description="Partially update interview candidate information",
        tags=["Interview Candidate"],
    ),
    destroy=extend_schema(
        summary="Delete interview candidate",
        description="Remove an interview candidate from the system",
        tags=["Interview Candidate"],
        examples=[
            OpenApiExample(
                "Success",
                value={"success": True, "data": None},
                response_only=True,
            ),
        ],
    ),
)
class InterviewCandidateViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for InterviewCandidate model"""

    queryset = (
        InterviewCandidate.objects.select_related(
            "recruitment_candidate",
            "interview_schedule",
        )
        .prefetch_related(
            "recruitment_candidate__recruitment_request",
        )
        .all()
    )
    serializer_class = InterviewCandidateSerializer
    filterset_class = InterviewCandidateFilterSet
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = ["interview_time", "created_at"]
    ordering = ["interview_time"]

    # Permission registration attributes
    module = "HRM"
    submodule = "Recruitment"
    permission_prefix = "interview_candidate"
