from django.conf import settings
from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets import InterviewScheduleFilterSet
from apps.hrm.api.serializers import (
    InterviewScheduleExportSerializer,
    InterviewScheduleSerializer,
    UpdateInterviewersSerializer,
)
from apps.hrm.callbacks import mark_interview_candidate_email_sent
from apps.hrm.models import InterviewSchedule
from apps.mailtemplates.serializers import TemplatePreviewResponseSerializer
from apps.mailtemplates.services import TemplateValidationError
from apps.mailtemplates.view_mixins import EmailTemplateActionMixin
from libs import BaseModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter
from libs.export_xlsx import ExportXLSXMixin


@extend_schema_view(
    list=extend_schema(
        summary="List all interview schedules",
        description="Retrieve a paginated list of all interview schedules with support for filtering and search",
        tags=["4.7: Interview Schedule"],
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
        tags=["4.7: Interview Schedule"],
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
        tags=["4.7: Interview Schedule"],
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
        tags=["4.7: Interview Schedule"],
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
        tags=["4.7: Interview Schedule"],
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
        tags=["4.7: Interview Schedule"],
        examples=[
            OpenApiExample(
                "Success",
                value={"success": True, "data": None},
                response_only=True,
            ),
        ],
    ),
    export=extend_schema(
        tags=["4.7: Interview Schedule"],
    ),
)
class InterviewScheduleViewSet(ExportXLSXMixin, EmailTemplateActionMixin, AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for InterviewSchedule model"""

    queryset = (
        InterviewSchedule.objects.prefetch_related(
            "interview_candidates__recruitment_candidate",
            "interviewers",
        )
        .select_related(
            "recruitment_request",
            "recruitment_request__job_description",
        )
        .all()
    )
    serializer_class = InterviewScheduleSerializer
    filterset_class = InterviewScheduleFilterSet
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    search_fields = ["title", "location"]
    ordering_fields = ["title", "time", "created_at"]
    ordering = ["-time"]

    # Permission registration attributes
    module = "HRM"
    submodule = _("Recruitment")
    permission_prefix = "interview_schedule"

    @extend_schema(
        summary="Preview interview invitation email",
        description="Generate a preview of the interview invitation email for this schedule using the interview_invite email template",
        tags=["4.7: Interview Schedule"],
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "object",
                        "description": "Optional data overrides for template variables",
                        "properties": {
                            "candidate_name": {"type": "string", "description": "Candidate's full name"},
                            "position": {"type": "string", "description": "Position being interviewed for"},
                            "interview_date": {"type": "string", "format": "date", "description": "Interview date"},
                            "interview_time": {"type": "string", "description": "Interview time"},
                            "location": {
                                "type": "string",
                                "description": "Interview location or meeting link (optional)",
                            },
                        },
                    },
                },
            }
        },
        responses={
            200: TemplatePreviewResponseSerializer,
            400: {
                "description": "Invalid data or template rendering error",
                "content": {
                    "application/json": {
                        "example": {
                            "success": False,
                            "error": "Template rendering failed: 'candidate_name' is undefined",
                        }
                    }
                },
            },
            404: {
                "description": "Interview schedule not found",
                "content": {
                    "application/json": {
                        "example": {
                            "success": False,
                            "error": "Not found.",
                        }
                    }
                },
            },
        },
    )
    @action(detail=True, methods=["post"], url_path="interview_invite/preview")
    def interview_invite_preview(self, request, pk=None):
        """Preview interview invitation email for this schedule."""
        return self.preview_template_email("interview_invite", request, pk)

    @extend_schema(
        summary="Send interview invitation email",
        description="Send interview invitation email to candidates in this schedule. After successful delivery, the InterviewCandidate.email_sent_at field will be updated with the current timestamp",
        tags=["4.7: Interview Schedule"],
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "candidate_ids": {
                        "type": "array",
                        "description": "Optional list of candidate IDs to send emails to. If not provided, emails are sent to all candidates in the schedule",
                        "items": {"type": "integer"},
                    },
                    "subject": {
                        "type": "string",
                        "description": "Optional email subject (defaults to 'Interview Invitation - MaiVietLand')",
                    },
                },
            }
        },
        responses={
            202: {
                "description": "Email job created and queued for sending",
                "content": {
                    "application/json": {
                        "example": {
                            "success": True,
                            "data": {
                                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                                "total_recipients": 3,
                                "detail": "Email send job enqueued",
                            },
                        }
                    }
                },
            },
            400: {
                "description": "Invalid request data or template validation error",
                "content": {
                    "application/json": {
                        "example": {
                            "success": False,
                            "error": {"recipients": ["This field is required."]},
                        }
                    }
                },
            },
            404: {
                "description": "Interview schedule not found",
                "content": {
                    "application/json": {
                        "example": {
                            "success": False,
                            "error": "Not found.",
                        }
                    }
                },
            },
        },
    )
    @action(detail=True, methods=["post"], url_path="interview_invite/send")
    def interview_invite_send(self, request, pk=None):
        """Send interview invitation email to candidates."""
        return self.send_template_email(
            "interview_invite",
            request,
            pk,
            on_success_callback=mark_interview_candidate_email_sent,
        )

    def get_recipients(self, request, instance):
        """Get recipients for interview schedule email.

        For interview schedules, returns multiple recipients - one for each candidate.
        Supports filtering by candidate_ids if provided in the request.

        Args:
            request: Request object, may contain 'candidate_ids' list
            instance: InterviewSchedule instance

        Returns:
            List of recipient dicts with email, data, and callback_data
        """
        # Get candidate_ids filter from request if provided
        candidate_ids = request.data.get("candidate_ids")

        # Get all interview candidates for this schedule
        interview_candidates = instance.interview_candidates.select_related(
            "recruitment_candidate", "interview_schedule__recruitment_request"
        ).all()

        # Filter by candidate_ids if provided
        if candidate_ids is not None:
            interview_candidates = interview_candidates.filter(id__in=candidate_ids, email_sent_at__isnull=True)

        if not interview_candidates.exists():
            raise TemplateValidationError("No candidates found for this interview schedule")

        recipients = []
        for interview_candidate in interview_candidates:
            recipient = self.get_recipient_for_interview_candidate(request, interview_candidate)

            if not recipient:
                continue  # Skip candidates without email

            recipients.append(recipient)

        return recipients

    def get_recipient_for_interview_candidate(self, request, interview_candidate):
        """Get recipient dict for a specific InterviewCandidate."""
        candidate = interview_candidate.recruitment_candidate
        schedule = interview_candidate.interview_schedule

        if not candidate.email:
            return  # Skip candidates without email

        # Format interview time
        interview_time_str = (
            interview_candidate.interview_time.strftime("%H:%M") if interview_candidate.interview_time else ""
        )
        interview_date_str = (
            interview_candidate.interview_time.strftime("%Y-%m-%d") if interview_candidate.interview_time else ""
        )

        # Get position from recruitment request
        position_name = ""
        if schedule.recruitment_request:
            if (
                hasattr(schedule.recruitment_request, "job_description")
                and schedule.recruitment_request.job_description
            ):
                position_name = schedule.recruitment_request.job_description.position_title
            elif hasattr(schedule.recruitment_request, "position_title"):
                position_name = schedule.recruitment_request.position_title

        recipient_data = {
            "email": candidate.email,
            "data": {
                "candidate_name": candidate.name,
                "position": position_name,
                "interview_date": interview_date_str,
                "interview_time": interview_time_str,
                "location": schedule.location,
                "logo_image_url": settings.LOGO_URL,
            },
            "callback_data": {
                "interview_candidate_id": interview_candidate.id,
            },
        }

        user = request.user
        if getattr(user, "employee", None):
            employee = user.employee
            recipient_data["contact_fullname"] = employee.fullname
            if employee.phone:
                recipient_data["contact_phone"] = employee.phone
            if employee.position:
                recipient_data["contact_position"] = employee.position.name

        return recipient_data

    @extend_schema(
        summary="Update interviewers in interview schedule",
        description="Update the list of interviewers for the interview schedule. This replaces all existing interviewers with the provided list.",
        tags=["4.7: Interview Schedule"],
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

    def get_export_data(self, request):
        """Custom export data for InterviewSchedule.

        Exports the following fields:
        - title
        - recruitment_request__name
        - recruitment_request__job_description__position_title
        - recruitment_request__number_of_positions
        - time
        """
        queryset = self.filter_queryset(self.get_queryset())
        serializer = InterviewScheduleExportSerializer(queryset, many=True)
        data = serializer.data

        return {
            "sheets": [
                {
                    "name": "Interview Schedules",
                    "headers": [
                        "Title",
                        "Recruitment Request",
                        "Position Title",
                        "Number of Positions",
                        "Interview Time",
                    ],
                    "field_names": [
                        "title",
                        "recruitment_request__name",
                        "recruitment_request__job_description__position_title",
                        "recruitment_request__number_of_positions",
                        "time",
                    ],
                    "data": data,
                }
            ]
        }
