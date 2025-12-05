from typing import List

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
    MeProposalFilterSet,
    MeProposalVerifierFilterSet,
    ProposalFilterSet,
    ProposalVerifierFilterSet,
)
from apps.hrm.api.serializers.proposal import (
    ProposalApproveSerializer,
    ProposalAssetAllocationExportXLSXSerializer,
    ProposalAssetAllocationSerializer,
    ProposalCombinedSerializer,
    ProposalExportXLSXSerializer,
    ProposalJobTransferExportXLSXSerializer,
    ProposalJobTransferSerializer,
    ProposalLateExemptionExportXLSXSerializer,
    ProposalLateExemptionSerializer,
    ProposalMaternityLeaveExportXLSXSerializer,
    ProposalMaternityLeaveSerializer,
    ProposalOvertimeWorkExportXLSXSerializer,
    ProposalOvertimeWorkSerializer,
    ProposalPaidLeaveExportXLSXSerializer,
    ProposalPaidLeaveSerializer,
    ProposalPostMaternityBenefitsExportXLSXSerializer,
    ProposalPostMaternityBenefitsSerializer,
    ProposalRejectSerializer,
    ProposalSerializer,
    ProposalTimesheetEntryComplaintApproveSerializer,
    ProposalTimesheetEntryComplaintExportXLSXSerializer,
    ProposalTimesheetEntryComplaintRejectSerializer,
    ProposalTimesheetEntryComplaintSerializer,
    ProposalUnpaidLeaveExportXLSXSerializer,
    ProposalUnpaidLeaveSerializer,
    ProposalVerifierNeedVerificationSerializer,
    ProposalVerifierSerializer,
    ProposalVerifierVerifySerializer,
)
from apps.hrm.constants import ProposalType
from apps.hrm.models import Proposal, ProposalVerifier
from libs import BaseModelViewSet, BaseReadOnlyModelViewSet
from libs.export_xlsx.mixins import ExportXLSXMixin


class ProposalMixin(AuditLoggingMixin, ExportXLSXMixin):
    queryset = Proposal.objects.all()
    serializer_class = ProposalSerializer  # Subclasses should override
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = ProposalFilterSet
    ordering_fields = ["proposal_date", "created_at"]
    ordering = ["-proposal_date"]

    module = "HRM"
    submodule = "Proposal"
    permission_prefix = "proposal"  # Subclasses should override

    # Subclasses must define this
    proposal_type: ProposalType = None  # type: ignore

    # Export serializer class - subclasses should override
    export_serializer_class = ProposalExportXLSXSerializer

    def get_select_related_fields(self) -> List[str]:
        """Get list of fields for select_related optimization."""
        return ["created_by", "approved_by"]

    def get_prefetch_related_fields(self) -> List[str]:
        """Get list of fields for prefetch_related optimization."""
        return []

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.proposal_type:
            queryset = queryset.filter(proposal_type=self.proposal_type)
        queryset = queryset.select_related(*self.get_select_related_fields()).prefetch_related(
            *self.get_prefetch_related_fields()
        )
        return queryset

    def get_serializer_class(self):
        """Return appropriate serializer class based on proposal type."""
        if self.action == "approve":
            return self.get_approve_serializer_class()
        elif self.action == "reject":
            return self.get_reject_serializer_class()
        elif self.action == "export":
            return self.get_export_serializer_class()
        return super().get_serializer_class()

    def get_approve_serializer_class(self):
        return ProposalApproveSerializer

    def get_reject_serializer_class(self):
        return ProposalRejectSerializer

    def get_export_serializer_class(self):
        """Return the export serializer class. Subclasses can override this method."""
        return self.export_serializer_class

    def get_export_data(self, request):
        """Return the data for XLSX export."""
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        name = str(Proposal._meta.verbose_name)
        if self.proposal_type:
            name = f"{name} {self.proposal_type.label}"
        data = {
            "sheets": [
                {
                    "name": name,
                    "headers": [str(field.label) for field in serializer.child.fields.values()],
                    "field_names": list(serializer.child.fields.keys()),
                    "data": serializer.data,
                }
            ]
        }
        return data

    def _get_export_filename(self):
        name = str(Proposal._meta.verbose_name)
        if self.proposal_type:
            name = f"{name} {self.proposal_type.label}"
        return f"{name} export.xlsx"

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        """Approve a proposal."""
        proposal = self.get_object()

        # Validate input and save
        serializer = self.get_serializer(proposal, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Return updated proposal with timesheet entry
        return Response(self.serializer_class(proposal).data)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        """Reject a proposal."""
        proposal = self.get_object()

        # Validate input and save
        serializer = self.get_serializer(proposal, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Return updated proposal with timesheet entry
        return Response(self.serializer_class(proposal).data)


@extend_schema_view(
    list=extend_schema(
        summary="List all proposals",
        description="Retrieve a list of all proposals regardless of type with optional filtering",
        tags=["9.2: Proposals"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "count": 2,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": 1,
                                "code": "DX000001",
                                "proposal_date": "2025-01-15",
                                "proposal_type": "timesheet_entry_complaint",
                                "colored_proposal_status": {"value": "pending", "variant": "yellow"},
                                "timesheet_entry_complaint_complaint_reason": "Incorrect check-in time recorded",
                                "proposed_check_in_time": "08:00:00",
                                "proposed_check_out_time": "17:00:00",
                                "approved_check_in_time": None,
                                "approved_check_out_time": None,
                                "note": "",
                                "created_at": "2025-01-15T10:00:00Z",
                                "updated_at": "2025-01-15T10:00:00Z",
                            },
                            {
                                "id": 2,
                                "code": "DX000002",
                                "proposal_date": "2025-01-16",
                                "proposal_type": "paid_leave",
                                "colored_proposal_status": {"value": "approved", "variant": "green"},
                                "timesheet_entry_complaint_complaint_reason": None,
                                "proposed_check_in_time": None,
                                "proposed_check_out_time": None,
                                "approved_check_in_time": None,
                                "approved_check_out_time": None,
                                "note": "Annual leave",
                                "created_at": "2025-01-16T09:00:00Z",
                                "updated_at": "2025-01-16T14:00:00Z",
                            },
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
        tags=["9.2: Proposals"],
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
                        "colored_proposal_status": {"value": "pending", "variant": "yellow"},
                        "timesheet_entry_complaint_complaint_reason": "Incorrect check-in time recorded",
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
class ProposalViewSet(ProposalMixin, BaseReadOnlyModelViewSet):
    """Base ViewSet for specific Proposal types with common configuration."""

    def get_prefetch_related_fields(self) -> List[str]:
        return ["timesheet_entries", "timesheet_entries__timesheet_entry"]

    @extend_schema(
        summary="Approve proposal",
        description="Approve a proposal",
        request=ProposalApproveSerializer,
        responses={200: ProposalSerializer},
        tags=["9.2: Proposals"],
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
                        "colored_proposal_status": {"value": "approved", "variant": "green"},
                        "timesheet_entry_complaint_complaint_reason": "Incorrect check-in time recorded",
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
        return super().approve(request, pk)

    @extend_schema(
        summary="Reject proposal",
        description="Reject a proposal with a required rejection reason",
        request=ProposalRejectSerializer,
        responses={200: ProposalSerializer},
        tags=["9.2: Proposals"],
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
                        "colored_proposal_status": {"value": "rejected", "variant": "red"},
                        "timesheet_entry_complaint_complaint_reason": "Incorrect check-in time recorded",
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
                    "error": {"note": ["This field is required."]},
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        return super().reject(request, pk)

    @extend_schema(exclude=True)
    def export(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)


class MeProposalViewSet(ProposalViewSet):
    """ViewSet for current user's proposals."""

    filterset_class = MeProposalFilterSet
    serializer_class = ProposalCombinedSerializer

    def get_queryset(self):
        return super().get_queryset().filter(created_by=self.request.user.employee)


@extend_schema_view(
    list=extend_schema(
        summary="List timesheet entry complaint proposals",
        description="Retrieve a list of timesheet entry complaint proposals with optional filtering",
        tags=["6.8: Timesheet Entry Complaint Proposals"],
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
                                "colored_proposal_status": {"value": "pending", "variant": "yellow"},
                                "timesheet_entry_complaint_complaint_reason": "Incorrect check-in time recorded",
                                "proposed_check_in_time": "08:00:00",
                                "proposed_check_out_time": "17:00:00",
                                "approved_check_in_time": None,
                                "approved_check_out_time": None,
                                "note": "",
                                "created_at": "2025-01-15T10:00:00Z",
                                "updated_at": "2025-01-15T10:00:00Z",
                                "timesheet_entry_id": 1,
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
        tags=["6.8: Timesheet Entry Complaint Proposals"],
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
                        "colored_proposal_status": {"value": "pending", "variant": "yellow"},
                        "timesheet_entry_complaint_complaint_reason": "Incorrect check-in time recorded",
                        "proposed_check_in_time": "08:00:00",
                        "proposed_check_out_time": "17:00:00",
                        "approved_check_in_time": None,
                        "approved_check_out_time": None,
                        "note": "",
                        "created_at": "2025-01-15T10:00:00Z",
                        "updated_at": "2025-01-15T10:00:00Z",
                        "timesheet_entry_id": 1,
                    },
                    "error": None,
                },
                response_only=True,
            ),
        ],
    ),
)
class ProposalTimesheetEntryComplaintViewSet(ProposalMixin, BaseReadOnlyModelViewSet):
    """ViewSet for Timesheet Entry Complaint proposals with approve and reject actions."""

    proposal_type = ProposalType.TIMESHEET_ENTRY_COMPLAINT
    serializer_class = ProposalTimesheetEntryComplaintSerializer
    permission_prefix = "proposal_timesheet_entry_complaint"
    export_serializer_class = ProposalTimesheetEntryComplaintExportXLSXSerializer

    def get_prefetch_related_fields(self) -> List[str]:
        return ["timesheet_entries", "timesheet_entries__timesheet_entry"]

    def get_approve_serializer_class(self):
        return ProposalTimesheetEntryComplaintApproveSerializer

    def get_reject_serializer_class(self):
        return ProposalTimesheetEntryComplaintRejectSerializer

    @extend_schema(
        summary="Approve complaint proposal",
        description="Approve a complaint proposal and set the approved check-in/out times",
        request=ProposalTimesheetEntryComplaintApproveSerializer,
        responses={200: ProposalTimesheetEntryComplaintSerializer},
        tags=["6.8: Timesheet Entry Complaint Proposals"],
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
                        "colored_proposal_status": {"value": "approved", "variant": "green"},
                        "timesheet_entry_complaint_complaint_reason": "Incorrect check-in time recorded",
                        "proposed_check_in_time": "08:00:00",
                        "proposed_check_out_time": "17:00:00",
                        "approved_check_in_time": "08:00:00",
                        "approved_check_out_time": "17:00:00",
                        "note": "Approved by manager",
                        "created_at": "2025-01-15T10:00:00Z",
                        "updated_at": "2025-01-15T14:00:00Z",
                        "timesheet_entry_id": 1,
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
        return super().approve(request, pk)

    @extend_schema(
        summary="Reject complaint proposal",
        description="Reject a complaint proposal with a required rejection reason",
        request=ProposalTimesheetEntryComplaintRejectSerializer,
        responses={200: ProposalTimesheetEntryComplaintSerializer},
        tags=["6.8: Timesheet Entry Complaint Proposals"],
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
                        "colored_proposal_status": {"value": "rejected", "variant": "red"},
                        "timesheet_entry_complaint_complaint_reason": "Incorrect check-in time recorded",
                        "proposed_check_in_time": "08:00:00",
                        "proposed_check_out_time": "17:00:00",
                        "approved_check_in_time": None,
                        "approved_check_out_time": None,
                        "note": "Not enough evidence provided",
                        "created_at": "2025-01-15T10:00:00Z",
                        "updated_at": "2025-01-15T14:00:00Z",
                        "timesheet_entry_id": 1,
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
        return super().reject(request, pk)


@extend_schema_view(
    list=extend_schema(
        summary="List post-maternity benefits proposals",
        description="Retrieve a list of post-maternity benefits proposals",
        tags=["9.2.2: Post-Maternity Benefits Proposals"],
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
                                "proposal_type": "post_maternity_benefits",
                                "colored_proposal_status": {"value": "pending", "variant": "yellow"},
                                "post_maternity_benefits_start_date": "2025-02-01",
                                "post_maternity_benefits_end_date": "2025-03-01",
                                "note": "Request for post-maternity work schedule",
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
        summary="Get post-maternity benefits proposal details",
        description="Retrieve detailed information for a specific post-maternity benefits proposal",
        tags=["9.2.2: Post-Maternity Benefits Proposals"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "post_maternity_benefits",
                        "colored_proposal_status": {"value": "pending", "variant": "yellow"},
                        "post_maternity_benefits_start_date": "2025-02-01",
                        "post_maternity_benefits_end_date": "2025-03-01",
                        "note": "Request for post-maternity work schedule",
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
        summary="Create post-maternity benefits proposal",
        description="Create a new post-maternity benefits proposal",
        tags=["9.2.2: Post-Maternity Benefits Proposals"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "post_maternity_benefits_start_date": "2025-02-01",
                    "post_maternity_benefits_end_date": "2025-03-01",
                    "note": "Request for post-maternity work schedule",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "post_maternity_benefits",
                        "colored_proposal_status": {"value": "pending", "variant": "yellow"},
                        "post_maternity_benefits_start_date": "2025-02-01",
                        "post_maternity_benefits_end_date": "2025-03-01",
                        "note": "Request for post-maternity work schedule",
                        "created_at": "2025-01-15T10:00:00Z",
                        "updated_at": "2025-01-15T10:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error - Missing fields",
                value={
                    "success": False,
                    "data": None,
                    "error": {
                        "post_maternity_benefits_start_date": ["Post-maternity benefits start date is required"],
                        "post_maternity_benefits_end_date": ["Post-maternity benefits end date is required"],
                    },
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    update=extend_schema(
        summary="Update post-maternity benefits proposal",
        description="Update a post-maternity benefits proposal",
        tags=["9.2.2: Post-Maternity Benefits Proposals"],
    ),
    partial_update=extend_schema(
        summary="Partially update post-maternity benefits proposal",
        description="Partially update a post-maternity benefits proposal",
        tags=["9.2.2: Post-Maternity Benefits Proposals"],
    ),
    destroy=extend_schema(
        summary="Delete post-maternity benefits proposal",
        description="Delete a post-maternity benefits proposal",
        tags=["9.2.2: Post-Maternity Benefits Proposals"],
    ),
    export=extend_schema(
        tags=["9.2.2: Post-Maternity Benefits Proposals"],
    ),
)
class ProposalPostMaternityBenefitsViewSet(ProposalMixin, BaseModelViewSet):
    """ViewSet for Post-Maternity Benefits proposals."""

    proposal_type = ProposalType.POST_MATERNITY_BENEFITS
    serializer_class = ProposalPostMaternityBenefitsSerializer
    permission_prefix = "proposal_post_maternity_benefits"
    export_serializer_class = ProposalPostMaternityBenefitsExportXLSXSerializer

    @extend_schema(
        summary="Approve post-maternity benefits proposal",
        description="Approve a post-maternity benefits proposal",
        request=ProposalApproveSerializer,
        responses={200: ProposalPostMaternityBenefitsSerializer},
        tags=["9.2.2: Post-Maternity Benefits Proposals"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "post_maternity_benefits",
                        "colored_proposal_status": {"value": "approved", "variant": "green"},
                        "post_maternity_benefits_start_date": "2025-02-01",
                        "post_maternity_benefits_end_date": "2025-03-01",
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
        return super().approve(request, pk)

    @extend_schema(
        summary="Reject post-maternity benefits proposal",
        description="Reject a post-maternity benefits proposal with a required rejection reason",
        request=ProposalRejectSerializer,
        responses={200: ProposalPostMaternityBenefitsSerializer},
        tags=["9.2.2: Post-Maternity Benefits Proposals"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "post_maternity_benefits",
                        "colored_proposal_status": {"value": "rejected", "variant": "red"},
                        "post_maternity_benefits_start_date": "2025-02-01",
                        "post_maternity_benefits_end_date": "2025-03-01",
                        "note": "Request does not meet policy requirements",
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
                    "error": {"note": ["This field is required."]},
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        return super().reject(request, pk)


@extend_schema_view(
    list=extend_schema(
        summary="List late exemption proposals",
        description="Retrieve a list of late exemption proposals",
        tags=["9.2.3: Late Exemption Proposals"],
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
                                "proposal_type": "late_exemption",
                                "colored_proposal_status": {"value": "pending", "variant": "yellow"},
                                "late_exemption_start_date": "2025-02-01",
                                "late_exemption_end_date": "2025-02-28",
                                "late_exemption_minutes": 30,
                                "note": "Request for late arrival exemption",
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
        summary="Get late exemption proposal details",
        description="Retrieve detailed information for a specific late exemption proposal",
        tags=["9.2.3: Late Exemption Proposals"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "late_exemption",
                        "colored_proposal_status": {"value": "pending", "variant": "yellow"},
                        "late_exemption_start_date": "2025-02-01",
                        "late_exemption_end_date": "2025-02-28",
                        "late_exemption_minutes": 30,
                        "note": "Request for late arrival exemption",
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
        summary="Create late exemption proposal",
        description="Create a new late exemption proposal",
        tags=["9.2.3: Late Exemption Proposals"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "late_exemption_start_date": "2025-02-01",
                    "late_exemption_end_date": "2025-02-28",
                    "late_exemption_minutes": 30,
                    "note": "Request for late arrival exemption",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "late_exemption",
                        "colored_proposal_status": {"value": "pending", "variant": "yellow"},
                        "late_exemption_start_date": "2025-02-01",
                        "late_exemption_end_date": "2025-02-28",
                        "late_exemption_minutes": 30,
                        "note": "Request for late arrival exemption",
                        "created_at": "2025-01-15T10:00:00Z",
                        "updated_at": "2025-01-15T10:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error - Missing fields",
                value={
                    "success": False,
                    "data": None,
                    "error": {
                        "late_exemption_start_date": ["Late exemption start date is required"],
                        "late_exemption_end_date": ["Late exemption end date is required"],
                        "late_exemption_minutes": ["Late exemption minutes is required"],
                    },
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    update=extend_schema(
        summary="Update late exemption proposal",
        description="Update a late exemption proposal",
        tags=["9.2.3: Late Exemption Proposals"],
    ),
    partial_update=extend_schema(
        summary="Partially update late exemption proposal",
        description="Partially update a late exemption proposal",
        tags=["9.2.3: Late Exemption Proposals"],
    ),
    destroy=extend_schema(
        summary="Delete late exemption proposal",
        description="Delete a late exemption proposal",
        tags=["9.2.3: Late Exemption Proposals"],
    ),
    export=extend_schema(
        tags=["9.2.3: Late Exemption Proposals"],
    ),
)
class ProposalLateExemptionViewSet(ProposalMixin, BaseModelViewSet):
    """ViewSet for Late Exemption proposals."""

    proposal_type = ProposalType.LATE_EXEMPTION
    serializer_class = ProposalLateExemptionSerializer
    permission_prefix = "proposal_late_exemption"
    export_serializer_class = ProposalLateExemptionExportXLSXSerializer

    @extend_schema(
        summary="Approve late exemption proposal",
        description="Approve a late exemption proposal",
        request=ProposalApproveSerializer,
        responses={200: ProposalLateExemptionSerializer},
        tags=["9.2.3: Late Exemption Proposals"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "late_exemption",
                        "colored_proposal_status": {"value": "approved", "variant": "green"},
                        "late_exemption_start_date": "2025-02-01",
                        "late_exemption_end_date": "2025-02-28",
                        "late_exemption_minutes": 30,
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
        return super().approve(request, pk)

    @extend_schema(
        summary="Reject late exemption proposal",
        description="Reject a late exemption proposal with a required rejection reason",
        request=ProposalRejectSerializer,
        responses={200: ProposalLateExemptionSerializer},
        tags=["9.2.3: Late Exemption Proposals"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "late_exemption",
                        "colored_proposal_status": {"value": "rejected", "variant": "red"},
                        "late_exemption_start_date": "2025-02-01",
                        "late_exemption_end_date": "2025-02-28",
                        "late_exemption_minutes": 30,
                        "note": "Late exemption not justified",
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
                    "error": {"note": ["This field is required."]},
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        return super().reject(request, pk)


@extend_schema_view(
    list=extend_schema(
        summary="List overtime work proposals",
        description="Retrieve a list of overtime work proposals",
        tags=["9.2.4: Overtime Work Proposals"],
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
                                "proposal_type": "overtime_work",
                                "colored_proposal_status": {"value": "pending", "variant": "yellow"},
                                "overtime_entries": [
                                    {
                                        "id": 1,
                                        "date": "2025-01-15",
                                        "start_time": "18:00:00",
                                        "end_time": "21:00:00",
                                        "description": "Project deadline",
                                        "duration_hours": 3.0,
                                    }
                                ],
                                "note": "Overtime for project deadline",
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
        summary="Get overtime work proposal details",
        description="Retrieve detailed information for a specific overtime work proposal",
        tags=["9.2.4: Overtime Work Proposals"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "overtime_work",
                        "colored_proposal_status": {"value": "pending", "variant": "yellow"},
                        "overtime_entries": [
                            {
                                "id": 1,
                                "date": "2025-01-15",
                                "start_time": "18:00:00",
                                "end_time": "21:00:00",
                                "description": "Project deadline",
                                "duration_hours": 3.0,
                            }
                        ],
                        "note": "Overtime for project deadline",
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
        summary="Create overtime work proposal",
        description="Create a new overtime work proposal with one or more overtime entries",
        tags=["9.2.4: Overtime Work Proposals"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "entries": [
                        {
                            "date": "2025-01-15",
                            "start_time": "18:00:00",
                            "end_time": "21:00:00",
                            "description": "Project deadline work",
                        },
                        {
                            "date": "2025-01-16",
                            "start_time": "19:00:00",
                            "end_time": "22:00:00",
                            "description": "Continue project work",
                        },
                    ],
                    "note": "Overtime for project deadline",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "overtime_work",
                        "colored_proposal_status": {"value": "pending", "variant": "yellow"},
                        "overtime_entries": [
                            {
                                "id": 1,
                                "date": "2025-01-15",
                                "start_time": "18:00:00",
                                "end_time": "21:00:00",
                                "description": "Project deadline work",
                                "duration_hours": 3.0,
                            },
                            {
                                "id": 2,
                                "date": "2025-01-16",
                                "start_time": "19:00:00",
                                "end_time": "22:00:00",
                                "description": "Continue project work",
                                "duration_hours": 3.0,
                            },
                        ],
                        "note": "Overtime for project deadline",
                        "created_at": "2025-01-15T10:00:00Z",
                        "updated_at": "2025-01-15T10:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error - Missing entries",
                value={
                    "success": False,
                    "data": None,
                    "error": {
                        "entries": ["At least one overtime entry is required"],
                    },
                },
                response_only=True,
                status_codes=["400"],
            ),
            OpenApiExample(
                "Error - Invalid time range",
                value={
                    "success": False,
                    "data": None,
                    "error": {
                        "entries": [{"end_time": ["End time must be after start time"]}],
                    },
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    update=extend_schema(
        summary="Update overtime work proposal",
        description="Update an overtime work proposal",
        tags=["9.2.4: Overtime Work Proposals"],
    ),
    partial_update=extend_schema(
        summary="Partially update overtime work proposal",
        description="Partially update an overtime work proposal",
        tags=["9.2.4: Overtime Work Proposals"],
    ),
    destroy=extend_schema(
        summary="Delete overtime work proposal",
        description="Delete an overtime work proposal",
        tags=["9.2.4: Overtime Work Proposals"],
    ),
    export=extend_schema(
        tags=["9.2.4: Overtime Work Proposals"],
    ),
)
class ProposalOvertimeWorkViewSet(ProposalMixin, BaseModelViewSet):
    """ViewSet for Overtime Work proposals."""

    proposal_type = ProposalType.OVERTIME_WORK
    serializer_class = ProposalOvertimeWorkSerializer
    permission_prefix = "proposal_overtime_work"
    export_serializer_class = ProposalOvertimeWorkExportXLSXSerializer

    def get_prefetch_related_fields(self) -> List[str]:
        return ["overtime_entries"]

    @extend_schema(
        summary="Approve overtime work proposal",
        description="Approve an overtime work proposal",
        request=ProposalApproveSerializer,
        responses={200: ProposalOvertimeWorkSerializer},
        tags=["9.2.4: Overtime Work Proposals"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "overtime_work",
                        "colored_proposal_status": {"value": "approved", "variant": "green"},
                        "overtime_entries": [
                            {
                                "id": 1,
                                "date": "2025-01-15",
                                "start_time": "18:00:00",
                                "end_time": "21:00:00",
                                "description": "Project deadline",
                                "duration_hours": 3.0,
                            }
                        ],
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
        return super().approve(request, pk)

    @extend_schema(
        summary="Reject overtime work proposal",
        description="Reject an overtime work proposal with a required rejection reason",
        request=ProposalRejectSerializer,
        responses={200: ProposalOvertimeWorkSerializer},
        tags=["9.2.4: Overtime Work Proposals"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "overtime_work",
                        "colored_proposal_status": {"value": "rejected", "variant": "red"},
                        "overtime_entries": [
                            {
                                "id": 1,
                                "date": "2025-01-15",
                                "start_time": "18:00:00",
                                "end_time": "21:00:00",
                                "description": "Project deadline",
                                "duration_hours": 3.0,
                            }
                        ],
                        "note": "Overtime not approved due to budget constraints",
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
                    "error": {"note": ["This field is required."]},
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        return super().reject(request, pk)


@extend_schema_view(
    list=extend_schema(
        summary="List paid leave proposals",
        description="Retrieve a list of paid leave proposals",
        tags=["9.2.5: Paid Leave Proposals"],
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
                                "proposal_type": "paid_leave",
                                "colored_proposal_status": {"value": "pending", "variant": "yellow"},
                                "paid_leave_start_date": "2025-02-01",
                                "paid_leave_end_date": "2025-02-05",
                                "paid_leave_shift": "full_day",
                                "paid_leave_reason": "Family vacation",
                                "note": "Annual leave",
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
        summary="Get paid leave proposal details",
        description="Retrieve detailed information for a specific paid leave proposal",
        tags=["9.2.5: Paid Leave Proposals"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "paid_leave",
                        "colored_proposal_status": {"value": "pending", "variant": "yellow"},
                        "paid_leave_start_date": "2025-02-01",
                        "paid_leave_end_date": "2025-02-05",
                        "paid_leave_shift": "full_day",
                        "paid_leave_reason": "Family vacation",
                        "note": "Annual leave",
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
        summary="Create paid leave proposal",
        description="Create a new paid leave proposal",
        tags=["9.2.5: Paid Leave Proposals"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "paid_leave_start_date": "2025-02-01",
                    "paid_leave_end_date": "2025-02-05",
                    "paid_leave_shift": "full_day",
                    "paid_leave_reason": "Family vacation",
                    "note": "Annual leave",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "paid_leave",
                        "colored_proposal_status": {"value": "pending", "variant": "yellow"},
                        "paid_leave_start_date": "2025-02-01",
                        "paid_leave_end_date": "2025-02-05",
                        "paid_leave_shift": "full_day",
                        "paid_leave_reason": "Family vacation",
                        "note": "Annual leave",
                        "created_at": "2025-01-15T10:00:00Z",
                        "updated_at": "2025-01-15T10:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error - Invalid date range",
                value={
                    "success": False,
                    "data": None,
                    "error": {
                        "paid_leave_end_date": ["Paid leave end date must be on or after start date"],
                    },
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    update=extend_schema(
        summary="Update paid leave proposal",
        description="Update a paid leave proposal",
        tags=["9.2.5: Paid Leave Proposals"],
    ),
    partial_update=extend_schema(
        summary="Partially update paid leave proposal",
        description="Partially update a paid leave proposal",
        tags=["9.2.5: Paid Leave Proposals"],
    ),
    destroy=extend_schema(
        summary="Delete paid leave proposal",
        description="Delete a paid leave proposal",
        tags=["9.2.5: Paid Leave Proposals"],
    ),
    export=extend_schema(
        tags=["9.2.5: Paid Leave Proposals"],
    ),
)
class ProposalPaidLeaveViewSet(ProposalMixin, BaseModelViewSet):
    """ViewSet for Paid Leave proposals."""

    proposal_type = ProposalType.PAID_LEAVE
    serializer_class = ProposalPaidLeaveSerializer
    permission_prefix = "proposal_paid_leave"
    export_serializer_class = ProposalPaidLeaveExportXLSXSerializer

    @extend_schema(
        summary="Approve paid leave proposal",
        description="Approve a paid leave proposal",
        request=ProposalApproveSerializer,
        responses={200: ProposalPaidLeaveSerializer},
        tags=["9.2.5: Paid Leave Proposals"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "paid_leave",
                        "colored_proposal_status": {"value": "approved", "variant": "green"},
                        "paid_leave_start_date": "2025-02-01",
                        "paid_leave_end_date": "2025-02-05",
                        "paid_leave_shift": "full_day",
                        "paid_leave_reason": "Family vacation",
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
        return super().approve(request, pk)

    @extend_schema(
        summary="Reject paid leave proposal",
        description="Reject a paid leave proposal with a required rejection reason",
        request=ProposalRejectSerializer,
        responses={200: ProposalPaidLeaveSerializer},
        tags=["9.2.5: Paid Leave Proposals"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "paid_leave",
                        "colored_proposal_status": {"value": "rejected", "variant": "red"},
                        "paid_leave_start_date": "2025-02-01",
                        "paid_leave_end_date": "2025-02-05",
                        "paid_leave_shift": "full_day",
                        "paid_leave_reason": "Family vacation",
                        "note": "Leave request conflicts with project deadline",
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
                    "error": {"note": ["This field is required."]},
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        return super().reject(request, pk)


@extend_schema_view(
    list=extend_schema(
        summary="List unpaid leave proposals",
        description="Retrieve a list of unpaid leave proposals",
        tags=["9.2.6: Unpaid Leave Proposals"],
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
                                "proposal_type": "unpaid_leave",
                                "colored_proposal_status": {"value": "pending", "variant": "yellow"},
                                "unpaid_leave_start_date": "2025-02-01",
                                "unpaid_leave_end_date": "2025-02-05",
                                "unpaid_leave_shift": "full_day",
                                "unpaid_leave_reason": "Personal matters",
                                "note": "Unpaid leave request",
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
        summary="Get unpaid leave proposal details",
        description="Retrieve detailed information for a specific unpaid leave proposal",
        tags=["9.2.6: Unpaid Leave Proposals"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "unpaid_leave",
                        "colored_proposal_status": {"value": "pending", "variant": "yellow"},
                        "unpaid_leave_start_date": "2025-02-01",
                        "unpaid_leave_end_date": "2025-02-05",
                        "unpaid_leave_shift": "full_day",
                        "unpaid_leave_reason": "Personal matters",
                        "note": "Unpaid leave request",
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
        summary="Create unpaid leave proposal",
        description="Create a new unpaid leave proposal",
        tags=["9.2.6: Unpaid Leave Proposals"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "unpaid_leave_start_date": "2025-02-01",
                    "unpaid_leave_end_date": "2025-02-05",
                    "unpaid_leave_shift": "full_day",
                    "unpaid_leave_reason": "Personal matters",
                    "note": "Unpaid leave request",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "unpaid_leave",
                        "colored_proposal_status": {"value": "pending", "variant": "yellow"},
                        "unpaid_leave_start_date": "2025-02-01",
                        "unpaid_leave_end_date": "2025-02-05",
                        "unpaid_leave_shift": "full_day",
                        "unpaid_leave_reason": "Personal matters",
                        "note": "Unpaid leave request",
                        "created_at": "2025-01-15T10:00:00Z",
                        "updated_at": "2025-01-15T10:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error - Invalid date range",
                value={
                    "success": False,
                    "data": None,
                    "error": {
                        "unpaid_leave_end_date": ["Unpaid leave end date must be on or after start date"],
                    },
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    update=extend_schema(
        summary="Update unpaid leave proposal",
        description="Update an unpaid leave proposal",
        tags=["9.2.6: Unpaid Leave Proposals"],
    ),
    partial_update=extend_schema(
        summary="Partially update unpaid leave proposal",
        description="Partially update an unpaid leave proposal",
        tags=["9.2.6: Unpaid Leave Proposals"],
    ),
    destroy=extend_schema(
        summary="Delete unpaid leave proposal",
        description="Delete an unpaid leave proposal",
        tags=["9.2.6: Unpaid Leave Proposals"],
    ),
    export=extend_schema(
        tags=["9.2.6: Unpaid Leave Proposals"],
    ),
)
class ProposalUnpaidLeaveViewSet(ProposalMixin, BaseModelViewSet):
    """ViewSet for Unpaid Leave proposals."""

    proposal_type = ProposalType.UNPAID_LEAVE
    serializer_class = ProposalUnpaidLeaveSerializer
    permission_prefix = "proposal_unpaid_leave"
    export_serializer_class = ProposalUnpaidLeaveExportXLSXSerializer

    @extend_schema(
        summary="Approve unpaid leave proposal",
        description="Approve an unpaid leave proposal",
        request=ProposalApproveSerializer,
        responses={200: ProposalUnpaidLeaveSerializer},
        tags=["9.2.6: Unpaid Leave Proposals"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "unpaid_leave",
                        "colored_proposal_status": {"value": "approved", "variant": "green"},
                        "unpaid_leave_start_date": "2025-02-01",
                        "unpaid_leave_end_date": "2025-02-05",
                        "unpaid_leave_shift": "full_day",
                        "unpaid_leave_reason": "Personal matters",
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
        return super().approve(request, pk)

    @extend_schema(
        summary="Reject unpaid leave proposal",
        description="Reject an unpaid leave proposal with a required rejection reason",
        request=ProposalRejectSerializer,
        responses={200: ProposalUnpaidLeaveSerializer},
        tags=["9.2.6: Unpaid Leave Proposals"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "unpaid_leave",
                        "colored_proposal_status": {"value": "rejected", "variant": "red"},
                        "unpaid_leave_start_date": "2025-02-01",
                        "unpaid_leave_end_date": "2025-02-05",
                        "unpaid_leave_shift": "full_day",
                        "unpaid_leave_reason": "Personal matters",
                        "note": "Leave request not approved due to staffing requirements",
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
                    "error": {"note": ["This field is required."]},
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        return super().reject(request, pk)


@extend_schema_view(
    list=extend_schema(
        summary="List maternity leave proposals",
        description="Retrieve a list of maternity leave proposals",
        tags=["9.2.7: Maternity Leave Proposals"],
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
                                "proposal_type": "maternity_leave",
                                "colored_proposal_status": {"value": "pending", "variant": "yellow"},
                                "maternity_leave_start_date": "2025-02-01",
                                "maternity_leave_end_date": "2025-08-01",
                                "maternity_leave_estimated_due_date": "2025-03-15",
                                "note": "Maternity leave request",
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
        summary="Get maternity leave proposal details",
        description="Retrieve detailed information for a specific maternity leave proposal",
        tags=["9.2.7: Maternity Leave Proposals"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "maternity_leave",
                        "colored_proposal_status": {"value": "pending", "variant": "yellow"},
                        "maternity_leave_start_date": "2025-02-01",
                        "maternity_leave_end_date": "2025-08-01",
                        "maternity_leave_estimated_due_date": "2025-03-15",
                        "note": "Maternity leave request",
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
        summary="Create maternity leave proposal",
        description="Create a new maternity leave proposal",
        tags=["9.2.7: Maternity Leave Proposals"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "maternity_leave_start_date": "2025-02-01",
                    "maternity_leave_end_date": "2025-08-01",
                    "maternity_leave_estimated_due_date": "2025-03-15",
                    "maternity_leave_replacement_employee_id": 2,
                    "note": "Maternity leave request",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "maternity_leave",
                        "colored_proposal_status": {"value": "pending", "variant": "yellow"},
                        "maternity_leave_start_date": "2025-02-01",
                        "maternity_leave_end_date": "2025-08-01",
                        "maternity_leave_estimated_due_date": "2025-03-15",
                        "note": "Maternity leave request",
                        "created_at": "2025-01-15T10:00:00Z",
                        "updated_at": "2025-01-15T10:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error - Invalid date range",
                value={
                    "success": False,
                    "data": None,
                    "error": {
                        "maternity_leave_end_date": ["Maternity leave end date must be on or after start date"],
                    },
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    update=extend_schema(
        summary="Update maternity leave proposal",
        description="Update a maternity leave proposal",
        tags=["9.2.7: Maternity Leave Proposals"],
    ),
    partial_update=extend_schema(
        summary="Partially update maternity leave proposal",
        description="Partially update a maternity leave proposal",
        tags=["9.2.7: Maternity Leave Proposals"],
    ),
    destroy=extend_schema(
        summary="Delete maternity leave proposal",
        description="Delete a maternity leave proposal",
        tags=["9.2.7: Maternity Leave Proposals"],
    ),
    export=extend_schema(
        tags=["9.2.7: Maternity Leave Proposals"],
    ),
)
class ProposalMaternityLeaveViewSet(ProposalMixin, BaseModelViewSet):
    """ViewSet for Maternity Leave proposals."""

    proposal_type = ProposalType.MATERNITY_LEAVE
    serializer_class = ProposalMaternityLeaveSerializer
    permission_prefix = "proposal_maternity_leave"
    export_serializer_class = ProposalMaternityLeaveExportXLSXSerializer

    def get_select_related_fields(self) -> List[str]:
        fields = super().get_select_related_fields()
        fields.append("maternity_leave_replacement_employee")
        return fields

    @extend_schema(
        summary="Approve maternity leave proposal",
        description="Approve a maternity leave proposal",
        request=ProposalApproveSerializer,
        responses={200: ProposalMaternityLeaveSerializer},
        tags=["9.2.7: Maternity Leave Proposals"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "maternity_leave",
                        "colored_proposal_status": {"value": "approved", "variant": "green"},
                        "maternity_leave_start_date": "2025-02-01",
                        "maternity_leave_end_date": "2025-08-01",
                        "maternity_leave_estimated_due_date": "2025-03-15",
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
        return super().approve(request, pk)

    @extend_schema(
        summary="Reject maternity leave proposal",
        description="Reject a maternity leave proposal with a required rejection reason",
        request=ProposalRejectSerializer,
        responses={200: ProposalMaternityLeaveSerializer},
        tags=["9.2.7: Maternity Leave Proposals"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "maternity_leave",
                        "colored_proposal_status": {"value": "rejected", "variant": "red"},
                        "maternity_leave_start_date": "2025-02-01",
                        "maternity_leave_end_date": "2025-08-01",
                        "maternity_leave_estimated_due_date": "2025-03-15",
                        "note": "Missing required documentation",
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
                    "error": {"note": ["This field is required."]},
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        return super().reject(request, pk)


@extend_schema_view(
    list=extend_schema(
        summary="List attendance exemption proposals",
        description="Retrieve a list of attendance exemption proposals",
        tags=["9.2.8: Attendance Exemption Proposals"],
    ),
    retrieve=extend_schema(
        summary="Get attendance exemption proposal details",
        description="Retrieve detailed information for a specific attendance exemption proposal",
        tags=["9.2.8: Attendance Exemption Proposals"],
    ),
)
class ProposalAttendanceExemptionViewSet(ProposalMixin, BaseReadOnlyModelViewSet):
    """ViewSet for Attendance Exemption proposals."""

    proposal_type = ProposalType.ATTENDANCE_EXEMPTION
    permission_prefix = "proposal_attendance_exemption"

    def get_prefetch_related_fields(self) -> List[str]:
        return ["timesheet_entries", "timesheet_entries__timesheet_entry"]

    @extend_schema(exclude=True)
    def approve(self, request, pk=None):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    @extend_schema(exclude=True)
    def reject(self, request, pk=None):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    @extend_schema(exclude=True)
    def export(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)


@extend_schema_view(
    list=extend_schema(
        summary="List job transfer proposals",
        description="Retrieve a list of job transfer proposals",
        tags=["9.2.9: Job Transfer Proposals"],
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
                                "proposal_type": "job_transfer",
                                "colored_proposal_status": {"value": "pending", "variant": "yellow"},
                                "job_transfer_new_branch": {"id": 1, "name": "Head Office"},
                                "job_transfer_new_block": {"id": 2, "name": "Sales Block"},
                                "job_transfer_new_department": {"id": 3, "name": "Marketing"},
                                "job_transfer_new_department_id": 3,
                                "job_transfer_new_position": {"id": 4, "name": "Senior Developer"},
                                "job_transfer_new_position_id": 4,
                                "job_transfer_effective_date": "2025-02-01",
                                "job_transfer_reason": "Career development",
                                "note": "Transfer request to Marketing department",
                                "created_by": {"id": 1, "fullname": "John Doe", "email": "john@example.com"},
                                "approved_by": None,
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
        summary="Get job transfer proposal details",
        description="Retrieve detailed information for a specific job transfer proposal",
        tags=["9.2.9: Job Transfer Proposals"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "job_transfer",
                        "colored_proposal_status": {"value": "pending", "variant": "yellow"},
                        "job_transfer_new_branch": {"id": 1, "name": "Head Office"},
                        "job_transfer_new_block": {"id": 2, "name": "Sales Block"},
                        "job_transfer_new_department": {"id": 3, "name": "Marketing"},
                        "job_transfer_new_department_id": 3,
                        "job_transfer_new_position": {"id": 4, "name": "Senior Developer"},
                        "job_transfer_new_position_id": 4,
                        "job_transfer_effective_date": "2025-02-01",
                        "job_transfer_reason": "Career development",
                        "note": "Transfer request to Marketing department",
                        "created_by": {"id": 1, "fullname": "John Doe", "email": "john@example.com"},
                        "approved_by": None,
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
        summary="Create job transfer proposal",
        description="Create a new job transfer proposal",
        tags=["9.2.9: Job Transfer Proposals"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "job_transfer_new_department_id": 3,
                    "job_transfer_new_position_id": 4,
                    "job_transfer_effective_date": "2025-02-01",
                    "job_transfer_reason": "Career development",
                    "note": "Transfer request to Marketing department",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "job_transfer",
                        "colored_proposal_status": {"value": "pending", "variant": "yellow"},
                        "job_transfer_new_branch": None,
                        "job_transfer_new_block": None,
                        "job_transfer_new_department": {"id": 3, "name": "Marketing"},
                        "job_transfer_new_department_id": 3,
                        "job_transfer_new_position": {"id": 4, "name": "Senior Developer"},
                        "job_transfer_new_position_id": 4,
                        "job_transfer_effective_date": "2025-02-01",
                        "job_transfer_reason": "Career development",
                        "note": "Transfer request to Marketing department",
                        "created_by": {"id": 1, "fullname": "John Doe", "email": "john@example.com"},
                        "approved_by": None,
                        "created_at": "2025-01-15T10:00:00Z",
                        "updated_at": "2025-01-15T10:00:00Z",
                    },
                    "error": None,
                },
                response_only=True,
            ),
            OpenApiExample(
                "Error - Missing required fields",
                value={
                    "success": False,
                    "data": None,
                    "error": {
                        "job_transfer_effective_date": ["Job transfer effective date is required"],
                        "job_transfer_new_department_id": ["This field is required."],
                        "job_transfer_new_position_id": ["This field is required."],
                    },
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
    update=extend_schema(
        summary="Update job transfer proposal",
        description="Update a job transfer proposal",
        tags=["9.2.9: Job Transfer Proposals"],
    ),
    partial_update=extend_schema(
        summary="Partially update job transfer proposal",
        description="Partially update a job transfer proposal",
        tags=["9.2.9: Job Transfer Proposals"],
    ),
    destroy=extend_schema(
        summary="Delete job transfer proposal",
        description="Delete a job transfer proposal",
        tags=["9.2.9: Job Transfer Proposals"],
    ),
    export=extend_schema(
        tags=["9.2.9: Job Transfer Proposals"],
    ),
)
class ProposalJobTransferViewSet(ProposalMixin, BaseModelViewSet):
    """ViewSet for Job Transfer proposals."""

    proposal_type = ProposalType.JOB_TRANSFER
    serializer_class = ProposalJobTransferSerializer
    permission_prefix = "proposal_job_transfer"
    export_serializer_class = ProposalJobTransferExportXLSXSerializer

    def get_select_related_fields(self) -> List[str]:
        fields = super().get_select_related_fields()
        fields.extend(
            [
                "job_transfer_new_branch",
                "job_transfer_new_block",
                "job_transfer_new_department",
                "job_transfer_new_position",
            ]
        )
        return fields

    @extend_schema(
        summary="Approve job transfer proposal",
        description="Approve a job transfer proposal",
        request=ProposalApproveSerializer,
        responses={200: ProposalJobTransferSerializer},
        tags=["9.2.9: Job Transfer Proposals"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "job_transfer",
                        "colored_proposal_status": {"value": "approved", "variant": "green"},
                        "job_transfer_new_branch": {"id": 1, "name": "Head Office"},
                        "job_transfer_new_block": {"id": 2, "name": "Sales Block"},
                        "job_transfer_new_department": {"id": 3, "name": "Marketing"},
                        "job_transfer_new_department_id": 3,
                        "job_transfer_new_position": {"id": 4, "name": "Senior Developer"},
                        "job_transfer_new_position_id": 4,
                        "job_transfer_effective_date": "2025-02-01",
                        "job_transfer_reason": "Career development",
                        "note": "Approved by manager",
                        "created_by": {"id": 1, "fullname": "John Doe", "email": "john@example.com"},
                        "approved_by": {"id": 2, "fullname": "Jane Manager", "email": "jane@example.com"},
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
        return super().approve(request, pk)

    @extend_schema(
        summary="Reject job transfer proposal",
        description="Reject a job transfer proposal with a required rejection reason",
        request=ProposalRejectSerializer,
        responses={200: ProposalJobTransferSerializer},
        tags=["9.2.9: Job Transfer Proposals"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "job_transfer",
                        "colored_proposal_status": {"value": "rejected", "variant": "red"},
                        "job_transfer_new_branch": {"id": 1, "name": "Head Office"},
                        "job_transfer_new_block": {"id": 2, "name": "Sales Block"},
                        "job_transfer_new_department": {"id": 3, "name": "Marketing"},
                        "job_transfer_new_department_id": 3,
                        "job_transfer_new_position": {"id": 4, "name": "Senior Developer"},
                        "job_transfer_new_position_id": 4,
                        "job_transfer_effective_date": "2025-02-01",
                        "job_transfer_reason": "Career development",
                        "note": "Position not available at this time",
                        "created_by": {"id": 1, "fullname": "John Doe", "email": "john@example.com"},
                        "approved_by": None,
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
                    "error": {"note": ["This field is required."]},
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        return super().reject(request, pk)


@extend_schema_view(
    list=extend_schema(
        summary="List asset allocation proposals",
        description="Retrieve a list of asset allocation proposals",
        tags=["9.2.10: Asset Allocation Proposals"],
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
                                "proposal_type": "asset_allocation",
                                "colored_proposal_status": {"value": "pending", "variant": "yellow"},
                                "assets": [
                                    {
                                        "id": 1,
                                        "name": "Laptop Dell XPS 15",
                                        "unit_type": "piece",
                                        "quantity": 1,
                                        "note": None,
                                    }
                                ],
                                "note": "For new employee",
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
        summary="Get asset allocation proposal details",
        description="Retrieve detailed information for a specific asset allocation proposal",
        tags=["9.2.10: Asset Allocation Proposals"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "asset_allocation",
                        "colored_proposal_status": {"value": "pending", "variant": "yellow"},
                        "assets": [
                            {
                                "id": 1,
                                "name": "Laptop Dell XPS 15",
                                "unit_type": "piece",
                                "quantity": 1,
                                "note": None,
                            }
                        ],
                        "note": "For new employee",
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
        summary="Create asset allocation proposal",
        description="Create a new asset allocation proposal with assets",
        tags=["9.2.10: Asset Allocation Proposals"],
        examples=[
            OpenApiExample(
                "Request",
                value={
                    "assets": [
                        {
                            "name": "Laptop Dell XPS 15",
                            "unit_type": "piece",
                            "quantity": 1,
                            "note": "For development work",
                        },
                        {
                            "name": "Monitor 27 inch",
                            "unit_type": "piece",
                            "quantity": 2,
                        },
                    ],
                    "note": "Equipment for new employee",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "asset_allocation",
                        "colored_proposal_status": {"value": "pending", "variant": "yellow"},
                        "assets": [
                            {
                                "id": 1,
                                "name": "Laptop Dell XPS 15",
                                "unit_type": "piece",
                                "quantity": 1,
                                "note": "For development work",
                            },
                            {
                                "id": 2,
                                "name": "Monitor 27 inch",
                                "unit_type": "piece",
                                "quantity": 2,
                                "note": None,
                            },
                        ],
                        "note": "Equipment for new employee",
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
        summary="Update asset allocation proposal",
        description="Update an asset allocation proposal",
        tags=["9.2.10: Asset Allocation Proposals"],
    ),
    partial_update=extend_schema(
        summary="Partially update asset allocation proposal",
        description="Partially update an asset allocation proposal",
        tags=["9.2.10: Asset Allocation Proposals"],
    ),
    destroy=extend_schema(
        summary="Delete asset allocation proposal",
        description="Delete an asset allocation proposal",
        tags=["9.2.10: Asset Allocation Proposals"],
    ),
    export=extend_schema(
        tags=["9.2.10: Asset Allocation Proposals"],
    ),
)
class ProposalAssetAllocationViewSet(ProposalMixin, BaseModelViewSet):
    """ViewSet for Asset Allocation proposals."""

    proposal_type = ProposalType.ASSET_ALLOCATION
    serializer_class = ProposalAssetAllocationSerializer
    permission_prefix = "proposal_asset_allocation"
    export_serializer_class = ProposalAssetAllocationExportXLSXSerializer

    def get_prefetch_related_fields(self) -> List[str]:
        return ["assets"]

    @extend_schema(
        summary="Approve asset allocation proposal",
        description="Approve an asset allocation proposal",
        request=ProposalApproveSerializer,
        responses={200: ProposalAssetAllocationSerializer},
        tags=["9.2.10: Asset Allocation Proposals"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "asset_allocation",
                        "colored_proposal_status": {"value": "approved", "variant": "green"},
                        "assets": [
                            {
                                "id": 1,
                                "name": "Laptop Dell XPS 15",
                                "unit_type": "piece",
                                "quantity": 1,
                                "note": None,
                            }
                        ],
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
        return super().approve(request, pk)

    @extend_schema(
        summary="Reject asset allocation proposal",
        description="Reject an asset allocation proposal with a required rejection reason",
        request=ProposalRejectSerializer,
        responses={200: ProposalAssetAllocationSerializer},
        tags=["9.2.10: Asset Allocation Proposals"],
        examples=[
            OpenApiExample(
                "Success",
                value={
                    "success": True,
                    "data": {
                        "id": 1,
                        "code": "DX000001",
                        "proposal_date": "2025-01-15",
                        "proposal_type": "asset_allocation",
                        "colored_proposal_status": {"value": "rejected", "variant": "red"},
                        "assets": [
                            {
                                "id": 1,
                                "name": "Laptop Dell XPS 15",
                                "unit_type": "piece",
                                "quantity": 1,
                                "note": None,
                            }
                        ],
                        "note": "Asset not available in inventory",
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
                    "error": {"note": ["This field is required."]},
                },
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        return super().reject(request, pk)


@extend_schema_view(
    list=extend_schema(
        summary="List proposal verifiers",
        description="Retrieve a list of proposal verifiers with optional filtering",
        tags=["9.3: Proposal Verifiers"],
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
        tags=["9.3: Proposal Verifiers"],
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
        tags=["9.3: Proposal Verifiers"],
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
        tags=["9.3: Proposal Verifiers"],
    ),
    partial_update=extend_schema(
        summary="Partially update proposal verifier",
        description="Partially update a proposal verifier",
        tags=["9.3: Proposal Verifiers"],
    ),
    destroy=extend_schema(
        summary="Delete proposal verifier",
        description="Delete a proposal verifier",
        tags=["9.3: Proposal Verifiers"],
    ),
)
class ProposalVerifierViewSet(AuditLoggingMixin, BaseModelViewSet):
    """ViewSet for managing proposal verifiers."""

    queryset = ProposalVerifier.objects.select_related("proposal", "employee")
    serializer_class = ProposalVerifierSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = ProposalVerifierFilterSet
    ordering_fields = ["created_at", "verified_time"]
    ordering = ["-created_at"]

    module = "HRM"
    submodule = "ProposalVerifier"
    permission_prefix = "proposal_verifier"

    def get_serializer_class(self):
        if self.action == "verify":
            return ProposalVerifierVerifySerializer
        return super().get_serializer_class()

    @extend_schema(
        summary="Verify proposal",
        description="Mark a proposal as verified. Only applicable for timesheet entry complaint proposals.",
        tags=["9.3: Proposal Verifiers"],
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
        serializer = self.get_serializer(verifier, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(self.serializer_class(verifier).data, status=status.HTTP_200_OK)


class MeProposalVerifierViewSet(ProposalVerifierViewSet):
    """ViewSet for current user's proposal verifiers."""

    serializer_class = ProposalVerifierNeedVerificationSerializer
    filterset_class = MeProposalVerifierFilterSet

    def get_queryset(self):
        return super().get_queryset().filter(employee=self.request.user.employee)
