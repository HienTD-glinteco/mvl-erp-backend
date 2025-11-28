from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets import JobDescriptionFilterSet
from apps.hrm.api.serializers import JobDescriptionSerializer
from apps.hrm.models import JobDescription
from libs import BaseModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter
from libs.export_xlsx.mixins import ExportXLSXMixin


@extend_schema_view(
    list=extend_schema(
        summary="List all job descriptions",
        description="Retrieve a list of all job descriptions with support for filtering and search",
        tags=["4.5 Job Description"],
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
                                "position_title": "Senior Backend Developer",
                                "responsibility": "Develop and maintain backend services",
                                "requirement": "5+ years Python experience",
                                "preferred_criteria": "Experience with Django and FastAPI",
                                "benefit": "Competitive salary and benefits",
                                "proposed_salary": "2000-3000 USD",
                                "note": "Remote work available",
                                "attachment": None,
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
        description="Create a new job description in the system. Optionally include file token for attachment upload.",
        tags=["4.5 Job Description"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "JD0001",
                        "title": "Senior Python Developer",
                        "position_title": "Senior Backend Developer",
                        "responsibility": "Develop and maintain backend services",
                        "requirement": "5+ years Python experience",
                        "preferred_criteria": "Experience with Django and FastAPI",
                        "benefit": "Competitive salary and benefits",
                        "proposed_salary": "2000-3000 USD",
                        "note": "Remote work available",
                        "attachment": None,
                        "created_at": "2025-10-16T03:00:00Z",
                        "updated_at": "2025-10-16T03:00:00Z",
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Success with attachment",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "JD0001",
                        "title": "Senior Python Developer",
                        "position_title": "Senior Backend Developer",
                        "responsibility": "Develop and maintain backend services",
                        "requirement": "5+ years Python experience",
                        "preferred_criteria": "Experience with Django and FastAPI",
                        "benefit": "Competitive salary and benefits",
                        "proposed_salary": "2000-3000 USD",
                        "note": "Remote work available",
                        "attachment": {
                            "id": 1,
                            "purpose": "job_description",
                            "file_name": "jd_attachment.pdf",
                            "file_path": "uploads/job_description/1/jd_attachment.pdf",
                            "size": 123456,
                            "is_confirmed": True,
                            "view_url": "https://example.com/view/...",
                            "download_url": "https://example.com/download/...",
                        },
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
        tags=["4.5 Job Description"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "JD0001",
                        "title": "Senior Python Developer",
                        "position_title": "Senior Backend Developer",
                        "responsibility": "Develop and maintain backend services",
                        "requirement": "5+ years Python experience",
                        "preferred_criteria": "Experience with Django and FastAPI",
                        "benefit": "Competitive salary and benefits",
                        "proposed_salary": "2000-3000 USD",
                        "note": "Remote work available",
                        "attachment": None,
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
        tags=["4.5 Job Description"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "JD0001",
                        "title": "Senior Python Developer",
                        "position_title": "Senior Backend Developer",
                        "responsibility": "Develop and maintain backend services",
                        "requirement": "5+ years Python experience",
                        "preferred_criteria": "Experience with Django and FastAPI",
                        "benefit": "Competitive salary and benefits",
                        "proposed_salary": "2000-3000 USD",
                        "note": "Remote work available",
                        "attachment": None,
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
        tags=["4.5 Job Description"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "JD0001",
                        "title": "Senior Python Developer",
                        "position_title": "Senior Backend Developer",
                        "responsibility": "Develop and maintain backend services",
                        "requirement": "5+ years Python experience",
                        "preferred_criteria": "Experience with Django and FastAPI",
                        "benefit": "Competitive salary and benefits",
                        "proposed_salary": "2000-3000 USD",
                        "note": "Remote work available",
                        "attachment": None,
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
        tags=["4.5 Job Description"],
        examples=[
            OpenApiExample(
                "Success",
                value={"success": True, "data": None},
                response_only=True,
            )
        ],
    ),
    export=extend_schema(
        tags=["4.5 Job Description"],
    ),
)
class JobDescriptionViewSet(ExportXLSXMixin, AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for JobDescription model"""

    queryset = JobDescription.objects.all()
    serializer_class = JobDescriptionSerializer
    filterset_class = JobDescriptionFilterSet
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    search_fields = ["title", "code", "responsibility", "requirement"]
    ordering_fields = ["title", "code", "created_at"]
    ordering = ["-created_at"]

    # Permission registration attributes
    module = "HRM"
    submodule = "Recruitment"
    permission_prefix = "job_description"

    def get_export_data(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        data = {
            "sheets": [
                {
                    "name": str(JobDescription._meta.verbose_name),
                    "headers": [str(field.label) for field in serializer.child.fields.values()],
                    "field_names": list(serializer.child.fields.keys()),
                    "data": serializer.data,
                }
            ]
        }
        return data
