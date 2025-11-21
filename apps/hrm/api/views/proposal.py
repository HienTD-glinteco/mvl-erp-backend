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
from apps.hrm.api.filtersets.proposal import ProposalFilterSet
from apps.hrm.api.serializers.proposal import (
    ProposalApproveSerializer,
    ProposalRejectSerializer,
    ProposalSerializer,
)
from apps.hrm.constants import ProposalType
from apps.hrm.models import Proposal
from libs import BaseReadOnlyModelViewSet


@extend_schema_view(
    list=extend_schema(
        summary="List proposals",
        description="Retrieve a list of employee proposals with optional filtering by timesheet entry, type, and status",
        tags=["6.5: Proposals"],
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
                                "proposal_type": "complaint",
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
        summary="Get proposal details",
        description="Retrieve detailed information for a specific proposal",
        tags=["6.5: Proposals"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "complaint",
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
class ProposalViewSet(AuditLoggingMixin, BaseReadOnlyModelViewSet):
    """Read-only ViewSet for Proposal with custom approve and reject actions."""

    queryset = Proposal.objects.prefetch_related(
        "timesheet_entries",
        "timesheet_entries__timesheet_entry",
    ).all()
    serializer_class = ProposalSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = ProposalFilterSet
    ordering_fields = ["proposal_date", "created_at"]
    ordering = ["-proposal_date"]

    module = "HRM"
    submodule = "Proposal"
    permission_prefix = "proposal"

    @extend_schema(
        summary="Approve complaint proposal",
        description="Approve a complaint proposal and set the approved check-in/out times",
        request=ProposalApproveSerializer,
        responses={200: ProposalSerializer},
        tags=["6.5: Proposals"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "complaint",
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
    @action(detail=True, methods=["post"], url_path="approve-complaint")
    def approve_complaint(self, request, pk=None):
        """Approve a complaint proposal."""
        proposal = self.get_object()

        # Check if proposal is a complaint
        if proposal.proposal_type != ProposalType.TIMESHEET_ENTRY_COMPLAINT:
            return Response(
                {"detail": "This action is only applicable for complaint proposals"},
                status=status.HTTP_400_BAD_REQUEST,
            )

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
        tags=["6.5: Proposals"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "complaint",
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
    @action(detail=True, methods=["post"], url_path="reject-complaint")
    def reject_complaint(self, request, pk=None):
        """Reject a complaint proposal."""
        proposal = self.get_object()

        # Validate input and save
        serializer = ProposalRejectSerializer(proposal, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Return updated proposal
        return Response(ProposalSerializer(proposal).data)
