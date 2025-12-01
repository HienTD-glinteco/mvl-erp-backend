from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.hrm.constants import ProposalStatus, ProposalType
from apps.hrm.models import Proposal, ProposalAsset, ProposalTimeSheetEntry, ProposalVerifier

from .employee import EmployeeSerializer
from .organization import DepartmentSerializer, PositionSerializer


class ProposalAssetSerializer(serializers.ModelSerializer):
    """Serializer for ProposalAsset model."""

    class Meta:
        model = ProposalAsset
        fields = [
            "id",
            "name",
            "unit",
            "quantity",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProposalSerializer(serializers.ModelSerializer):
    """Serializer for Proposal model."""

    created_by = EmployeeSerializer(read_only=True)
    approved_by = EmployeeSerializer(read_only=True)
    handover_employee = EmployeeSerializer(read_only=True)
    new_department = DepartmentSerializer(read_only=True)
    new_job_title = PositionSerializer(read_only=True)
    assets = ProposalAssetSerializer(many=True, read_only=True)

    class Meta:
        model = Proposal
        fields = [
            "id",
            "code",
            "proposal_date",
            "proposal_type",
            "proposal_status",
            "complaint_reason",
            "proposed_check_in_time",
            "proposed_check_out_time",
            "approved_check_in_time",
            "approved_check_out_time",
            "start_date",
            "end_date",
            "effective_date",
            "total_hours",
            "session",
            "extra_data",
            "created_by",
            "approved_by",
            "handover_employee",
            "new_department",
            "new_job_title",
            "assets",
            "note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "code",
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


class ProposalAssetInputSerializer(serializers.Serializer):
    """Serializer for asset input in Asset Allocation proposals."""

    name = serializers.CharField(max_length=200, help_text="Asset name")
    unit = serializers.CharField(max_length=50, help_text="Unit of measurement")
    quantity = serializers.IntegerField(min_value=1, help_text="Quantity of assets")


class ProposalCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating proposals with polymorphic validation.

    This serializer handles creation of all proposal types with type-specific
    validation rules using a strategy pattern.
    """

    assets = ProposalAssetInputSerializer(many=True, required=False, write_only=True)

    class Meta:
        model = Proposal
        fields = [
            "proposal_type",
            "complaint_reason",
            "proposed_check_in_time",
            "proposed_check_out_time",
            "start_date",
            "end_date",
            "effective_date",
            "total_hours",
            "session",
            "extra_data",
            "handover_employee",
            "new_department",
            "new_job_title",
            "note",
            "assets",
        ]

    def _validate_leave_proposal(self, attrs: dict, proposal_type: str) -> None:
        """Validate leave proposals (paid/unpaid/maternity)."""
        errors = {}

        if not attrs.get("start_date"):
            errors["start_date"] = _("Start date is required for leave proposals")
        if not attrs.get("end_date"):
            errors["end_date"] = _("End date is required for leave proposals")

        if errors:
            raise serializers.ValidationError(errors)

    def _validate_overtime_proposal(self, attrs: dict) -> None:
        """Validate overtime work proposals."""
        errors = {}

        if not attrs.get("start_date"):
            errors["start_date"] = _("Date is required for overtime proposals")
        if not attrs.get("total_hours"):
            errors["total_hours"] = _("Total hours is required for overtime proposals")

        if errors:
            raise serializers.ValidationError(errors)

    def _validate_complaint_proposal(self, attrs: dict) -> None:
        """Validate timesheet entry complaint proposals."""
        if not attrs.get("complaint_reason") or not attrs.get("complaint_reason", "").strip():
            raise serializers.ValidationError(
                {"complaint_reason": _("Complaint reason is required for complaint proposals")}
            )

    def _validate_transfer_proposal(self, attrs: dict) -> None:
        """Validate transfer proposals."""
        errors = {}

        if not attrs.get("effective_date"):
            errors["effective_date"] = _("Effective date is required for transfer proposals")

        if errors:
            raise serializers.ValidationError(errors)

    def _validate_asset_allocation_proposal(self, attrs: dict) -> None:
        """Validate asset allocation proposals."""
        assets = attrs.get("assets", [])
        if not assets:
            raise serializers.ValidationError({"assets": _("At least one asset is required for asset allocation")})

    def validate(self, attrs):
        """Polymorphic validation based on proposal type."""
        proposal_type = attrs.get("proposal_type")

        if not proposal_type:
            raise serializers.ValidationError({"proposal_type": _("Proposal type is required")})

        # Validate start_date < end_date when both are provided
        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError({"start_date": _("Start date cannot be after end date")})

        # Type-specific validation using strategy pattern
        leave_types = [
            ProposalType.PAID_LEAVE,
            ProposalType.UNPAID_LEAVE,
            ProposalType.MATERNITY_LEAVE,
        ]

        if proposal_type in leave_types:
            self._validate_leave_proposal(attrs, proposal_type)
        elif proposal_type == ProposalType.OVERTIME_WORK:
            self._validate_overtime_proposal(attrs)
        elif proposal_type == ProposalType.TIMESHEET_ENTRY_COMPLAINT:
            self._validate_complaint_proposal(attrs)
        elif proposal_type == ProposalType.TRANSFER:
            self._validate_transfer_proposal(attrs)
        elif proposal_type == ProposalType.ASSET_ALLOCATION:
            self._validate_asset_allocation_proposal(attrs)
        # Other types (POST_MATERNITY_BENEFITS, LATE_EXEMPTION, ATTENDANCE_EXEMPTION)
        # have no additional required fields

        return attrs

    def create(self, validated_data):
        """Create proposal and associated assets."""
        assets_data = validated_data.pop("assets", [])

        # Set created_by from request user
        user = self.context["request"].user
        if hasattr(user, "employee") and user.employee:
            validated_data["created_by"] = user.employee
        else:
            raise serializers.ValidationError({"created_by": _("User must have an associated employee")})

        proposal = Proposal.objects.create(**validated_data)

        # Create assets for asset allocation proposals
        if assets_data:
            for asset_data in assets_data:
                ProposalAsset.objects.create(proposal=proposal, **asset_data)

        return proposal


class ProposalUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating proposals.

    Only allows updates when proposal is in PENDING status.
    """

    assets = ProposalAssetInputSerializer(many=True, required=False)

    class Meta:
        model = Proposal
        fields = [
            "complaint_reason",
            "proposed_check_in_time",
            "proposed_check_out_time",
            "start_date",
            "end_date",
            "effective_date",
            "total_hours",
            "session",
            "extra_data",
            "handover_employee",
            "new_department",
            "new_job_title",
            "note",
            "assets",
        ]

    def validate(self, attrs):
        """Check proposal is still pending before allowing update."""
        if self.instance and self.instance.proposal_status != ProposalStatus.PENDING:
            raise serializers.ValidationError(_("Cannot update a proposal that is not pending"))

        # Validate start_date < end_date when both are provided
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError({"start_date": _("Start date cannot be after end date")})

        return attrs

    def update(self, instance, validated_data):
        """Update proposal and associated assets."""
        assets_data = validated_data.pop("assets", None)

        # Update proposal fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update assets if provided (replace existing assets)
        if assets_data is not None and instance.proposal_type == ProposalType.ASSET_ALLOCATION:
            instance.assets.all().delete()
            for asset_data in assets_data:
                ProposalAsset.objects.create(proposal=instance, **asset_data)

        return instance


class ProposalBaseStatusActionSerializer(serializers.ModelSerializer):
    """Base serializer for proposal status actions (approve/reject).

    This is a generic version that works for all proposal types,
    not just complaint proposals.
    """

    class Meta:
        model = Proposal

    def validate(self, attrs):
        # Check if proposal is already processed
        if self.instance.proposal_status != ProposalStatus.PENDING:
            raise serializers.ValidationError(_("Proposal has already been processed"))

        attrs["proposal_status"] = self.get_target_status()

        user = self.context["request"].user
        if getattr(user, "employee", None):
            attrs["approved_by"] = user.employee

        return attrs

    def get_target_status(self):
        raise NotImplementedError("Subclasses must define target_status")


class ProposalGenericApproveSerializer(ProposalBaseStatusActionSerializer):
    """Generic serializer for approving any proposal type."""

    note = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Optional note for approval",
    )

    class Meta:
        model = Proposal
        fields = ["note"]

    def get_target_status(self):
        return ProposalStatus.APPROVED


class ProposalGenericRejectSerializer(ProposalBaseStatusActionSerializer):
    """Generic serializer for rejecting any proposal type."""

    note = serializers.CharField(
        required=True,
        allow_blank=False,
        help_text="Reason for rejection (required)",
    )

    class Meta:
        model = Proposal
        fields = ["note"]

    def validate_note(self, value):
        """Ensure note is not empty or whitespace only."""
        if not value or not value.strip():
            raise serializers.ValidationError(_("Note is required when rejecting a proposal"))
        return value

    def validate(self, attrs):
        """Ensure note is provided even for partial updates."""
        attrs = super().validate(attrs)
        # For partial updates, note field might not go through validate_note if not in request data
        # So we need to check here
        if "note" not in attrs:
            raise serializers.ValidationError({"note": _("Note is required when rejecting a proposal")})
        return attrs

    def get_target_status(self):
        return ProposalStatus.REJECTED


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
