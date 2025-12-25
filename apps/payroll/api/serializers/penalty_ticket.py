"""Serializers for penalty ticket API."""

from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.files.api.serializers.file_serializers import FileSerializer
from apps.files.api.serializers.mixins import FileConfirmSerializerMixin
from apps.files.models import FileModel
from apps.hrm.api.serializers.common_nested import (
    BlockNestedSerializer,
    BranchNestedSerializer,
    DepartmentNestedSerializer,
    EmployeeNestedSerializer,
    PositionNestedSerializer,
)
from apps.hrm.models import Employee
from apps.payroll.models import PenaltyTicket


class PenaltyTicketSerializer(FileConfirmSerializerMixin, serializers.ModelSerializer):
    """Serializer for PenaltyTicket CRUD operations."""

    employee = EmployeeNestedSerializer(read_only=True)
    employee_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(),
        source="employee",
        write_only=True,
    )
    block = BlockNestedSerializer(source="employee.block", read_only=True)
    branch = BranchNestedSerializer(source="employee.branch", read_only=True)
    department = DepartmentNestedSerializer(source="employee.department", read_only=True)
    position = PositionNestedSerializer(source="employee.position", read_only=True)
    month = serializers.CharField(max_length=7, help_text="Month in MM/YYYY format")
    violation_count = serializers.IntegerField(min_value=1, default=1, help_text="Number of violations in the ticket")
    violation_type = serializers.ChoiceField(
        choices=PenaltyTicket.ViolationType.choices,
        default=PenaltyTicket.ViolationType.OTHER,
        help_text="Type of violation",
    )
    status = serializers.ChoiceField(
        choices=PenaltyTicket.Status.choices, default=PenaltyTicket.Status.UNPAID, help_text="Penalty payment status"
    )
    attachments = FileSerializer(many=True, read_only=True)

    # Write-only field for attachment IDs
    attachment_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        allow_empty=False,
        help_text="List of confirmed file IDs to attach to this ticket",
    )

    class Meta:
        model = PenaltyTicket
        fields = [
            "id",
            "code",
            "month",
            "payment_date",
            "employee",
            "employee_id",
            "block",
            "branch",
            "department",
            "position",
            "violation_count",
            "violation_type",
            "amount",
            "status",
            "note",
            "attachments",
            "attachment_ids",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "code",
            "employee_code",
            "employee_name",
            "attachments",
            "created_at",
            "updated_at",
        ]

    def validate_month(self, value):
        """Validate month format is MM/YYYY and convert to date."""
        try:
            month, year = value.split("/")
            month = int(month)
            year = int(year)

            if month < 1 or month > 12:
                raise ValueError("Month must be between 1 and 12")

            from datetime import date

            return date(year, month, 1)

        except (ValueError, AttributeError) as e:
            raise serializers.ValidationError(f"Month must be in MM/YYYY format. Error: {str(e)}")

    def validate_amount(self, value):
        """Ensure amount is positive."""
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0")
        return value

    def validate_payment_date(self, value):
        """Ensure payment date is not in the future and not before penalty month."""
        if value:
            if value > timezone.now().date():
                raise serializers.ValidationError(_("Payment date cannot be in the future."))
            month = self.initial_data.get("month")
            if month:
                month_date = self.validate_month(month)
                if value < month_date:
                    raise serializers.ValidationError(_("Payment date cannot be before the penalty month."))
        return value

    def validate(self, attrs):
        """Cross-field validation."""
        # Populate employee snapshot fields on create
        if not self.instance and "employee" in attrs:
            employee = attrs["employee"]
            attrs["employee_code"] = employee.code
            attrs["employee_name"] = employee.fullname

        return attrs

    def validate_attachment_ids(self, value):
        """Validate that all attachment IDs exist in the database."""
        if not value:
            return value

        # Get existing file IDs
        existing_ids = set(FileModel.objects.filter(id__in=value, is_confirmed=True).values_list("id", flat=True))
        provided_ids = set(value)

        # Check for missing IDs
        missing_ids = provided_ids - existing_ids
        if missing_ids:
            raise serializers.ValidationError(
                _("File IDs not found or not confirmed: {ids}").format(ids=list(missing_ids))
            )

        return value

    def create(self, validated_data):
        """Create PenaltyTicket and link attachments."""
        attachment_ids = validated_data.pop("attachment_ids", [])
        instance = super().create(validated_data)
        if attachment_ids:
            self._link_attachments(instance, attachment_ids)

        return instance

    def update(self, instance, validated_data):
        """Update PenaltyTicket and link attachments."""
        attachment_ids = validated_data.pop("attachment_ids", None)
        instance = super().update(instance, validated_data)

        # Only update attachments if attachment_ids was provided in the request
        if attachment_ids is not None:
            self._link_attachments(instance, attachment_ids)

        return instance

    def _link_attachments(self, instance, attachment_ids):
        """Link file attachments to the PenaltyTicket instance.

        Uses GenericRelation's set() method to efficiently replace all attachments.

        Args:
            instance: The PenaltyTicket instance to link files to
            attachment_ids: List of FileModel IDs to link
        """
        # Get the FileModel instances to link
        files_to_link = FileModel.objects.filter(id__in=attachment_ids)

        # Use GenericRelation's set() method to replace all attachments
        instance.attachments.set(files_to_link)

    def to_representation(self, instance):
        """Convert date fields and attachments for API response."""
        ret = super().to_representation(instance)
        if instance.month:
            ret["month"] = instance.month.strftime("%m/%Y")
        ret["attachments"] = [str(file.id) for file in instance.attachments.all()]
        return ret


class PenaltyTicketUpdateSerializer(PenaltyTicketSerializer):
    """Serializer for updating penalty tickets.

    Code field is immutable. Period changes are not recommended but allowed.
    """

    class Meta(PenaltyTicketSerializer.Meta):
        read_only_fields = PenaltyTicketSerializer.Meta.read_only_fields + ["code"]


class BulkUpdateStatusSerializer(serializers.Serializer):
    """Serializer for bulk payment status updates."""

    ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
        help_text="List of penalty ticket IDs",
    )
    status = serializers.ChoiceField(choices=PenaltyTicket.Status.choices, help_text="Desired payment status")

    def validate_ids(self, value):
        existing_ids = set(PenaltyTicket.objects.filter(id__in=value).values_list("id", flat=True))
        missing_ids = sorted(set(value) - existing_ids)
        if missing_ids:
            raise serializers.ValidationError(f"Tickets not found: {missing_ids}")
        return value

    def bulk_update_status(self):
        """Bulk update payment status for given ticket IDs."""
        ids = self.validated_data["ids"]
        tickets = PenaltyTicket.objects.filter(id__in=ids)
        for ticket in tickets:
            ticket.status = self.validated_data["status"]
            ticket.updated_by = self.context["request"].user
            ticket.save(update_fields=["status", "updated_by"])
        return len(tickets)
