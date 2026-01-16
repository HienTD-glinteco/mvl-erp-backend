import logging
from typing import Optional

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.files.api.serializers import FileSerializer
from apps.files.api.serializers.mixins import FileConfirmSerializerMixin
from apps.hrm.api.serializers.common_nested import (
    BlockNestedSerializer,
    BranchNestedSerializer,
    DepartmentNestedSerializer,
    PositionNestedSerializer,
)
from apps.hrm.constants import ProposalStatus, ProposalType
from apps.hrm.models import Proposal, ProposalAsset, ProposalOvertimeEntry, ProposalTimeSheetEntry, ProposalVerifier
from apps.hrm.services.proposal_service import ProposalService
from libs.drf.serializers import ColoredValueSerializer, FieldFilteringSerializerMixin

from .employee import EmployeeSerializer

logger = logging.getLogger(__name__)

# =============================================================================
# 1. BASE & GENERIC SERIALIZERS
# =============================================================================


class ProposalSerializer(serializers.ModelSerializer):
    """Serializer for Proposal model."""

    created_by = EmployeeSerializer(read_only=True)
    approved_by = EmployeeSerializer(read_only=True)
    colored_proposal_status = ColoredValueSerializer(read_only=True)

    class Meta:
        model = Proposal
        fields = [
            "id",
            "code",
            "proposal_date",
            "proposal_type",
            "colored_proposal_status",
            "created_by",
            "approved_by",
            "approved_at",
            "note",
            "approval_note",
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
            "approved_at",
            "created_at",
            "updated_at",
        ]


class ProposalByTypeSerializer(serializers.ModelSerializer):
    """Base serializer for proposals of a specific type."""

    created_by = EmployeeSerializer(read_only=True)
    approved_by = EmployeeSerializer(read_only=True)
    colored_proposal_status = ColoredValueSerializer(read_only=True)
    short_description = serializers.CharField(read_only=True)

    class Meta:
        model = Proposal
        fields = [
            "id",
            "code",
            "proposal_date",
            "proposal_type",
            "colored_proposal_status",
            "short_description",
            "note",
            "approval_note",
            "approved_at",
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
            "colored_proposal_status",
            "short_description",
            "approval_note",
            "approved_at",
            "created_by",
            "approved_by",
            "created_at",
            "updated_at",
        ]

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
        return self.context["view"].proposal_type


# =============================================================================
# 2. ACTION SERIALIZERS (Change Status)
# =============================================================================


class ProposalChangeStatusSerializer(serializers.ModelSerializer):
    """Base serializer for changing status of a Proposal."""

    class Meta:
        model = Proposal

    def validate(self, attrs):
        if not self.instance:
            raise serializers.ValidationError("An existing Proposal is required to perform this action!")

        # Check if proposal is a complaint
        _proposal_type = self._get_proposal_type()
        if _proposal_type and self.instance.proposal_type != _proposal_type:
            raise serializers.ValidationError(f"This action is only applicable for {_proposal_type} proposals")

        # Check if proposal is already processed
        if self.instance.proposal_status != ProposalStatus.PENDING:
            raise serializers.ValidationError("Proposal has already been approved/rejected")

        attrs["proposal_status"] = self.get_target_status()
        attrs["approved_at"] = timezone.now()

        user = self.context["request"].user
        if getattr(user, "employee", None):
            attrs["approved_by"] = user.employee

        return attrs

    def get_target_status(self):
        raise NotImplementedError("Subclasses must define target_status")

    def _get_proposal_type(self) -> Optional[ProposalType]:
        """
        Override this method if the serializer only response for a specific type of Proposal.
        """
        return None

    def update(self, instance, validated_data):
        """Update the proposal and execute it if approved."""
        # Update the proposal status and fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        self.post_update(instance)
        return instance

    def post_update(self, instance: Proposal) -> None:
        """Hook for additional actions after updating the proposal."""
        pass


class ProposalApproveSerializer(ProposalChangeStatusSerializer):
    """
    Base serializer for approving a Proposal.
    approval_note is not required.
    """

    approval_note = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Optional note for approval",
    )

    class Meta:
        model = Proposal
        fields = ["approval_note"]

    def get_target_status(self):
        return ProposalStatus.APPROVED

    def post_update(self, instance: Proposal) -> None:
        super().post_update(instance)
        if instance.proposal_status == ProposalStatus.APPROVED:
            try:
                ProposalService.execute_approved_proposal(instance)
            except Exception as e:
                # Log the error but don't fail the approval
                # The proposal is already approved, so we should not rollback
                logger.error(f"Failed to execute proposal {instance.id}: {str(e)}", exc_info=True)


class ProposalRejectSerializer(ProposalChangeStatusSerializer):
    """
    Base serializer for rejecting a Proposal.
    approval_note is required.
    """

    approval_note = serializers.CharField(
        required=True,
        allow_blank=False,
        help_text="Reason for rejection (required)",
    )

    class Meta:
        model = Proposal
        fields = ["approval_note"]

    def get_target_status(self):
        return ProposalStatus.REJECTED


class ProposalTimesheetEntryComplaintApproveSerializer(ProposalApproveSerializer):
    """Serializer for approving a timesheet entry complaint proposal."""

    approved_check_in_time = serializers.TimeField(required=True, help_text="Approved check-in time")
    approved_check_out_time = serializers.TimeField(required=True, help_text="Approved check-out time")

    class Meta:
        model = Proposal
        fields = ["approved_check_in_time", "approved_check_out_time"] + ProposalApproveSerializer.Meta.fields

    def validate(self, attrs):
        # Ensure the proposal is linked to a timesheet entry before approval
        if self.instance:
            junction_exists = ProposalTimeSheetEntry.objects.filter(proposal_id=self.instance.id).exists()
            if not junction_exists:
                raise serializers.ValidationError(
                    _("This complaint proposal is not linked to a timesheet entry. Please try again later.")
                )

        attrs["timesheet_entry_complaint_approved_check_in_time"] = attrs.pop("approved_check_in_time")
        attrs["timesheet_entry_complaint_approved_check_out_time"] = attrs.pop("approved_check_out_time")
        return super().validate(attrs)

    def _get_proposal_type(self) -> ProposalType:
        return ProposalType.TIMESHEET_ENTRY_COMPLAINT


class ProposalTimesheetEntryComplaintRejectSerializer(ProposalRejectSerializer):
    """Serializer for rejecting a timesheet entry complaint proposal."""

    class Meta:
        model = Proposal
        fields = ProposalRejectSerializer.Meta.fields

    def _get_proposal_type(self) -> ProposalType:
        return ProposalType.TIMESHEET_ENTRY_COMPLAINT


# =============================================================================
# 3. COMPONENT SERIALIZERS
# =============================================================================


class ProposalOvertimeEntrySerializer(serializers.ModelSerializer):
    """Serializer for ProposalOvertimeEntry model."""

    class Meta:
        model = ProposalOvertimeEntry
        fields = ["id", "date", "start_time", "end_time", "description", "duration_hours"]
        read_only_fields = ["id", "duration_hours"]

    def validate(self, attrs):
        instance = self.instance or ProposalOvertimeEntry()
        for attr, value in attrs.items():
            setattr(instance, attr, value)

        request = self.context["request"]
        user = request.user
        if hasattr(user, "employee"):
            # NOTE: temporarily assign employee to _proposal_created_by - For validation
            # Must be an Employee instance
            instance._proposal_created_by = user.employee

        try:
            instance.clean()
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.message_dict)

        return attrs


class ProposalAssetSerializer(serializers.ModelSerializer):
    """Serializer for ProposalAsset model."""

    class Meta:
        model = ProposalAsset
        fields = ["id", "name", "unit_type", "quantity", "note"]
        read_only_fields = ["id"]


# =============================================================================
# 4. SPECIFIC PROPOSAL TYPES
# =============================================================================


class ProposalLateExemptionSerializer(ProposalByTypeSerializer):
    """Serializer for Late Exemption proposal."""

    class Meta:
        model = Proposal
        fields = ProposalByTypeSerializer.Meta.fields + [
            "late_exemption_start_date",
            "late_exemption_end_date",
            "late_exemption_minutes",
        ]
        read_only_fields = ProposalByTypeSerializer.Meta.read_only_fields


class ProposalOvertimeWorkSerializer(ProposalByTypeSerializer):
    """Serializer for Overtime Work proposal."""

    entries = ProposalOvertimeEntrySerializer(many=True, write_only=True)
    overtime_entries = ProposalOvertimeEntrySerializer(many=True, read_only=True)

    class Meta:
        model = Proposal
        fields = ProposalByTypeSerializer.Meta.fields + [
            "entries",
            "overtime_entries",
        ]
        read_only_fields = ProposalByTypeSerializer.Meta.read_only_fields + [
            "overtime_entries",
        ]

    def validate_entries(self, value):
        if not value:
            raise serializers.ValidationError(_("At least one overtime entry is required"))

        # Check for overlapping time ranges on the same date
        # Entries appearing earlier in the list are considered valid
        seen_intervals = {}  # date -> list of (start_time, end_time)
        for entry in value:
            date = entry["date"]
            start = entry["start_time"]
            end = entry["end_time"]

            if date not in seen_intervals:
                seen_intervals[date] = []

            for s, e in seen_intervals[date]:
                # Overlap condition: use model static method
                if ProposalOvertimeEntry._check_overlap(start, end, s, e):
                    raise serializers.ValidationError(
                        _(
                            "Overlapping overtime entries on %(date)s: %(start)s-%(end)s overlaps with a previous entry."
                        )
                        % {"date": date, "start": start, "end": end}
                    )

            seen_intervals[date].append((start, end))

        return value

    def create(self, validated_data):
        entries_data = validated_data.pop("entries", [])
        proposal = super().create(validated_data)
        self._create_entries_bulk(proposal, entries_data)
        return proposal

    def update(self, instance, validated_data):
        entries_data = validated_data.pop("entries", [])
        proposal = super().update(instance, validated_data)

        if entries_data:
            proposal.overtime_entries.all().delete()
            self._create_entries_bulk(proposal, entries_data)

        return proposal

    def _create_entries_bulk(self, proposal, entries_data):
        overtime_entries = [ProposalOvertimeEntry(proposal=proposal, **d) for d in entries_data]
        ProposalOvertimeEntry.objects.bulk_create(overtime_entries)


class ProposalPostMaternityBenefitsSerializer(ProposalByTypeSerializer):
    """Serializer for Post-Maternity Benefits proposal."""

    class Meta:
        model = Proposal
        fields = ProposalByTypeSerializer.Meta.fields + [
            "post_maternity_benefits_start_date",
            "post_maternity_benefits_end_date",
        ]
        read_only_fields = ProposalByTypeSerializer.Meta.read_only_fields


class ProposalAssetAllocationSerializer(ProposalByTypeSerializer):
    """Serializer for Asset Allocation proposal."""

    proposal_assets = ProposalAssetSerializer(many=True, write_only=True)
    assets = ProposalAssetSerializer(many=True, read_only=True)

    class Meta:
        model = Proposal
        fields = ProposalByTypeSerializer.Meta.fields + [
            "proposal_assets",
            "assets",
        ]
        read_only_fields = ProposalByTypeSerializer.Meta.read_only_fields + [
            "assets",
        ]

    def create(self, validated_data):
        assets_data = validated_data.pop("proposal_assets", [])
        proposal = super().create(validated_data)
        self._create_new_assets_bulk(proposal, assets_data)
        return proposal

    def update(self, instance, validated_data):
        assets_data = validated_data.pop("proposal_assets", [])
        proposal = super().update(instance, validated_data)

        if assets_data:
            proposal.assets.all().delete()
            self._create_new_assets_bulk(proposal, assets_data)

        return proposal

    def _create_new_assets_bulk(self, proposal, assets_data):
        assets = [ProposalAsset(proposal=proposal, **d) for d in assets_data]
        ProposalAsset.objects.bulk_create(assets)


class ProposalMaternityLeaveSerializer(ProposalByTypeSerializer):
    """Serializer for Maternity Leave proposal."""

    maternity_leave_replacement_employee = EmployeeSerializer(read_only=True)
    maternity_leave_replacement_employee_id = serializers.IntegerField(required=False, write_only=True)

    class Meta:
        model = Proposal
        fields = ProposalByTypeSerializer.Meta.fields + [
            "maternity_leave_start_date",
            "maternity_leave_end_date",
            "maternity_leave_estimated_due_date",
            "maternity_leave_replacement_employee",
            "maternity_leave_replacement_employee_id",
        ]
        read_only_fields = ProposalByTypeSerializer.Meta.read_only_fields + [
            "maternity_leave_replacement_employee",
        ]


class ProposalPaidLeaveSerializer(ProposalByTypeSerializer):
    """Serializer for Paid Leave proposals."""

    class Meta:
        model = Proposal
        fields = ProposalByTypeSerializer.Meta.fields + [
            "paid_leave_start_date",
            "paid_leave_end_date",
            "paid_leave_shift",
            "paid_leave_reason",
        ]
        read_only_fields = ProposalByTypeSerializer.Meta.read_only_fields


class ProposalUnpaidLeaveSerializer(ProposalByTypeSerializer):
    """Serializer for Unpaid Leave proposals."""

    class Meta:
        model = Proposal
        fields = ProposalByTypeSerializer.Meta.fields + [
            "unpaid_leave_start_date",
            "unpaid_leave_end_date",
            "unpaid_leave_shift",
            "unpaid_leave_reason",
        ]
        read_only_fields = ProposalByTypeSerializer.Meta.read_only_fields


class ProposalJobTransferSerializer(ProposalByTypeSerializer):
    """Serializer for Job Transfer proposals."""

    job_transfer_new_department_id = serializers.IntegerField(write_only=True)
    job_transfer_new_position_id = serializers.IntegerField(write_only=True)

    job_transfer_new_department = DepartmentNestedSerializer(read_only=True)
    job_transfer_new_position = PositionNestedSerializer(read_only=True)
    job_transfer_new_branch = BranchNestedSerializer(read_only=True)
    job_transfer_new_block = BlockNestedSerializer(read_only=True)

    class Meta:
        model = Proposal
        fields = ProposalByTypeSerializer.Meta.fields + [
            "job_transfer_new_branch",
            "job_transfer_new_block",
            "job_transfer_new_department_id",
            "job_transfer_new_department",
            "job_transfer_new_position_id",
            "job_transfer_new_position",
            "job_transfer_effective_date",
            "job_transfer_reason",
        ]
        read_only_fields = ProposalByTypeSerializer.Meta.read_only_fields + [
            "job_transfer_new_branch",
            "job_transfer_new_block",
            "job_transfer_new_department",
            "job_transfer_new_position",
        ]


class ProposalDeviceChangeSerializer(ProposalByTypeSerializer):
    """Serializer for Device Change proposals."""

    class Meta:
        model = Proposal
        fields = ProposalByTypeSerializer.Meta.fields + [
            "device_change_new_device_id",
            "device_change_new_platform",
            "device_change_old_device_id",
        ]
        read_only_fields = ProposalByTypeSerializer.Meta.read_only_fields


class ProposalTimesheetEntryComplaintVerifierSerializer(serializers.ModelSerializer):
    """Serializer for ProposalVerifier model specifically for Timesheet Entry Complaint."""

    employee = EmployeeSerializer(read_only=True)
    colored_status = ColoredValueSerializer(read_only=True)

    class Meta:
        model = ProposalVerifier
        fields = read_only_fields = [
            "id",
            "proposal_id",
            "employee_id",
            "employee",
            "status",
            "colored_status",
            "verified_time",
            "note",
            "created_at",
            "updated_at",
        ]


class ProposalTimesheetEntryComplaintSerializer(FileConfirmSerializerMixin, ProposalByTypeSerializer):
    """Serializer for Timesheet Entry Complaint proposal."""

    file_confirm_fields = ["timesheet_entry_complaint_complaint_image"]

    timesheet_entry_id = serializers.SerializerMethodField()
    proposal_verifier = ProposalTimesheetEntryComplaintVerifierSerializer(read_only=True, source="verifiers.first")

    timesheet_entry_complaint_complaint_image = FileSerializer(read_only=True)

    class Meta(ProposalByTypeSerializer.Meta):
        fields = ProposalByTypeSerializer.Meta.fields + [
            "timesheet_entry_id",
            "timesheet_entry_complaint_complaint_date",
            "timesheet_entry_complaint_complaint_reason",
            "timesheet_entry_complaint_proposed_check_in_time",
            "timesheet_entry_complaint_proposed_check_out_time",
            "timesheet_entry_complaint_approved_check_in_time",
            "timesheet_entry_complaint_approved_check_out_time",
            "timesheet_entry_complaint_latitude",
            "timesheet_entry_complaint_longitude",
            "timesheet_entry_complaint_address",
            "timesheet_entry_complaint_complaint_image",
            "proposal_verifier",
        ]
        read_only_fields = ProposalByTypeSerializer.Meta.read_only_fields + [
            "timesheet_entry_complaint_approved_check_in_time",
            "timesheet_entry_complaint_approved_check_out_time",
        ]

    def get_timesheet_entry_id(self, obj: Proposal) -> int | None:
        junction = ProposalTimeSheetEntry.objects.filter(proposal_id=obj.id).only("timesheet_entry_id").first()
        if junction:
            return junction.timesheet_entry_id
        return None


# =============================================================================
# 5. COMBINED SERIALIZER
# =============================================================================


class ProposalCombinedSerializer(
    ProposalLateExemptionSerializer,
    ProposalOvertimeWorkSerializer,
    ProposalPostMaternityBenefitsSerializer,
    ProposalAssetAllocationSerializer,
    ProposalMaternityLeaveSerializer,
    ProposalPaidLeaveSerializer,
    ProposalUnpaidLeaveSerializer,
    ProposalJobTransferSerializer,
    ProposalTimesheetEntryComplaintSerializer,
):
    """Combined serializer for all proposal types."""

    class Meta:
        model = Proposal
        fields = (
            ProposalByTypeSerializer.Meta.fields
            + ProposalOvertimeWorkSerializer.Meta.read_only_fields
            + ProposalAssetAllocationSerializer.Meta.read_only_fields
            + [
                "late_exemption_start_date",
                "late_exemption_end_date",
                "late_exemption_minutes",
                "post_maternity_benefits_start_date",
                "post_maternity_benefits_end_date",
                "maternity_leave_start_date",
                "maternity_leave_end_date",
                "maternity_leave_estimated_due_date",
                "maternity_leave_replacement_employee",
                "paid_leave_start_date",
                "paid_leave_end_date",
                "paid_leave_shift",
                "paid_leave_reason",
                "unpaid_leave_start_date",
                "unpaid_leave_end_date",
                "unpaid_leave_shift",
                "unpaid_leave_reason",
                "job_transfer_new_branch",
                "job_transfer_new_block",
                "job_transfer_new_department",
                "job_transfer_new_position",
                "job_transfer_effective_date",
                "job_transfer_reason",
                "device_change_new_device_id",
                "device_change_new_platform",
                "device_change_old_device_id",
                # Timesheet Entry Complaint fields
                "timesheet_entry_id",
                "timesheet_entry_complaint_complaint_date",
                "timesheet_entry_complaint_complaint_reason",
                "timesheet_entry_complaint_proposed_check_in_time",
                "timesheet_entry_complaint_proposed_check_out_time",
                "timesheet_entry_complaint_approved_check_in_time",
                "timesheet_entry_complaint_approved_check_out_time",
                "timesheet_entry_complaint_latitude",
                "timesheet_entry_complaint_longitude",
                "timesheet_entry_complaint_address",
                "timesheet_entry_complaint_complaint_image",
                "proposal_verifier",
            ]
        )
        read_only_fields = fields


# =============================================================================
# 6. VERIFIER SERIALIZERS
# =============================================================================


class ProposalVerifierSerializer(serializers.ModelSerializer):
    """Serializer for ProposalVerifier model."""

    proposal_id = serializers.IntegerField(write_only=True)
    employee_id = serializers.IntegerField(write_only=True)

    proposal = ProposalCombinedSerializer(read_only=True)
    employee = EmployeeSerializer(read_only=True)

    colored_status = ColoredValueSerializer(read_only=True)

    class Meta:
        model = ProposalVerifier
        fields = [
            "id",
            "proposal_id",
            "employee_id",
            "proposal",
            "employee",
            "status",
            "colored_status",
            "verified_time",
            "note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "colored_status",
            "created_at",
            "updated_at",
            "proposal",
            "employee",
        ]


class ProposalVerifierListSerializer(ProposalVerifierSerializer):
    """
    Serializer for listing ProposalVerifiers.

    This use normal ProposalSerializer for not overloading the response.
    """

    proposal = ProposalSerializer(read_only=True)


class ProposalVerifierVerifySerializer(serializers.ModelSerializer):
    """Serializer for verifying a ProposalVerifier."""

    note = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = ProposalVerifier
        fields = ["note"]

    def validate(self, attrs):
        if not self.instance:
            raise serializers.ValidationError("This serializer requires an existing verifier instance")

        user = self.context["request"].user
        employee = self.instance.employee

        if user.employee != employee.department.leader:
            raise serializers.ValidationError("Only the department leader can verify this proposal")

        return attrs

    def update(self, instance, validated_data):
        from apps.hrm.constants import ProposalVerifierStatus

        instance.status = ProposalVerifierStatus.VERIFIED
        instance.verified_time = timezone.now()
        if validated_data.get("note"):
            instance.note = validated_data["note"]

        instance.save()
        return instance


class ProposalVerifierRejectSerializer(serializers.ModelSerializer):
    """Serializer for rejecting a ProposalVerifier."""

    note = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = ProposalVerifier
        fields = ["note"]

    def validate(self, attrs):
        if not self.instance:
            raise serializers.ValidationError(_("This serializer requires an existing verifier instance"))

        user = self.context["request"].user
        if user.employee != self.instance.employee.department.leader:
            raise serializers.ValidationError(_("Only the department leader can reject this proposal"))

        return attrs

    def update(self, instance, validated_data):
        from apps.hrm.constants import ProposalVerifierStatus

        instance.status = ProposalVerifierStatus.NOT_VERIFIED
        instance.verified_time = timezone.now()
        if validated_data.get("note"):
            instance.note = validated_data["note"]

        instance.save()
        return instance


class ProposalVerifierNeedVerificationSerializer(ProposalVerifierSerializer):
    """Serializer for ProposalVerifier model used in need-verification view."""

    proposal = ProposalCombinedSerializer(read_only=True)
    employee = EmployeeSerializer(read_only=True)

    class Meta:
        model = ProposalVerifier
        fields = [
            "id",
            "proposal",
            "employee",
            "colored_status",
            "verified_time",
            "note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


# =============================================================================
# 7. EXPORT XLSX SERIALIZERS
# =============================================================================


class ProposalExportXLSXSerializer(FieldFilteringSerializerMixin, serializers.ModelSerializer):
    """Base serializer for Proposal XLSX export."""

    proposal_status = serializers.CharField(source="colored_proposal_status.value", read_only=True, label="Status")
    created_by_code = serializers.CharField(source="created_by.code", read_only=True, label="Created By Code")
    created_by_name = serializers.CharField(source="created_by.fullname", read_only=True, label="Created By Name")
    approved_by_code = serializers.CharField(
        source="approved_by.code", read_only=True, allow_null=True, label="Approved By Code"
    )
    approved_by_name = serializers.CharField(
        source="approved_by.fullname", read_only=True, allow_null=True, label="Approved By Name"
    )

    class Meta:
        model = Proposal
        fields = [
            "id",
            "code",
            "proposal_date",
            "proposal_type",
            "proposal_status",
            "note",
            "created_by_code",
            "created_by_name",
            "approved_by_code",
            "approved_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ProposalTimesheetEntryComplaintExportXLSXSerializer(ProposalExportXLSXSerializer):
    """Export serializer for Timesheet Entry Complaint proposals."""

    class Meta:
        model = Proposal
        fields = ProposalExportXLSXSerializer.Meta.fields + [
            "timesheet_entry_complaint_complaint_reason",
            "timesheet_entry_complaint_proposed_check_in_time",
            "timesheet_entry_complaint_proposed_check_out_time",
            "timesheet_entry_complaint_approved_check_in_time",
            "timesheet_entry_complaint_approved_check_out_time",
        ]
        read_only_fields = fields


class ProposalLateExemptionExportXLSXSerializer(ProposalExportXLSXSerializer):
    """Export serializer for Late Exemption proposals."""

    class Meta:
        model = Proposal
        fields = ProposalExportXLSXSerializer.Meta.fields + [
            "late_exemption_start_date",
            "late_exemption_end_date",
            "late_exemption_minutes",
        ]
        read_only_fields = fields


class ProposalOvertimeWorkExportXLSXSerializer(ProposalExportXLSXSerializer):
    """Export serializer for Overtime Work proposals."""

    class Meta:
        model = Proposal
        fields = ProposalExportXLSXSerializer.Meta.fields
        read_only_fields = fields


class ProposalPostMaternityBenefitsExportXLSXSerializer(ProposalExportXLSXSerializer):
    """Export serializer for Post-Maternity Benefits proposals."""

    class Meta:
        model = Proposal
        fields = ProposalExportXLSXSerializer.Meta.fields + [
            "post_maternity_benefits_start_date",
            "post_maternity_benefits_end_date",
        ]
        read_only_fields = fields


class ProposalPaidLeaveExportXLSXSerializer(ProposalExportXLSXSerializer):
    """Export serializer for Paid Leave proposals."""

    class Meta:
        model = Proposal
        fields = ProposalExportXLSXSerializer.Meta.fields + [
            "paid_leave_start_date",
            "paid_leave_end_date",
            "paid_leave_shift",
            "paid_leave_reason",
        ]
        read_only_fields = fields


class ProposalUnpaidLeaveExportXLSXSerializer(ProposalExportXLSXSerializer):
    """Export serializer for Unpaid Leave proposals."""

    class Meta:
        model = Proposal
        fields = ProposalExportXLSXSerializer.Meta.fields + [
            "unpaid_leave_start_date",
            "unpaid_leave_end_date",
            "unpaid_leave_shift",
            "unpaid_leave_reason",
        ]
        read_only_fields = fields


class ProposalMaternityLeaveExportXLSXSerializer(ProposalExportXLSXSerializer):
    """Export serializer for Maternity Leave proposals."""

    replacement_employee_code = serializers.CharField(
        source="maternity_leave_replacement_employee.code",
        read_only=True,
        allow_null=True,
        label="Replacement Employee Code",
    )
    replacement_employee_name = serializers.CharField(
        source="maternity_leave_replacement_employee.fullname",
        read_only=True,
        allow_null=True,
        label="Replacement Employee Name",
    )

    class Meta:
        model = Proposal
        fields = ProposalExportXLSXSerializer.Meta.fields + [
            "maternity_leave_start_date",
            "maternity_leave_end_date",
            "maternity_leave_estimated_due_date",
            "replacement_employee_code",
            "replacement_employee_name",
        ]
        read_only_fields = fields


class ProposalJobTransferExportXLSXSerializer(ProposalExportXLSXSerializer):
    """Export serializer for Job Transfer proposals."""

    new_branch_name = serializers.CharField(
        source="job_transfer_new_branch.name",
        read_only=True,
        allow_null=True,
        label="New Branch",
    )
    new_block_name = serializers.CharField(
        source="job_transfer_new_block.name",
        read_only=True,
        allow_null=True,
        label="New Block",
    )
    new_department_name = serializers.CharField(
        source="job_transfer_new_department.name",
        read_only=True,
        allow_null=True,
        label="New Department",
    )
    new_position_name = serializers.CharField(
        source="job_transfer_new_position.name",
        read_only=True,
        allow_null=True,
        label="New Position",
    )

    class Meta:
        model = Proposal
        fields = ProposalExportXLSXSerializer.Meta.fields + [
            "new_branch_name",
            "new_block_name",
            "new_department_name",
            "new_position_name",
            "job_transfer_effective_date",
            "job_transfer_reason",
        ]
        read_only_fields = fields


class ProposalAssetAllocationExportXLSXSerializer(ProposalExportXLSXSerializer):
    """Export serializer for Asset Allocation proposals."""

    class Meta:
        model = Proposal
        fields = ProposalExportXLSXSerializer.Meta.fields
        read_only_fields = fields


class ProposalDeviceChangeExportXLSXSerializer(ProposalExportXLSXSerializer):
    """Serializer for Device Change proposal XLSX export."""

    class Meta(ProposalExportXLSXSerializer.Meta):
        fields = ProposalExportXLSXSerializer.Meta.fields + [
            "device_change_new_device_id",
            "device_change_new_platform",
            "device_change_old_device_id",
        ]
        read_only_fields = fields
