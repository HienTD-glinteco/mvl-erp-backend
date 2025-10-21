from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter, SearchFilter

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets import RecruitmentCandidateContactLogFilterSet
from apps.hrm.api.serializers import RecruitmentCandidateContactLogSerializer
from apps.hrm.models import RecruitmentCandidateContactLog
from libs import BaseModelViewSet


@extend_schema_view(
    list=extend_schema(
        summary="List all recruitment candidate contact logs",
        description="Retrieve a paginated list of all recruitment candidate contact logs with support for filtering",
        tags=["Recruitment Candidate Contact Log"],
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
                                "employee": {
                                    "id": 1,
                                    "code": "MV001",
                                    "fullname": "Nguyen Van A",
                                },
                                "date": "2025-10-16",
                                "method": "PHONE",
                                "note": "Contacted to schedule first interview",
                                "recruitment_candidate": {
                                    "id": 1,
                                    "code": "RC0001",
                                    "name": "Nguyen Van B",
                                },
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
        summary="Create a new recruitment candidate contact log",
        description="Create a new contact log entry for a recruitment candidate",
        tags=["Recruitment Candidate Contact Log"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "employee_id": 1,
                    "date": "2025-10-16",
                    "method": "PHONE",
                    "note": "Contacted to schedule first interview",
                    "recruitment_candidate_id": 1,
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "employee": {
                            "id": 1,
                            "code": "MV001",
                            "fullname": "Nguyen Van A",
                        },
                        "date": "2025-10-16",
                        "method": "PHONE",
                        "note": "Contacted to schedule first interview",
                        "recruitment_candidate": {
                            "id": 1,
                            "code": "RC0001",
                            "name": "Nguyen Van B",
                        },
                        "created_at": "2025-10-16T03:00:00Z",
                        "updated_at": "2025-10-16T03:00:00Z",
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error",
                value={"success": False, "error": {"date": ["This field is required."]}},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get recruitment candidate contact log details",
        description="Retrieve detailed information about a specific contact log",
        tags=["Recruitment Candidate Contact Log"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "employee": {
                            "id": 1,
                            "code": "MV001",
                            "fullname": "Nguyen Van A",
                        },
                        "date": "2025-10-16",
                        "method": "PHONE",
                        "note": "Contacted to schedule first interview",
                        "recruitment_candidate": {
                            "id": 1,
                            "code": "RC0001",
                            "name": "Nguyen Van B",
                        },
                        "created_at": "2025-10-16T03:00:00Z",
                        "updated_at": "2025-10-16T03:00:00Z",
                    },
                },
                response_only=True,
            )
        ],
    ),
    update=extend_schema(
        summary="Update recruitment candidate contact log",
        description="Update contact log information",
        tags=["Recruitment Candidate Contact Log"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "employee_id": 1,
                    "date": "2025-10-16",
                    "method": "EMAIL",
                    "note": "Sent interview confirmation via email",
                    "recruitment_candidate_id": 1,
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "employee": {
                            "id": 1,
                            "code": "MV001",
                            "fullname": "Nguyen Van A",
                        },
                        "date": "2025-10-16",
                        "method": "EMAIL",
                        "note": "Sent interview confirmation via email",
                        "recruitment_candidate": {
                            "id": 1,
                            "code": "RC0001",
                            "name": "Nguyen Van B",
                        },
                        "created_at": "2025-10-16T03:00:00Z",
                        "updated_at": "2025-10-16T03:05:00Z",
                    },
                },
                response_only=True,
            ),
        ],
    ),
    partial_update=extend_schema(
        summary="Partially update recruitment candidate contact log",
        description="Partially update contact log information",
        tags=["Recruitment Candidate Contact Log"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "note": "Candidate confirmed interview time",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "employee": {
                            "id": 1,
                            "code": "MV001",
                            "fullname": "Nguyen Van A",
                        },
                        "date": "2025-10-16",
                        "method": "PHONE",
                        "note": "Candidate confirmed interview time",
                        "recruitment_candidate": {
                            "id": 1,
                            "code": "RC0001",
                            "name": "Nguyen Van B",
                        },
                        "created_at": "2025-10-16T03:00:00Z",
                        "updated_at": "2025-10-16T03:10:00Z",
                    },
                },
                response_only=True,
            ),
        ],
    ),
    destroy=extend_schema(
        summary="Delete recruitment candidate contact log",
        description="Remove a contact log entry from the system",
        tags=["Recruitment Candidate Contact Log"],
        examples=[
            OpenApiExample(
                "Success",
                value={"success": True, "data": None},
                response_only=True,
            ),
        ],
    ),
)
class RecruitmentCandidateContactLogViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for RecruitmentCandidateContactLog model"""

    queryset = RecruitmentCandidateContactLog.objects.select_related("employee", "recruitment_candidate").all()
    serializer_class = RecruitmentCandidateContactLogSerializer
    filterset_class = RecruitmentCandidateContactLogFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["recruitment_candidate__name", "recruitment_candidate__code", "note"]
    ordering_fields = ["date", "created_at", "method"]
    ordering = ["-date", "-created_at"]

    # Permission registration attributes
    module = "HRM"
    submodule = "Recruitment"
    permission_prefix = "recruitment_candidate_contact_log"
