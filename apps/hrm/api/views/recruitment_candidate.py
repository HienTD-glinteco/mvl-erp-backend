from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets import RecruitmentCandidateFilterSet
from apps.hrm.api.serializers import (
    CandidateToEmployeeSerializer,
    EmployeeSerializer,
    RecruitmentCandidateExportSerializer,
    RecruitmentCandidateSerializer,
    UpdateReferrerSerializer,
)
from apps.hrm.models import RecruitmentCandidate
from apps.imports.api.mixins import AsyncImportProgressMixin
from libs import BaseModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter
from libs.export_xlsx import ExportXLSXMixin


@extend_schema_view(
    list=extend_schema(
        summary="List all recruitment candidates",
        description="Retrieve a paginated list of all recruitment candidates with support for filtering and search",
        tags=["4.6 Recruitment Candidate"],
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
                                "years_of_experience": "MORE_THAN_FIVE_YEARS",
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
        tags=["4.6 Recruitment Candidate"],
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
                    "years_of_experience": "MORE_THAN_FIVE_YEARS",
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
                        "years_of_experience": "MORE_THAN_FIVE_YEARS",
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
        tags=["4.6 Recruitment Candidate"],
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
                        "years_of_experience": "MORE_THAN_FIVE_YEARS",
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
        tags=["4.6 Recruitment Candidate"],
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
                    "years_of_experience": "MORE_THAN_FIVE_YEARS",
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
                        "years_of_experience": "MORE_THAN_FIVE_YEARS",
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
        tags=["4.6 Recruitment Candidate"],
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
                        "years_of_experience": "MORE_THAN_FIVE_YEARS",
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
        tags=["4.6 Recruitment Candidate"],
        examples=[
            OpenApiExample(
                "Success",
                value={"success": True, "data": None},
                response_only=True,
            ),
        ],
    ),
    export=extend_schema(
        tags=["4.6 Recruitment Candidate"],
    ),
    start_import=extend_schema(
        tags=["4.6 Recruitment Candidate"],
    ),
    import_template=extend_schema(
        tags=["4.6 Recruitment Candidate"],
    ),
)
class RecruitmentCandidateViewSet(AsyncImportProgressMixin, ExportXLSXMixin, AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for RecruitmentCandidate model"""

    queryset = RecruitmentCandidate.objects.select_related(
        "recruitment_request",
        "branch",
        "block",
        "department",
        "recruitment_source",
        "recruitment_channel",
        "referrer",
        "employee",
    ).all()
    serializer_class = RecruitmentCandidateSerializer
    filterset_class = RecruitmentCandidateFilterSet
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    search_fields = ["name", "code", "email", "phone", "citizen_id"]
    ordering_fields = ["code", "name", "submitted_date", "status", "created_at"]
    ordering = ["-created_at"]

    # Permission registration attributes
    module = "HRM"
    submodule = "Recruitment"
    permission_prefix = "recruitment_candidate"

    # Import handler path for AsyncImportProgressMixin
    import_row_handler = "apps.hrm.import_handlers.recruitment_candidate.import_handler"  # type: ignore[assignment]

    def get_export_data(self, request):
        """Custom export data for RecruitmentCandidate.

        Exports the following fields:
        - code
        - name
        - recruitment_request__name
        - recruitment_source__name
        - recruitment_channel__name
        - phone
        - status
        """
        queryset = self.filter_queryset(self.get_queryset())
        serializer = RecruitmentCandidateExportSerializer(queryset, many=True)
        data = serializer.data

        return {
            "sheets": [
                {
                    "name": "Recruitment Candidates",
                    "headers": [
                        "Code",
                        "Name",
                        "Recruitment Request",
                        "Recruitment Source",
                        "Recruitment Channel",
                        "Phone",
                        "Status",
                    ],
                    "field_names": [
                        "code",
                        "name",
                        "recruitment_request__name",
                        "recruitment_source__name",
                        "recruitment_channel__name",
                        "phone",
                        "status",
                    ],
                    "data": data,
                }
            ]
        }

    @extend_schema(
        summary="Update candidate referrer",
        description="Update the referrer field for a recruitment candidate",
        tags=["4.6 Recruitment Candidate"],
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
                        "years_of_experience": "MORE_THAN_FIVE_YEARS",
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

    @extend_schema(
        summary="Convert candidate to employee",
        description="Convert a recruitment candidate to an employee. Requires code_type in request body. Copies shared fields (name, email, citizen_id, phone, department), sets start_date to today, generates random 6-digit attendance_code, and sets username to candidate's email.",
        tags=["4.6 Recruitment Candidate"],
        request=CandidateToEmployeeSerializer,
        examples=[
            OpenApiExample(
                "Request",
                value={"code_type": "MV"},
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code_type": "MV",
                        "code": "MV0001",
                        "fullname": "Nguyen Van B",
                        "attendance_code": "123456",
                        "username": "nguyenvanb@example.com",
                        "email": "nguyenvanb@example.com",
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
                        "position": None,
                        "contract_type": None,
                        "start_date": "2025-10-28",
                        "status": "Onboarding",
                        "date_of_birth": None,
                        "gender": "MALE",
                        "marital_status": "SINGLE",
                        "citizen_id": "123456789012",
                        "phone": "0123456789",
                        "personal_email": None,
                        "is_onboarding_email_sent": False,
                        "created_at": "2025-10-28T10:30:00Z",
                        "updated_at": "2025-10-28T10:30:00Z",
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error - Already Converted",
                value={
                    "success": False,
                    "error": {"non_field_errors": ["This candidate has already been converted to an employee."]},
                },
                response_only=True,
                status_codes=["400"],
            ),
            OpenApiExample(
                "Error - Validation Failed",
                value={
                    "success": False,
                    "error": {"code_type": ["This field is required."]},
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    @action(detail=True, methods=["post"], url_path="to-employee")
    def to_employee(self, request, pk=None):
        """Convert recruitment candidate to employee"""
        candidate = self.get_object()

        serializer = CandidateToEmployeeSerializer(
            data=request.data,
            context={"candidate": candidate},
        )

        if serializer.is_valid():
            employee = serializer.save()
            return Response(EmployeeSerializer(employee).data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
