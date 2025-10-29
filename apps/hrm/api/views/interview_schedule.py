from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets import InterviewScheduleFilterSet
from apps.hrm.api.serializers import (
    InterviewScheduleSerializer,
    UpdateInterviewersSerializer,
)
from apps.hrm.callbacks import mark_interview_candidate_email_sent
from apps.hrm.models import InterviewSchedule
from apps.mailtemplates.permissions import CanSendMail
from apps.mailtemplates.view_mixins import TemplateActionMixin
from libs import BaseModelViewSet


@extend_schema_view(
    list=extend_schema(
        summary="List all interview schedules",
        description="Retrieve a paginated list of all interview schedules with support for filtering and search",
        tags=["Interview Schedule"],
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
                                "title": "First Round Interview",
                                "recruitment_request": {
                                    "id": 1,
                                    "code": "RR0001",
                                    "name": "Senior Backend Developer Position",
                                    "position_title": "Backend Developer",
                                },
                                "interview_type": "IN_PERSON",
                                "location": "Office Meeting Room A",
                                "time": "2025-10-25T10:00:00Z",
                                "note": "Please bring portfolio",
                                "interviewers": [
                                    {
                                        "id": 1,
                                        "code": "MV001",
                                        "fullname": "Nguyen Van A",
                                        "branch_name": "Head Office",
                                        "block_name": "Technology",
                                        "department_name": "Engineering",
                                        "position_name": "Senior HR Manager",
                                    }
                                ],
                                "number_of_candidates": 1,
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
        summary="Create a new interview schedule",
        description="Create a new interview schedule. Candidates and interviewers should be added via custom actions after creation.",
        tags=["Interview Schedule"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "title": "First Round Interview",
                    "recruitment_request_id": 1,
                    "interview_type": "IN_PERSON",
                    "location": "Office Meeting Room A",
                    "time": "2025-10-25T10:00:00Z",
                    "note": "Please bring portfolio",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "title": "First Round Interview",
                        "recruitment_request": {
                            "id": 1,
                            "code": "RR0001",
                            "name": "Senior Backend Developer Position",
                            "position_title": "Backend Developer",
                        },
                        "interview_type": "IN_PERSON",
                        "location": "Office Meeting Room A",
                        "time": "2025-10-25T10:00:00Z",
                        "note": "Please bring portfolio",
                        "interviewers": [],
                        "number_of_candidates": 0,
                        "created_at": "2025-10-22T03:00:00Z",
                        "updated_at": "2025-10-22T03:00:00Z",
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error - Missing required field",
                value={"success": False, "error": {"title": ["This field is required."]}},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get interview schedule details",
        description="Retrieve detailed information about a specific interview schedule",
        tags=["Interview Schedule"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "title": "First Round Interview",
                        "recruitment_request": {
                            "id": 1,
                            "code": "RR0001",
                            "name": "Senior Backend Developer Position",
                            "position_title": "Backend Developer",
                        },
                        "interview_type": "IN_PERSON",
                        "location": "Office Meeting Room A",
                        "time": "2025-10-25T10:00:00Z",
                        "note": "Please bring portfolio",
                        "interviewers": [
                            {
                                "id": 1,
                                "code": "MV001",
                                "fullname": "Nguyen Van A",
                                "branch_name": "Head Office",
                                "block_name": "Technology",
                                "department_name": "Engineering",
                                "position_name": "Senior HR Manager",
                            }
                        ],
                        "number_of_candidates": 1,
                        "created_at": "2025-10-22T03:00:00Z",
                        "updated_at": "2025-10-22T03:00:00Z",
                    },
                },
                response_only=True,
            )
        ],
    ),
    update=extend_schema(
        summary="Update interview schedule",
        description="Update interview schedule information. Candidates and interviewers should be updated via custom actions.",
        tags=["Interview Schedule"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "title": "First Round Interview - Updated",
                    "recruitment_request_id": 1,
                    "interview_type": "ONLINE",
                    "location": "Zoom Meeting",
                    "time": "2025-10-25T14:00:00Z",
                    "note": "Updated to online format",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "title": "First Round Interview - Updated",
                        "recruitment_request": {
                            "id": 1,
                            "code": "RR0001",
                            "name": "Senior Backend Developer Position",
                            "position_title": "Backend Developer",
                        },
                        "interview_type": "ONLINE",
                        "location": "Zoom Meeting",
                        "time": "2025-10-25T14:00:00Z",
                        "note": "Updated to online format",
                        "interviewers": [
                            {
                                "id": 1,
                                "code": "MV001",
                                "fullname": "Nguyen Van A",
                                "branch_name": "Head Office",
                                "block_name": "Technology",
                                "department_name": "Engineering",
                                "position_name": "Senior HR Manager",
                            }
                        ],
                        "number_of_candidates": 1,
                        "created_at": "2025-10-22T03:00:00Z",
                        "updated_at": "2025-10-22T03:05:00Z",
                    },
                },
                response_only=True,
            ),
        ],
    ),
    partial_update=extend_schema(
        summary="Partially update interview schedule",
        description="Partially update interview schedule information",
        tags=["Interview Schedule"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "time": "2025-10-25T15:00:00Z",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "title": "First Round Interview",
                        "recruitment_request": {
                            "id": 1,
                            "code": "RR0001",
                            "name": "Senior Backend Developer Position",
                            "position_title": "Backend Developer",
                        },
                        "interview_type": "IN_PERSON",
                        "location": "Office Meeting Room A",
                        "time": "2025-10-25T15:00:00Z",
                        "note": "Please bring portfolio",
                        "interviewers": [
                            {
                                "id": 1,
                                "code": "MV001",
                                "fullname": "Nguyen Van A",
                                "branch_name": "Head Office",
                                "block_name": "Technology",
                                "department_name": "Engineering",
                                "position_name": "Senior HR Manager",
                            }
                        ],
                        "number_of_candidates": 1,
                        "created_at": "2025-10-22T03:00:00Z",
                        "updated_at": "2025-10-22T03:10:00Z",
                    },
                },
                response_only=True,
            ),
        ],
    ),
    destroy=extend_schema(
        summary="Delete interview schedule",
        description="Remove an interview schedule from the system",
        tags=["Interview Schedule"],
        examples=[
            OpenApiExample(
                "Success",
                value={"success": True, "data": None},
                response_only=True,
            ),
        ],
    ),
)
class InterviewScheduleViewSet(TemplateActionMixin, AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for InterviewSchedule model"""

    queryset = (
        InterviewSchedule.objects.prefetch_related(
            "interview_candidates__recruitment_candidate",
            "interviewers",
        )
        .select_related(
            "recruitment_request",
        )
        .all()
    )
    serializer_class = InterviewScheduleSerializer
    filterset_class = InterviewScheduleFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["title", "location"]
    ordering_fields = ["title", "time", "created_at"]
    ordering = ["-time"]

    # Permission registration attributes
    module = "HRM"
    submodule = "Recruitment"
    permission_prefix = "interview_schedule"

    @extend_schema(
        summary="Preview interview invitation email",
        description="Generate a preview of the interview invitation email for this schedule",
        tags=["Interview Schedule"],
    )
    @action(detail=True, methods=["post"], url_path="send_interview_invite/preview")
    def send_interview_invite_preview(self, request, pk=None):
        """Preview interview invitation email for this schedule."""
        return self.preview_template_email("interview_invite", request, pk)

    @extend_schema(
        summary="Send interview invitation email",
        description="Send interview invitation email to candidates in this schedule and mark InterviewCandidate.email_sent_at",
        tags=["Interview Schedule"],
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="send_interview_invite/send",
        permission_classes=[CanSendMail],
    )
    def send_interview_invite_send(self, request, pk=None):
        """Send interview invitation email to candidates."""
        return self.send_template_email(
            "interview_invite",
            request,
            pk,
            on_success_callback=mark_interview_candidate_email_sent,
        )

    @extend_schema(
        summary="Update interviewers in interview schedule",
        description="Update the list of interviewers for the interview schedule. This replaces all existing interviewers with the provided list.",
        tags=["Interview Schedule"],
        request=UpdateInterviewersSerializer,
        examples=[
            OpenApiExample(
                "Request",
                value={"interviewer_ids": [1, 2]},
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "title": "First Round Interview",
                        "recruitment_request": {
                            "id": 1,
                            "code": "RR0001",
                            "name": "Senior Backend Developer Position",
                            "position_title": "Backend Developer",
                        },
                        "interview_type": "IN_PERSON",
                        "location": "Office Meeting Room A",
                        "time": "2025-10-25T10:00:00Z",
                        "note": "Please bring portfolio",
                        "interviewers": [
                            {
                                "id": 1,
                                "code": "MV001",
                                "fullname": "Nguyen Van A",
                                "branch_name": "Head Office",
                                "block_name": "Technology",
                                "department_name": "Engineering",
                                "position_name": "Senior HR Manager",
                            },
                            {
                                "id": 2,
                                "code": "MV002",
                                "fullname": "Le Thi D",
                                "branch_name": "Head Office",
                                "block_name": "Technology",
                                "department_name": "Engineering",
                                "position_name": "HR Specialist",
                            },
                        ],
                        "number_of_candidates": 1,
                        "created_at": "2025-10-22T03:00:00Z",
                        "updated_at": "2025-10-22T03:25:00Z",
                    },
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error",
                value={"success": False, "error": {"interviewer_ids": ["Invalid pk - object does not exist."]}},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    @action(detail=True, methods=["post"], url_path="update-interviewers")
    def update_interviewers(self, request, pk=None):
        """Custom action to update interviewers in interview schedule"""
        instance = self.get_object()
        serializer = UpdateInterviewersSerializer(data=request.data)

        if serializer.is_valid():
            interviewers = serializer.validated_data.get("interviewer_ids")
            instance.interviewers.set(interviewers)
            return Response(self.get_serializer(instance).data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
