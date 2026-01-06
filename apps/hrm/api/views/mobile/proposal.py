from typing import List, Optional

from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apps.hrm.api.filtersets.proposal import MeProposalFilterSet, MeProposalVerifierFilterSet
from apps.hrm.api.serializers.proposal import (
    ProposalAssetAllocationSerializer,
    ProposalCombinedSerializer,
    ProposalDeviceChangeSerializer,
    ProposalJobTransferSerializer,
    ProposalLateExemptionSerializer,
    ProposalMaternityLeaveSerializer,
    ProposalOvertimeWorkSerializer,
    ProposalPaidLeaveSerializer,
    ProposalPostMaternityBenefitsSerializer,
    ProposalTimesheetEntryComplaintApproveSerializer,
    ProposalTimesheetEntryComplaintRejectSerializer,
    ProposalTimesheetEntryComplaintSerializer,
    ProposalUnpaidLeaveSerializer,
    ProposalVerifierNeedVerificationSerializer,
    ProposalVerifierRejectSerializer,
    ProposalVerifierSerializer,
    ProposalVerifierVerifySerializer,
)
from apps.hrm.constants import ProposalType
from apps.hrm.models import Proposal, ProposalVerifier
from libs import BaseModelViewSet, BaseReadOnlyModelViewSet
from libs.drf.filtersets.search import PhraseSearchFilter


@extend_schema_view(
    list=extend_schema(
        summary="List my proposals",
        description="Retrieve all proposals created by the current user",
        tags=["9.2: My Proposals"],
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
                                "proposal_type": "paid_leave",
                                "colored_proposal_status": {"value": "pending", "variant": "yellow"},
                                "note": "Annual leave",
                            }
                        ],
                    },
                    "error": None,
                },
                response_only=True,
            )
        ],
    ),
    retrieve=extend_schema(
        summary="Get my proposal details",
        description="Retrieve detailed information for a specific proposal created by the current user",
        tags=["9.2: My Proposals"],
    ),
)
class MyProposalViewSet(BaseReadOnlyModelViewSet):
    """Mobile ViewSet for viewing user's own proposals."""

    queryset = Proposal.objects.none()
    serializer_class = ProposalCombinedSerializer
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    filterset_class = MeProposalFilterSet
    search_fields = ["code"]
    ordering_fields = ["created_at", "proposal_date"]
    ordering = ["-created_at"]

    module = _("HRM - Mobile")
    submodule = _("My Proposals")
    permission_prefix = "my_proposal"

    def get_queryset(self):
        """Filter proposals to only show current user's proposals."""
        if getattr(self, "swagger_fake_view", False):
            return Proposal.objects.none()
        return Proposal.objects.filter(created_by=self.request.user.employee).select_related(
            "created_by", "approved_by"
        )

    def get_prefetch_related_fields(self) -> List[str]:
        return ["timesheet_entries", "timesheet_entries__timesheet_entry"]


class MyProposalMixin(BaseModelViewSet):
    """Base mixin for mobile proposal ViewSets with common configuration."""

    queryset = Proposal.objects.none()
    filter_backends = [DjangoFilterBackend, PhraseSearchFilter, OrderingFilter]
    filterset_class = MeProposalFilterSet
    search_fields = ["code"]
    ordering_fields = ["created_at", "proposal_date"]
    ordering = ["-created_at"]
    proposal_type: Optional[ProposalType] = None

    module = _("HRM - Mobile")
    submodule = _("My Proposals")
    permission_prefix = "my_proposal"

    def get_queryset(self):
        """Filter to current user's proposals of specific type."""
        if getattr(self, "swagger_fake_view", False):
            return Proposal.objects.none()
        qs = Proposal.objects.filter(created_by=self.request.user.employee).select_related("created_by", "approved_by")
        if self.proposal_type:
            qs = qs.filter(proposal_type=self.proposal_type)
        return qs

    def get_prefetch_related_fields(self) -> List[str]:
        return ["timesheet_entries", "timesheet_entries__timesheet_entry"]

    def perform_create(self, serializer):
        """Set created_by to current user's employee."""
        serializer.save(created_by=self.request.user.employee, proposal_type=self.proposal_type)


@extend_schema_view(
    list=extend_schema(
        summary="List my maternity leave proposals",
        description="Retrieve maternity leave proposals created by the current user",
        tags=["9.2.7: Maternity Leave Proposals"],
    ),
    create=extend_schema(
        summary="Create maternity leave proposal",
        description="Create a new maternity leave proposal",
        tags=["9.2.7: Maternity Leave Proposals"],
    ),
    retrieve=extend_schema(
        summary="Get maternity leave proposal details",
        description="Retrieve detailed information for a specific maternity leave proposal",
        tags=["9.2.7: Maternity Leave Proposals"],
    ),
    update=extend_schema(
        summary="Update maternity leave proposal",
        description="Update a maternity leave proposal (draft only)",
        tags=["9.2.7: Maternity Leave Proposals"],
    ),
    partial_update=extend_schema(
        summary="Partially update maternity leave proposal",
        description="Partially update a maternity leave proposal (draft only)",
        tags=["9.2.7: Maternity Leave Proposals"],
    ),
    destroy=extend_schema(
        summary="Delete maternity leave proposal",
        description="Delete a maternity leave proposal (draft only)",
        tags=["9.2.7: Maternity Leave Proposals"],
    ),
)
class MyProposalMaternityLeaveViewSet(MyProposalMixin):
    """Mobile ViewSet for maternity leave proposals."""

    serializer_class = ProposalMaternityLeaveSerializer
    proposal_type = ProposalType.MATERNITY_LEAVE
    permission_prefix = "my_proposal_maternity_leave"


@extend_schema_view(
    list=extend_schema(
        summary="List my unpaid leave proposals",
        tags=["9.2.6: Unpaid Leave Proposals"],
    ),
    create=extend_schema(
        summary="Create unpaid leave proposal",
        tags=["9.2.6: Unpaid Leave Proposals"],
    ),
    retrieve=extend_schema(
        summary="Get unpaid leave proposal details",
        tags=["9.2.6: Unpaid Leave Proposals"],
    ),
    update=extend_schema(
        summary="Update unpaid leave proposal",
        tags=["9.2.6: Unpaid Leave Proposals"],
    ),
    partial_update=extend_schema(
        summary="Partially update unpaid leave proposal",
        tags=["9.2.6: Unpaid Leave Proposals"],
    ),
    destroy=extend_schema(
        summary="Delete unpaid leave proposal",
        tags=["9.2.6: Unpaid Leave Proposals"],
    ),
)
class MyProposalUnpaidLeaveViewSet(MyProposalMixin):
    """Mobile ViewSet for unpaid leave proposals."""

    serializer_class = ProposalUnpaidLeaveSerializer
    proposal_type = ProposalType.UNPAID_LEAVE
    permission_prefix = "my_proposal_unpaid_leave"


@extend_schema_view(
    list=extend_schema(
        summary="List my paid leave proposals",
        tags=["9.2.5: Paid Leave Proposals"],
    ),
    create=extend_schema(
        summary="Create paid leave proposal",
        tags=["9.2.5: Paid Leave Proposals"],
    ),
    retrieve=extend_schema(
        summary="Get paid leave proposal details",
        tags=["9.2.5: Paid Leave Proposals"],
    ),
    update=extend_schema(
        summary="Update paid leave proposal",
        tags=["9.2.5: Paid Leave Proposals"],
    ),
    partial_update=extend_schema(
        summary="Partially update paid leave proposal",
        tags=["9.2.5: Paid Leave Proposals"],
    ),
    destroy=extend_schema(
        summary="Delete paid leave proposal",
        tags=["9.2.5: Paid Leave Proposals"],
    ),
)
class MyProposalPaidLeaveViewSet(MyProposalMixin):
    """Mobile ViewSet for paid leave proposals."""

    serializer_class = ProposalPaidLeaveSerializer
    proposal_type = ProposalType.PAID_LEAVE
    permission_prefix = "my_proposal_paid_leave"


@extend_schema_view(
    list=extend_schema(
        summary="List my post-maternity benefits proposals",
        tags=["9.2.2: Post-Maternity Benefits Proposals"],
    ),
    create=extend_schema(
        summary="Create post-maternity benefits proposal",
        tags=["9.2.2: Post-Maternity Benefits Proposals"],
    ),
    retrieve=extend_schema(
        summary="Get post-maternity benefits proposal details",
        tags=["9.2.2: Post-Maternity Benefits Proposals"],
    ),
    update=extend_schema(
        summary="Update post-maternity benefits proposal",
        tags=["9.2.2: Post-Maternity Benefits Proposals"],
    ),
    partial_update=extend_schema(
        summary="Partially update post-maternity benefits proposal",
        tags=["9.2.2: Post-Maternity Benefits Proposals"],
    ),
    destroy=extend_schema(
        summary="Delete post-maternity benefits proposal",
        tags=["9.2.2: Post-Maternity Benefits Proposals"],
    ),
)
class MyProposalPostMaternityBenefitsViewSet(MyProposalMixin):
    """Mobile ViewSet for post-maternity benefits proposals."""

    serializer_class = ProposalPostMaternityBenefitsSerializer
    proposal_type = ProposalType.POST_MATERNITY_BENEFITS
    permission_prefix = "my_proposal_post_maternity_benefits"


@extend_schema_view(
    list=extend_schema(
        summary="List my overtime work proposals",
        tags=["9.2.4: Overtime Work Proposals"],
    ),
    create=extend_schema(
        summary="Create overtime work proposal",
        tags=["9.2.4: Overtime Work Proposals"],
    ),
    retrieve=extend_schema(
        summary="Get overtime work proposal details",
        tags=["9.2.4: Overtime Work Proposals"],
    ),
    update=extend_schema(
        summary="Update overtime work proposal",
        tags=["9.2.4: Overtime Work Proposals"],
    ),
    partial_update=extend_schema(
        summary="Partially update overtime work proposal",
        tags=["9.2.4: Overtime Work Proposals"],
    ),
    destroy=extend_schema(
        summary="Delete overtime work proposal",
        tags=["9.2.4: Overtime Work Proposals"],
    ),
)
class MyProposalOvertimeWorkViewSet(MyProposalMixin):
    """Mobile ViewSet for overtime work proposals."""

    serializer_class = ProposalOvertimeWorkSerializer
    proposal_type = ProposalType.OVERTIME_WORK
    permission_prefix = "my_proposal_overtime_work"


@extend_schema_view(
    list=extend_schema(
        summary="List my late exemption proposals",
        tags=["9.2.3: Late Exemption Proposals"],
    ),
    create=extend_schema(
        summary="Create late exemption proposal",
        tags=["9.2.3: Late Exemption Proposals"],
    ),
    retrieve=extend_schema(
        summary="Get late exemption proposal details",
        tags=["9.2.3: Late Exemption Proposals"],
    ),
    update=extend_schema(
        summary="Update late exemption proposal",
        tags=["9.2.3: Late Exemption Proposals"],
    ),
    partial_update=extend_schema(
        summary="Partially update late exemption proposal",
        tags=["9.2.3: Late Exemption Proposals"],
    ),
    destroy=extend_schema(
        summary="Delete late exemption proposal",
        tags=["9.2.3: Late Exemption Proposals"],
    ),
)
class MyProposalLateExemptionViewSet(MyProposalMixin):
    """Mobile ViewSet for late exemption proposals."""

    serializer_class = ProposalLateExemptionSerializer
    proposal_type = ProposalType.LATE_EXEMPTION
    permission_prefix = "my_proposal_late_exemption"


@extend_schema_view(
    list=extend_schema(
        summary="List my job transfer proposals",
        tags=["9.2.9: Job Transfer Proposals"],
    ),
    create=extend_schema(
        summary="Create job transfer proposal",
        tags=["9.2.9: Job Transfer Proposals"],
    ),
    retrieve=extend_schema(
        summary="Get job transfer proposal details",
        tags=["9.2.9: Job Transfer Proposals"],
    ),
    update=extend_schema(
        summary="Update job transfer proposal",
        tags=["9.2.9: Job Transfer Proposals"],
    ),
    partial_update=extend_schema(
        summary="Partially update job transfer proposal",
        tags=["9.2.9: Job Transfer Proposals"],
    ),
    destroy=extend_schema(
        summary="Delete job transfer proposal",
        tags=["9.2.9: Job Transfer Proposals"],
    ),
)
class MyProposalJobTransferViewSet(MyProposalMixin):
    """Mobile ViewSet for job transfer proposals."""

    serializer_class = ProposalJobTransferSerializer
    proposal_type = ProposalType.JOB_TRANSFER
    permission_prefix = "my_proposal_job_transfer"


@extend_schema_view(
    list=extend_schema(
        summary="List my device change proposals",
        tags=["9.2.11: Device Change Proposals"],
    ),
    create=extend_schema(
        summary="Create device change proposal",
        tags=["9.2.11: Device Change Proposals"],
    ),
    retrieve=extend_schema(
        summary="Get device change proposal details",
        tags=["9.2.11: Device Change Proposals"],
    ),
    update=extend_schema(
        summary="Update device change proposal",
        tags=["9.2.11: Device Change Proposals"],
    ),
    partial_update=extend_schema(
        summary="Partially update device change proposal",
        tags=["9.2.11: Device Change Proposals"],
    ),
    destroy=extend_schema(
        summary="Delete device change proposal",
        tags=["9.2.11: Device Change Proposals"],
    ),
)
class MyProposalDeviceChangeViewSet(MyProposalMixin):
    """Mobile ViewSet for device change proposals."""

    serializer_class = ProposalDeviceChangeSerializer
    proposal_type = ProposalType.DEVICE_CHANGE
    permission_prefix = "my_proposal_device_change"


@extend_schema_view(
    list=extend_schema(
        summary="List my asset allocation proposals",
        tags=["9.2.10: Asset Allocation Proposals"],
    ),
    create=extend_schema(
        summary="Create asset allocation proposal",
        tags=["9.2.10: Asset Allocation Proposals"],
    ),
    retrieve=extend_schema(
        summary="Get asset allocation proposal details",
        tags=["9.2.10: Asset Allocation Proposals"],
    ),
    update=extend_schema(
        summary="Update asset allocation proposal",
        tags=["9.2.10: Asset Allocation Proposals"],
    ),
    partial_update=extend_schema(
        summary="Partially update asset allocation proposal",
        tags=["9.2.10: Asset Allocation Proposals"],
    ),
    destroy=extend_schema(
        summary="Delete asset allocation proposal",
        tags=["9.2.10: Asset Allocation Proposals"],
    ),
)
class MyProposalAssetAllocationViewSet(MyProposalMixin):
    """Mobile ViewSet for asset allocation proposals."""

    serializer_class = ProposalAssetAllocationSerializer
    proposal_type = ProposalType.ASSET_ALLOCATION
    permission_prefix = "my_proposal_asset_allocation"


@extend_schema_view(
    list=extend_schema(
        summary="List my timesheet entry complaint proposals",
        tags=["6.8: Timesheet Entry Complaint Proposals"],
    ),
    create=extend_schema(
        summary="Create timesheet entry complaint proposal",
        tags=["6.8: Timesheet Entry Complaint Proposals"],
    ),
    retrieve=extend_schema(
        summary="Get timesheet entry complaint proposal details",
        tags=["6.8: Timesheet Entry Complaint Proposals"],
    ),
    update=extend_schema(
        summary="Update timesheet entry complaint proposal",
        tags=["6.8: Timesheet Entry Complaint Proposals"],
    ),
    partial_update=extend_schema(
        summary="Partially update timesheet entry complaint proposal",
        tags=["6.8: Timesheet Entry Complaint Proposals"],
    ),
    destroy=extend_schema(
        summary="Delete timesheet entry complaint proposal",
        tags=["6.8: Timesheet Entry Complaint Proposals"],
    ),
)
class MyProposalTimesheetEntryComplaintViewSet(MyProposalMixin):
    """Mobile ViewSet for timesheet entry complaint proposals."""

    serializer_class = ProposalTimesheetEntryComplaintSerializer
    proposal_type = ProposalType.TIMESHEET_ENTRY_COMPLAINT
    permission_prefix = "my_proposal_time_sheet_entry_complaint"

    def get_serializer_class(self):
        if self.action == "approve":
            return ProposalTimesheetEntryComplaintApproveSerializer
        if self.action == "reject":
            return ProposalTimesheetEntryComplaintRejectSerializer
        return super().get_serializer_class()


@extend_schema_view(
    list=extend_schema(
        summary="List my proposal verifiers",
        description="Retrieve proposals that need verification by the current user",
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
                            }
                        ],
                    },
                    "error": None,
                },
                response_only=True,
            )
        ],
    ),
    retrieve=extend_schema(
        summary="Get my proposal verifier details",
        description="Retrieve detailed information for a specific proposal verifier",
        tags=["9.3: Proposal Verifiers"],
    ),
)
class MyProposalVerifierViewSet(BaseReadOnlyModelViewSet):
    """Mobile ViewSet for proposal verifier assigned to current user."""

    queryset = ProposalVerifier.objects.none()
    serializer_class = ProposalVerifierNeedVerificationSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = MeProposalVerifierFilterSet
    ordering_fields = ["created_at", "verified_time"]
    ordering = ["-created_at"]

    module = _("HRM - Mobile")
    submodule = _("Proposals Verifications")
    permission_prefix = "my_proposal_verification"

    def get_queryset(self):
        """Filter to verifications assigned to current user."""
        if getattr(self, "swagger_fake_view", False):
            return ProposalVerifier.objects.none()
        return ProposalVerifier.objects.filter(employee=self.request.user.employee).select_related(
            "proposal", "employee"
        )

    def get_serializer_class(self):
        if self.action == "verify":
            return ProposalVerifierVerifySerializer
        if self.action == "reject":
            return ProposalVerifierRejectSerializer
        return super().get_serializer_class()

    @extend_schema(
        summary="Verify proposal",
        description="Mark a proposal as verified",
        tags=["9.3: Proposal Verifiers"],
        request=ProposalVerifierVerifySerializer,
        examples=[
            OpenApiExample(
                "Request",
                value={"note": "Verified and approved"},
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
                    },
                    "error": None,
                },
                response_only=True,
            ),
        ],
    )
    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        """Verify a proposal."""
        verifier = self.get_object()
        serializer = self.get_serializer(verifier, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ProposalVerifierSerializer(verifier).data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Reject proposal verification",
        description="Mark a proposal verification as rejected",
        tags=["9.3: Proposal Verifiers"],
        request=ProposalVerifierRejectSerializer,
        examples=[
            OpenApiExample(
                "Request",
                value={"note": "Rejected due to insufficient evidence"},
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
                        "note": "Rejected due to insufficient evidence",
                    },
                    "error": None,
                },
                response_only=True,
            ),
        ],
    )
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        """Reject a proposal verification."""
        verifier = self.get_object()
        serializer = self.get_serializer(verifier, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ProposalVerifierSerializer(verifier).data, status=status.HTTP_200_OK)
