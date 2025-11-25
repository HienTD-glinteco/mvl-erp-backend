from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import (
    OpenApiExample,
    extend_schema,
    extend_schema_view,
)
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apps.audit_logging.api.mixins import AuditLoggingMixin
from apps.hrm.api.filtersets.proposal import (
    ProposalFilterSet,
    TimesheetEntryComplaintProposalFilterSet,
)
from apps.hrm.api.serializers.proposal import (
    ProposalApproveSerializer,
    ProposalRejectSerializer,
    ProposalSerializer,
    ProposalVerifierSerializer,
    ProposalVerifierVerifySerializer,
)
from apps.hrm.constants import ProposalType
from apps.hrm.models import Proposal, ProposalVerifier
from libs import BaseModelViewSet, BaseReadOnlyModelViewSet


class ProposalBaseViewSet(AuditLoggingMixin, BaseReadOnlyModelViewSet):
    """Base ViewSet for all Proposal types with common configuration."""

    serializer_class = ProposalSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = ProposalFilterSet
    ordering_fields = ["proposal_date", "created_at"]
    ordering = ["-proposal_date"]

    module = "HRM"
    submodule = "Proposal"

    # Subclasses must define this
    proposal_type: ProposalType = None  # type: ignore

    def get_queryset(self):
        """Filter queryset to only include proposals of the specific type."""
        queryset = Proposal.objects.prefetch_related(
            "timesheet_entries",
            "timesheet_entries__timesheet_entry",
            "created_by",
            "approved_by",
        )
        if self.proposal_type:
            queryset = queryset.filter(proposal_type=self.proposal_type)
        return queryset


@extend_schema_view(
    list=extend_schema(
        summary="List timesheet entry complaint proposals",
        description="Retrieve a list of timesheet entry complaint proposals with optional filtering",
        tags=["6.5.1: Timesheet Entry Complaint Proposals"],
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
                                "code": "DX000001",
                                "proposal_date": "2025-01-15",
                                "proposal_type": "timesheet_entry_complaint",
                                "proposal_status": "pending",
                                "complaint_reason": "Incorrect check-in time recorded",
                                "proposed_check_in_time": "08:00:00",
                                "proposed_check_out_time": "17:00:00",
                                "approved_check_in_time": None,
                                "approved_check_out_time": None,
                                "note": "",
                                "created_at": "2025-01-15T10:00:00Z",
                                "updated_at": "2025-01-15T10:00:00Z",
                            }
                        ],
                    },
                    "error": None,
                },
                response_only=True,
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get timesheet entry complaint proposal details",
        description="Retrieve detailed information for a specific timesheet entry complaint proposal",
        tags=["6.5.1: Timesheet Entry Complaint Proposals"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "timesheet_entry_complaint",
                        "proposal_status": "pending",
                        "complaint_reason": "Incorrect check-in time recorded",
                        "proposed_check_in_time": "08:00:00",
                        "proposed_check_out_time": "17:00:00",
                        "approved_check_in_time": None,
                        "approved_check_out_time": None,
                        "note": "",
                        "created_at": "2025-01-15T10:00:00Z",
                        "updated_at": "2025-01-15T10:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            ),
        ],
    ),
)
class ProposalTimesheetEntryComplaintViewSet(ProposalBaseViewSet):
    """ViewSet for Timesheet Entry Complaint proposals with approve and reject actions."""

    proposal_type = ProposalType.TIMESHEET_ENTRY_COMPLAINT
    filterset_class = TimesheetEntryComplaintProposalFilterSet
    permission_prefix = "proposal_timesheet_entry_complaint"

    @extend_schema(
        summary="Approve complaint proposal",
        description="Approve a complaint proposal and set the approved check-in/out times",
        request=ProposalApproveSerializer,
        responses={200: ProposalSerializer},
        tags=["6.5.1: Timesheet Entry Complaint Proposals"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "timesheet_entry_complaint",
                        "proposal_status": "approved",
                        "complaint_reason": "Incorrect check-in time recorded",
                        "proposed_check_in_time": "08:00:00",
                        "proposed_check_out_time": "17:00:00",
                        "approved_check_in_time": "08:00:00",
                        "approved_check_out_time": "17:00:00",
                        "note": "Approved by manager",
                        "created_at": "2025-01-15T10:00:00Z",
                        "updated_at": "2025-01-15T14:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error - Already processed",
                value={
                    "success": False,
                    "data": None,
                    "error": {"detail": "Proposal has already been processed"},
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        """Approve a complaint proposal."""
        proposal = self.get_object()

        # Validate input and save
        serializer = ProposalApproveSerializer(proposal, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Return updated proposal
        return Response(ProposalSerializer(proposal).data)

    @extend_schema(
        summary="Reject complaint proposal",
        description="Reject a complaint proposal with a required rejection reason",
        request=ProposalRejectSerializer,
        responses={200: ProposalSerializer},
        tags=["6.5.1: Timesheet Entry Complaint Proposals"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "timesheet_entry_complaint",
                        "proposal_status": "rejected",
                        "complaint_reason": "Incorrect check-in time recorded",
                        "proposed_check_in_time": "08:00:00",
                        "proposed_check_out_time": "17:00:00",
                        "approved_check_in_time": None,
                        "approved_check_out_time": None,
                        "note": "Not enough evidence provided",
                        "created_at": "2025-01-15T10:00:00Z",
                        "updated_at": "2025-01-15T14:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error - Missing note",
                value={
                    "success": False,
                    "data": None,
                    "error": {"note": ["Note is required when rejecting a proposal"]},
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        """Reject a complaint proposal."""
        proposal = self.get_object()

        # Validate input and save
        serializer = ProposalRejectSerializer(proposal, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Return updated proposal
        return Response(ProposalSerializer(proposal).data)


@extend_schema_view(
    list=extend_schema(
        summary="List post-maternity benefits proposals",
        description="Retrieve a list of post-maternity benefits proposals",
        tags=["6.5.2: Post-Maternity Benefits Proposals"],
    ),
    retrieve=extend_schema(
        summary="Get post-maternity benefits proposal details",
        description="Retrieve detailed information for a specific post-maternity benefits proposal",
        tags=["6.5.2: Post-Maternity Benefits Proposals"],
    ),
)
class ProposalPostMaternityBenefitsViewSet(ProposalBaseViewSet):
    """ViewSet for Post-Maternity Benefits proposals."""

    proposal_type = ProposalType.POST_MATERNITY_BENEFITS
    permission_prefix = "proposal_post_maternity_benefits"


@extend_schema_view(
    list=extend_schema(
        summary="List late exemption proposals",
        description="Retrieve a list of late exemption proposals",
        tags=["6.5.3: Late Exemption Proposals"],
    ),
    retrieve=extend_schema(
        summary="Get late exemption proposal details",
        description="Retrieve detailed information for a specific late exemption proposal",
        tags=["6.5.3: Late Exemption Proposals"],
    ),
)
class ProposalLateExemptionViewSet(ProposalBaseViewSet):
    """ViewSet for Late Exemption proposals."""

    proposal_type = ProposalType.LATE_EXEMPTION
    permission_prefix = "proposal_late_exemption"


@extend_schema_view(
    list=extend_schema(
        summary="List overtime work proposals",
        description="Retrieve a list of overtime work proposals",
        tags=["6.5.4: Overtime Work Proposals"],
    ),
    retrieve=extend_schema(
        summary="Get overtime work proposal details",
        description="Retrieve detailed information for a specific overtime work proposal",
        tags=["6.5.4: Overtime Work Proposals"],
    ),
)
class ProposalOvertimeWorkViewSet(ProposalBaseViewSet):
    """ViewSet for Overtime Work proposals."""

    proposal_type = ProposalType.OVERTIME_WORK
    permission_prefix = "proposal_overtime_work"


@extend_schema_view(
    list=extend_schema(
        summary="List paid leave proposals",
        description="Retrieve a list of paid leave proposals",
        tags=["6.5.5: Paid Leave Proposals"],
    ),
    retrieve=extend_schema(
        summary="Get paid leave proposal details",
        description="Retrieve detailed information for a specific paid leave proposal",
        tags=["6.5.5: Paid Leave Proposals"],
    ),
)
class ProposalPaidLeaveViewSet(ProposalBaseViewSet):
    """ViewSet for Paid Leave proposals."""

    proposal_type = ProposalType.PAID_LEAVE
    permission_prefix = "proposal_paid_leave"


@extend_schema_view(
    list=extend_schema(
        summary="List unpaid leave proposals",
        description="Retrieve a list of unpaid leave proposals",
        tags=["6.5.6: Unpaid Leave Proposals"],
    ),
    retrieve=extend_schema(
        summary="Get unpaid leave proposal details",
        description="Retrieve detailed information for a specific unpaid leave proposal",
        tags=["6.5.6: Unpaid Leave Proposals"],
    ),
)
class ProposalUnpaidLeaveViewSet(ProposalBaseViewSet):
    """ViewSet for Unpaid Leave proposals."""

    proposal_type = ProposalType.UNPAID_LEAVE
    permission_prefix = "proposal_unpaid_leave"


@extend_schema_view(
    list=extend_schema(
        summary="List maternity leave proposals",
        description="Retrieve a list of maternity leave proposals",
        tags=["6.5.7: Maternity Leave Proposals"],
    ),
    retrieve=extend_schema(
        summary="Get maternity leave proposal details",
        description="Retrieve detailed information for a specific maternity leave proposal",
        tags=["6.5.7: Maternity Leave Proposals"],
    ),
)
class ProposalMaternityLeaveViewSet(ProposalBaseViewSet):
    """ViewSet for Maternity Leave proposals."""

    proposal_type = ProposalType.MATERNITY_LEAVE
    permission_prefix = "proposal_maternity_leave"


@extend_schema_view(
    list=extend_schema(
        summary="List attendance exemption proposals",
        description="Retrieve a list of attendance exemption proposals",
        tags=["6.5.8: Attendance Exemption Proposals"],
    ),
    retrieve=extend_schema(
        summary="Get attendance exemption proposal details",
        description="Retrieve detailed information for a specific attendance exemption proposal",
        tags=["6.5.8: Attendance Exemption Proposals"],
    ),
)
class ProposalAttendanceExemptionViewSet(ProposalBaseViewSet):
    """ViewSet for Attendance Exemption proposals."""

    proposal_type = ProposalType.ATTENDANCE_EXEMPTION
    permission_prefix = "proposal_attendance_exemption"


@extend_schema_view(
    list=extend_schema(
        summary="List proposal verifiers",
        description="Retrieve a list of proposal verifiers with optional filtering",
        tags=["6.5.9: Proposal Verifiers"],
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
                                "proposal": 1,
                                "employee": 1,
                                "status": "not_verified",
                                "verified_time": None,
                                "note": None,
                                "created_at": "2025-01-15T10:00:00Z",
                                "updated_at": "2025-01-15T10:00:00Z",
                            }
                        ],
                    },
                    "error": None,
                },
                response_only=True,
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get proposal verifier details",
        description="Retrieve detailed information for a specific proposal verifier",
        tags=["6.5.9: Proposal Verifiers"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "proposal": 1,
                        "employee": 1,
                        "status": "not_verified",
                        "verified_time": None,
                        "note": None,
                        "created_at": "2025-01-15T10:00:00Z",
                        "updated_at": "2025-01-15T10:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            ),
        ],
    ),
    create=extend_schema(
        summary="Create proposal verifier",
        description="Create a new proposal verifier",
        tags=["6.5.9: Proposal Verifiers"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "proposal": 1,
                    "employee": 1,
                    "note": "Assigned as verifier",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "proposal": 1,
                        "employee": 1,
                        "status": "not_verified",
                        "verified_time": None,
                        "note": "Assigned as verifier",
                        "created_at": "2025-01-15T10:00:00Z",
                        "updated_at": "2025-01-15T10:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            ),
        ],
    ),
    update=extend_schema(
        summary="Update proposal verifier",
        description="Update a proposal verifier",
        tags=["6.5.9: Proposal Verifiers"],
    ),
    partial_update=extend_schema(
        summary="Partially update proposal verifier",
        description="Partially update a proposal verifier",
        tags=["6.5.9: Proposal Verifiers"],
    ),
    destroy=extend_schema(
        summary="Delete proposal verifier",
        description="Delete a proposal verifier",
        tags=["6.5.9: Proposal Verifiers"],
    ),
)
class ProposalVerifierViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for managing proposal verifiers."""

    queryset = ProposalVerifier.objects.select_related("proposal", "employee")
    serializer_class = ProposalVerifierSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = ["created_at", "verified_time"]
    ordering = ["-created_at"]

    module = "HRM"
    submodule = "ProposalVerifier"
    permission_prefix = "proposal_verifier"

    @extend_schema(
        summary="Verify proposal",
        description="Mark a proposal as verified. Only applicable for timesheet entry complaint proposals.",
        tags=["6.5.9: Proposal Verifiers"],
        request=ProposalVerifierVerifySerializer,
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "note": "Verified and approved",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "proposal": 1,
                        "employee": 1,
                        "status": "verified",
                        "verified_time": "2025-01-15T11:00:00Z",
                        "note": "Verified and approved",
                        "created_at": "2025-01-15T10:00:00Z",
                        "updated_at": "2025-01-15T11:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error - Invalid proposal type",
                value={
                    "success": False,
                    "data": None,
                    "error": {
                        "non_field_errors": ["Verification is only applicable for timesheet entry complaint proposals"]
                    },
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        """Verify a proposal. Only applicable for timesheet entry complaint proposals."""
        verifier = self.get_object()
        serializer = ProposalVerifierVerifySerializer(verifier, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(ProposalVerifierSerializer(verifier).data, status=status.HTTP_200_OK)
