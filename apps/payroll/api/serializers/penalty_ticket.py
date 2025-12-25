"""Serializers for penalty ticket API."""

from rest_framework import serializers

from apps.files.models import FileModel
from apps.hrm.api.serializers.common_nested import (
    BlockNestedSerializer,
    BranchNestedSerializer,
    DepartmentNestedSerializer,
    EmployeeNestedSerializer,
    PositionNestedSerializer,
)
from apps.hrm.models import Employee
from apps.payroll.constants import PaymentStatus, PayrollStatus, ViolationType
from apps.payroll.models import PenaltyTicket


class PenaltyTicketSerializer(serializers.ModelSerializer):
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
        choices=ViolationType.choices, default=ViolationType.OTHER, help_text="Type of violation"
    )
    payment_status = serializers.ChoiceField(
        choices=PaymentStatus.choices, default=PaymentStatus.UNPAID, help_text="Penalty payment status"
    )
    payroll_status = serializers.ChoiceField(
        choices=PayrollStatus.choices, default=PayrollStatus.NOT_CALCULATED, help_text="Payroll calculation status"
    )
    attachments = serializers.PrimaryKeyRelatedField(
        queryset=FileModel.objects.all(),
        many=True,
        required=False,
        allow_empty=True,
        help_text="List of file IDs for attachments",
    )

    class Meta:
        model = PenaltyTicket
        fields = [
            "id",
            "code",
            "month",
            "employee",
            "employee_id",
            "block",
            "branch",
            "department",
            "position",
            "violation_count",
            "violation_type",
            "amount",
            "payment_status",
            "payroll_status",
            "note",
            "attachments",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "code",
            "employee_code",
            "employee_name",
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

    def validate(self, attrs):
        """Cross-field validation."""
        # Populate employee snapshot fields on create
        if not self.instance and "employee" in attrs:
            employee = attrs["employee"]
            attrs["employee_code"] = employee.code
            attrs["employee_name"] = employee.fullname

        return attrs

    def create(self, validated_data):
        """Create penalty ticket with attachments."""
        attachments = validated_data.pop("attachments", [])
        ticket = super().create(validated_data)
        if attachments:
            ticket.attachments.set(attachments)
        return ticket

    def update(self, instance, validated_data):
        """Update penalty ticket with attachments."""
        attachments = validated_data.pop("attachments", None)
        ticket = super().update(instance, validated_data)
        if attachments is not None:
            ticket.attachments.set(attachments)
        return ticket

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


class PaymentStatusUpdateSerializer(serializers.Serializer):
    """Serializer for bulk payment status updates."""

    ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
        help_text="List of penalty ticket IDs",
    )
    payment_status = serializers.ChoiceField(choices=PaymentStatus.choices, help_text="Desired payment status")

    def validate_ids(self, value):
        existing_ids = set(PenaltyTicket.objects.filter(id__in=value).values_list("id", flat=True))
        missing_ids = sorted(set(value) - existing_ids)
        if missing_ids:
            raise serializers.ValidationError(f"Tickets not found: {missing_ids}")
        return value
