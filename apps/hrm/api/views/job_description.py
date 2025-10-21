from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets import JobDescriptionFilterSet
from apps.hrm.api.serializers import JobDescriptionSerializer
from apps.hrm.models import JobDescription
from libs import BaseModelViewSet


@extend_schema_view(
    list=extend_schema(
        summary="List all job descriptions",
        description="Retrieve a list of all job descriptions with support for filtering and search",
        tags=["Job Description"],
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
                                "code": "JD0001",
                                "title": "Senior Python Developer",
                                "responsibility": "Develop and maintain backend services",
                                "requirement": "5+ years Python experience",
                                "preferred_criteria": "Experience with Django and FastAPI",
                                "benefit": "Competitive salary and benefits",
                                "proposed_salary": "2000-3000 USD",
                                "note": "Remote work available",
                                "attachment": "",
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
        summary="Create a new job description",
        description="Create a new job description in the system",
        tags=["Job Description"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "JD0001",
                        "title": "Senior Python Developer",
                        "responsibility": "Develop and maintain backend services",
                        "requirement": "5+ years Python experience",
                        "preferred_criteria": "Experience with Django and FastAPI",
                        "benefit": "Competitive salary and benefits",
                        "proposed_salary": "2000-3000 USD",
                        "note": "Remote work available",
                        "attachment": "",
                        "created_at": "2025-10-16T03:00:00Z",
                        "updated_at": "2025-10-16T03:00:00Z",
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error",
                value={"success": False, "error": {"title": ["This field is required."]}},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get job description details",
        description="Retrieve detailed information about a specific job description",
        tags=["Job Description"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "JD0001",
                        "title": "Senior Python Developer",
                        "responsibility": "Develop and maintain backend services",
                        "requirement": "5+ years Python experience",
                        "preferred_criteria": "Experience with Django and FastAPI",
                        "benefit": "Competitive salary and benefits",
                        "proposed_salary": "2000-3000 USD",
                        "note": "Remote work available",
                        "attachment": "",
                        "created_at": "2025-10-16T03:00:00Z",
                        "updated_at": "2025-10-16T03:00:00Z",
                    },
                },
                response_only=True,
            )
        ],
    ),
    update=extend_schema(
        summary="Update job description",
        description="Update job description information",
        tags=["Job Description"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "JD0001",
                        "title": "Senior Python Developer",
                        "responsibility": "Develop and maintain backend services",
                        "requirement": "5+ years Python experience",
                        "preferred_criteria": "Experience with Django and FastAPI",
                        "benefit": "Competitive salary and benefits",
                        "proposed_salary": "2000-3000 USD",
                        "note": "Remote work available",
                        "attachment": "",
                        "created_at": "2025-10-16T03:00:00Z",
                        "updated_at": "2025-10-16T03:00:00Z",
                    },
                },
                response_only=True,
            )
        ],
    ),
    partial_update=extend_schema(
        summary="Partially update job description",
        description="Partially update job description information",
        tags=["Job Description"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "JD0001",
                        "title": "Senior Python Developer",
                        "responsibility": "Develop and maintain backend services",
                        "requirement": "5+ years Python experience",
                        "preferred_criteria": "Experience with Django and FastAPI",
                        "benefit": "Competitive salary and benefits",
                        "proposed_salary": "2000-3000 USD",
                        "note": "Remote work available",
                        "attachment": "",
                        "created_at": "2025-10-16T03:00:00Z",
                        "updated_at": "2025-10-16T03:00:00Z",
                    },
                },
                response_only=True,
            )
        ],
    ),
    destroy=extend_schema(
        summary="Delete job description",
        description="Remove a job description from the system",
        tags=["Job Description"],
        examples=[
            OpenApiExample(
                "Success",
                value={"success": True, "data": None},
                response_only=True,
            )
        ],
    ),
)
class JobDescriptionViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for JobDescription model"""

    queryset = JobDescription.objects.all()
    serializer_class = JobDescriptionSerializer
    filterset_class = JobDescriptionFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["title", "code", "responsibility", "requirement"]
    ordering_fields = ["title", "code", "created_at"]
    ordering = ["-created_at"]

    # Permission registration attributes
    module = "HRM"
    submodule = "Recruitment"
    permission_prefix = "job_description"

    @extend_schema(
        summary="Copy job description",
        description="Create a duplicate of an existing job description",
        tags=["Job Description"],
        request=None,
        responses={200: JobDescriptionSerializer},
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 2,
                        "code": "JD0002",
                        "title": "Senior Python Developer",
                        "responsibility": "Develop and maintain backend services",
                        "requirement": "5+ years Python experience",
                        "preferred_criteria": "Experience with Django and FastAPI",
                        "benefit": "Competitive salary and benefits",
                        "proposed_salary": "2000-3000 USD",
                        "note": "Remote work available",
                        "attachment": "",
                        "created_at": "2025-10-16T03:05:00Z",
                        "updated_at": "2025-10-16T03:05:00Z",
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error",
                value={"success": False, "error": "Job description not found"},
                response_only=True,
                status_codes=["404"],
            ),
        ],
    )
    @action(detail=True, methods=["post"], url_path="copy")
    def copy(self, request, pk=None):
        """Create a duplicate of an existing job description"""
        original = self.get_object()

        # Create a copy with all fields except id, code, created_at, updated_at
        copied = JobDescription.objects.create(
            title=original.title,
            responsibility=original.responsibility,
            requirement=original.requirement,
            preferred_criteria=original.preferred_criteria,
            benefit=original.benefit,
            proposed_salary=original.proposed_salary,
            note=original.note,
            attachment=original.attachment,
        )

        serializer = self.get_serializer(copied)
        return Response(serializer.data, status=status.HTTP_200_OK)
