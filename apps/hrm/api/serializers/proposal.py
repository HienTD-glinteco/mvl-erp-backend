from rest_framework import serializers

from apps.hrm.constants import ProposalStatus, ProposalType
from apps.hrm.models import Proposal


class ProposalSerializer(serializers.ModelSerializer):
    """Serializer for Proposal model."""

    class Meta:
        model = Proposal
        fields = [
            "id",
            "proposal_date",
            "proposal_type",
            "proposal_status",
            "complaint_reason",
            "proposed_check_in_time",
            "proposed_check_out_time",
            "approved_check_in_time",
            "approved_check_out_time",
            "note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "proposal_date",
            "proposal_status",
            "approved_check_in_time",
            "approved_check_out_time",
            "created_at",
            "updated_at",
        ]


class ProposalBaseComplaintStatusActionSerializer(serializers.ModelSerializer):
    """Base serializer for complaint proposal actions (approve/reject)."""

    class Meta:
        model = Proposal

    def validate(self, attrs):
        # Check if proposal is a complaint
        if self.instance.proposal_type != ProposalType.TIMESHEET_ENTRY_COMPLAINT:
            raise serializers.ValidationError("This action is only applicable for complaint proposals")

        # Check if proposal is already processed
        if self.instance.proposal_status != ProposalStatus.PENDING:
            raise serializers.ValidationError("Proposal has already been processed")

        attrs["proposal_status"] = self.get_target_status()
        return attrs

    def get_target_status(self):
        raise NotImplementedError("Subclasses must define target_status")


class ProposalApproveSerializer(ProposalBaseComplaintStatusActionSerializer):
    """Serializer for approving a proposal."""

    approved_check_in_time = serializers.TimeField(required=True, help_text="Approved check-in time")
    approved_check_out_time = serializers.TimeField(required=True, help_text="Approved check-out time")
    note = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Optional note for approval",
    )

    class Meta:
        model = Proposal
        fields = ["approved_check_in_time", "approved_check_out_time", "note"]

    def get_target_status(self):
        return ProposalStatus.APPROVED


class ProposalRejectSerializer(ProposalBaseComplaintStatusActionSerializer):
    """Serializer for rejecting a proposal."""

    note = serializers.CharField(
        required=True,
        allow_blank=False,
        help_text="Reason for rejection (required)",
    )

    target_status = ProposalStatus.REJECTED

    class Meta:
        model = Proposal
        fields = ["note"]

    def validate_note(self, value):
        """Ensure note is not empty or whitespace only."""
        if not value or not value.strip():
            raise serializers.ValidationError("Note is required when rejecting a proposal")
        return value

    def get_target_status(self):
        return ProposalStatus.REJECTED
