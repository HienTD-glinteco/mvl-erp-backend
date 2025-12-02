from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.hrm.api.serializers.common_nested import (
    BlockNestedSerializer,
    BranchNestedSerializer,
    DepartmentNestedSerializer,
    PositionNestedSerializer,
)
from apps.hrm.constants import ProposalStatus, ProposalType
from apps.hrm.models import Proposal, ProposalAsset, ProposalOvertimeEntry, ProposalTimeSheetEntry, ProposalVerifier

from .employee import EmployeeSerializer


class ProposalSerializer(serializers.ModelSerializer):
    """Serializer for Proposal model."""

    created_by = EmployeeSerializer(read_only=True)
    approved_by = EmployeeSerializer(read_only=True)

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
            "created_by",
            "approved_by",
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
            "created_by",
            "approved_by",
            "created_at",
            "updated_at",
        ]


class ProposalTimesheetEntryComplaintSerializer(ProposalSerializer):
    """Serializer for Timesheet Entry Complaint proposals with linked timesheet entry ID.

    This serializer extends ProposalSerializer to include the linked timesheet entry ID
    for complaint proposals. A complaint proposal links to exactly one timesheet entry.
    """

    timesheet_entry_id = serializers.SerializerMethodField(
        help_text="ID of the linked timesheet entry", required=False
    )

    class Meta(ProposalSerializer.Meta):
        fields = ProposalSerializer.Meta.fields + ["timesheet_entry_id"]

    def get_timesheet_entry_id(self, obj: Proposal) -> int | None:
        """Get the ID of the linked timesheet entry for this complaint proposal.

        Returns:
            The timesheet entry ID, or None if no entry is linked.
        """
        # Use .only() to fetch only the timesheet_entry_id field for optimization
        junction = ProposalTimeSheetEntry.objects.filter(proposal_id=obj.id).only("timesheet_entry_id").first()
        if junction:
            return junction.timesheet_entry_id
        return None


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

        user = self.context["request"].user
        if getattr(user, "employee", None):
            attrs["approved_by"] = user.employee

        return attrs

    def get_target_status(self):
        raise NotImplementedError("Subclasses must define target_status")


class ProposalTimesheetEntryComplaintApproveSerializer(ProposalBaseComplaintStatusActionSerializer):
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


class ProposalTimesheetEntryComplaintRejectSerializer(ProposalBaseComplaintStatusActionSerializer):
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


class ProposalVerifierSerializer(serializers.ModelSerializer):
    """Serializer for ProposalVerifier model."""

    class Meta:
        model = ProposalVerifier
        fields = [
            "id",
            "proposal",
            "employee",
            "status",
            "verified_time",
            "note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]


class ProposalVerifierVerifySerializer(serializers.ModelSerializer):
    """Serializer for verifying a proposal."""

    note = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Optional note for verification",
    )

    class Meta:
        model = ProposalVerifier
        fields = ["note"]

    def validate(self, attrs):
        """Validate that the proposal is a timesheet entry complaint."""
        # self.instance is the ProposalVerifier object being updated
        if not self.instance:
            raise serializers.ValidationError("This serializer requires an existing verifier instance")

        proposal = self.instance.proposal
        if proposal.proposal_type != ProposalType.TIMESHEET_ENTRY_COMPLAINT:
            raise serializers.ValidationError(
                "Verification is only applicable for timesheet entry complaint proposals"
            )

        return attrs

    def update(self, instance, validated_data):
        """Update the verifier instance with verified status and timestamp."""
        from django.utils import timezone

        from apps.hrm.constants import ProposalVerifierStatus

        # Update status and timestamp
        instance.status = ProposalVerifierStatus.VERIFIED
        instance.verified_time = timezone.now()

        # Update note if provided
        if validated_data.get("note"):
            instance.note = validated_data["note"]

        instance.save()
        return instance


class ProposalByTypeSerializer(serializers.ModelSerializer):
    """
    Serializer for proposals of a specific type.
    Each serializer subclass corresponds to a specific proposal type,
    and should have only the fields relevant to that type.
    """

    created_by = EmployeeSerializer(read_only=True)
    approved_by = EmployeeSerializer(read_only=True)

    def validate(self, attrs):
        user = self.context["request"].user
        if getattr(user, "employee", None):
            attrs["created_by"] = user.employee

        attrs["proposal_type"] = self.get_proposal_type()

        instance = self.instance or Proposal()
        for attr, value in attrs.items():
            setattr(instance, attr, value)

        try:
            instance.clean()
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.message_dict)

        return attrs

    def get_proposal_type(self):
        """
        Get the proposal type from the view context.
        Make sure the view use default get_serializer_context method (or override it).
        """
        return self.context["view"].proposal_type


class ProposalLateExemptionSerializer(ProposalByTypeSerializer):
    """Serializer for Late Exemption proposals."""

    class Meta:
        model = Proposal
        fields = [
            "id",
            "code",
            "proposal_date",
            "proposal_type",
            "proposal_status",
            "late_exemption_start_date",
            "late_exemption_end_date",
            "late_exemption_minutes",
            "note",
            "created_by",
            "approved_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "code",
            "proposal_date",
            "proposal_type",
            "proposal_status",
            "created_by",
            "approved_by",
            "created_at",
            "updated_at",
        ]


class ProposalOvertimeEntrySerializer(serializers.ModelSerializer):
    """Serializer for ProposalOvertimeEntry model."""

    class Meta:
        model = ProposalOvertimeEntry
        fields = [
            "id",
            "date",
            "start_time",
            "end_time",
            "description",
            "duration_hours",
        ]
        read_only_fields = ["id", "duration_hours"]

    def validate(self, attrs):
        instance = self.instance or ProposalOvertimeEntry()
        for attr, value in attrs.items():
            setattr(instance, attr, value)

        try:
            instance.clean()
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.message_dict)

        return attrs


class ProposalOvertimeWorkSerializer(ProposalByTypeSerializer):
    """Serializer for Overtime Work proposals."""

    entries = ProposalOvertimeEntrySerializer(many=True, write_only=True)
    overtime_entries = ProposalOvertimeEntrySerializer(many=True, read_only=True)

    class Meta:
        model = Proposal
        fields = [
            "id",
            "code",
            "proposal_date",
            "proposal_type",
            "proposal_status",
            "entries",
            "overtime_entries",
            "note",
            "created_by",
            "approved_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "code",
            "proposal_date",
            "proposal_type",
            "proposal_status",
            "overtime_entries",
            "created_by",
            "approved_by",
            "created_at",
            "updated_at",
        ]

    def validate_entries(self, value):
        """Validate that at least one entry is provided."""
        if not value:
            raise serializers.ValidationError(_("At least one overtime entry is required"))
        return value

    def create(self, validated_data):
        """Create a proposal with related overtime entries."""
        entries_data = validated_data.pop("entries", [])
        proposal = super().create(validated_data)

        self._create_entries_bulk(proposal, entries_data)

        return proposal

    def update(self, instance, validated_data):
        """Update a proposal with related overtime entries."""
        entries_data = validated_data.pop("entries", [])
        proposal = super().update(instance, validated_data)

        if entries_data:
            # Delete existing entries and recreate
            proposal.overtime_entries.all().delete()
            self._create_entries_bulk(proposal, entries_data)

        return proposal

    def _create_entries_bulk(self, proposal, entries_data):
        """Bulk create overtime entries for the proposal."""
        overtime_entries = []
        for entry_data in entries_data:
            overtime_entries.append(ProposalOvertimeEntry(proposal=proposal, **entry_data))
        ProposalOvertimeEntry.objects.bulk_create(overtime_entries)


class ProposalPostMaternityBenefitsSerializer(ProposalByTypeSerializer):
    """Serializer for Post-Maternity Benefits proposals."""

    class Meta:
        model = Proposal
        fields = [
            "id",
            "code",
            "proposal_date",
            "proposal_type",
            "proposal_status",
            "post_maternity_benefits_start_date",
            "post_maternity_benefits_end_date",
            "note",
            "created_by",
            "approved_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "code",
            "proposal_date",
            "proposal_type",
            "proposal_status",
            "created_by",
            "approved_by",
            "created_at",
            "updated_at",
        ]


class ProposalAssetSerializer(serializers.ModelSerializer):
    """Serializer for ProposalAsset model."""

    class Meta:
        model = ProposalAsset
        fields = [
            "id",
            "name",
            "unit_type",
            "quantity",
            "note",
        ]
        read_only_fields = ["id"]


class ProposalAssetAllocationSerializer(ProposalByTypeSerializer):
    """Serializer for Asset Allocation proposals."""

    proposal_assets = ProposalAssetSerializer(many=True, write_only=True)
    assets = ProposalAssetSerializer(many=True, read_only=True)

    class Meta:
        model = Proposal
        fields = [
            "id",
            "code",
            "proposal_date",
            "proposal_type",
            "proposal_status",
            "proposal_assets",
            "assets",
            "note",
            "created_by",
            "approved_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "code",
            "proposal_date",
            "proposal_type",
            "proposal_status",
            "assets",
            "created_by",
            "approved_by",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        """Create a proposal with related assets."""
        proposal_assets_data = validated_data.pop("proposal_assets", [])
        proposal = super().create(validated_data)

        self._create_new_assets_bulk(proposal, proposal_assets_data)

        return proposal

    def update(self, instance, validated_data):
        """Update a proposal with related assets."""
        proposal_assets_data = validated_data.pop("proposal_assets", [])
        proposal = super().update(instance, validated_data)

        if proposal_assets_data:
            # Delete existing assets and recreate
            proposal.assets.all().delete()
            self._create_new_assets_bulk(proposal, proposal_assets_data)

        return proposal

    def _create_new_assets_bulk(self, proposal, assets_data):
        proposal_assets = []
        for asset_data in assets_data:
            proposal_assets.append(ProposalAsset(proposal=proposal, **asset_data))
        ProposalAsset.objects.bulk_create(proposal_assets)


class ProposalMaternityLeaveSerializer(ProposalByTypeSerializer):
    """Serializer for Maternity Leave proposals."""

    maternity_leave_replacement_employee = EmployeeSerializer(read_only=True)
    maternity_leave_replacement_employee_id = serializers.IntegerField(required=False)

    class Meta:
        model = Proposal
        fields = [
            "id",
            "code",
            "proposal_date",
            "proposal_type",
            "proposal_status",
            "maternity_leave_start_date",
            "maternity_leave_end_date",
            "maternity_leave_estimated_due_date",
            "maternity_leave_replacement_employee",
            "maternity_leave_replacement_employee_id",
            "note",
            "created_by",
            "approved_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "code",
            "proposal_date",
            "proposal_type",
            "proposal_status",
            "created_by",
            "approved_by",
            "created_at",
            "updated_at",
        ]


class ProposalPaidLeaveSerializer(ProposalByTypeSerializer):
    """Serializer for Paid Leave proposals."""

    class Meta:
        model = Proposal
        fields = [
            "id",
            "code",
            "proposal_date",
            "proposal_type",
            "proposal_status",
            "paid_leave_start_date",
            "paid_leave_end_date",
            "paid_leave_shift",
            "paid_leave_reason",
            "note",
            "created_by",
            "approved_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "code",
            "proposal_date",
            "proposal_type",
            "proposal_status",
            "created_by",
            "approved_by",
            "created_at",
            "updated_at",
        ]


class ProposalUnpaidLeaveSerializer(ProposalByTypeSerializer):
    """Serializer for Unpaid Leave proposals."""

    class Meta:
        model = Proposal
        fields = [
            "id",
            "code",
            "proposal_date",
            "proposal_type",
            "proposal_status",
            "unpaid_leave_start_date",
            "unpaid_leave_end_date",
            "unpaid_leave_shift",
            "unpaid_leave_reason",
            "note",
            "created_by",
            "approved_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "code",
            "proposal_date",
            "proposal_type",
            "proposal_status",
            "created_by",
            "approved_by",
            "created_at",
            "updated_at",
        ]


class ProposalJobTransferSerializer(ProposalByTypeSerializer):
    """Serializer for Job Transfer proposals."""

    job_transfer_new_department_id = serializers.IntegerField()
    job_transfer_new_position_id = serializers.IntegerField()

    job_transfer_new_department = DepartmentNestedSerializer(read_only=True)
    job_transfer_new_position = PositionNestedSerializer(read_only=True)
    job_transfer_new_branch = BranchNestedSerializer(read_only=True)
    job_transfer_new_block = BlockNestedSerializer(read_only=True)

    class Meta:
        model = Proposal
        fields = [
            "id",
            "code",
            "proposal_date",
            "proposal_type",
            "proposal_status",
            "job_transfer_new_branch",
            "job_transfer_new_department_id",
            "job_transfer_new_block",
            "job_transfer_new_department",
            "job_transfer_new_position",
            "job_transfer_new_position_id",
            "job_transfer_effective_date",
            "job_transfer_reason",
            "note",
            "created_by",
            "approved_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "code",
            "proposal_date",
            "proposal_type",
            "proposal_status",
            "job_transfer_new_branch",
            "job_transfer_new_block",
            "job_transfer_new_department",
            "job_transfer_new_position",
            "created_by",
            "approved_by",
            "created_at",
            "updated_at",
        ]
