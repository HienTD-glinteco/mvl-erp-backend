"""Serializers for penalty ticket API."""

from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.files.api.serializers.file_serializers import FileSerializer
from apps.files.api.serializers.mixins import FileConfirmSerializerMixin
from apps.hrm.api.serializers.common_nested import (
    BlockNestedSerializer,
    BranchNestedSerializer,
    DepartmentNestedSerializer,
    EmployeeNestedSerializer,
    PositionNestedSerializer,
)
from apps.hrm.models import Employee
from apps.notifications.utils import create_notification
from apps.payroll.models import PenaltyTicket


class PenaltyTicketSerializer(FileConfirmSerializerMixin, serializers.ModelSerializer):
    """Serializer for PenaltyTicket CRUD operations."""

    file_confirm_fields = ["attachments"]
    file_multi_valued_fields = ["attachments"]

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
            if value > timezone.localdate():
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

    def create(self, validated_data):
        actor = None
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            actor = request.user
        # audit fields
        validated_data.setdefault("created_by", actor)
        validated_data.setdefault("updated_by", actor)
        ticket = super().create(validated_data)
        # notify on create
        recipient = getattr(ticket.employee, "user", None)
        if actor and recipient:
            create_notification(
                actor=actor,
                recipient=recipient,
                verb="penalty_ticket_created",
                target=ticket,
                message=(
                    _(
                        "New penalty ticket {code} ({violation}) was created for you. Please check the ticket list for details."
                    ).format(code=ticket.code, violation=ticket.get_violation_type_display())
                ),
                extra_data={
                    "ticket_id": str(ticket.id),
                    "code": ticket.code,
                    "violation_type": ticket.violation_type,
                },
                delivery_method="firebase",
                target_client="mobile",
            )
        return ticket

    def to_representation(self, instance):
        """Convert month field for API response."""
        ret = super().to_representation(instance)
        if instance.month:
            ret["month"] = instance.month.strftime("%m/%Y")
        return ret


class PenaltyTicketUpdateSerializer(PenaltyTicketSerializer):
    """Serializer for updating penalty tickets.

    Code field is immutable. Period changes are not recommended but allowed.
    """

    class Meta(PenaltyTicketSerializer.Meta):
        read_only_fields = PenaltyTicketSerializer.Meta.read_only_fields + ["code"]

    def update(self, instance, validated_data):
        actor = None
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            actor = request.user
        old_status = instance.status
        # ensure audit
        if actor is not None:
            validated_data["updated_by"] = actor
        # if status provided and not PAID, clear payment_date
        new_status = validated_data.get("status", instance.status)
        if new_status != PenaltyTicket.Status.PAID:
            validated_data["payment_date"] = None
        ticket = super().update(instance, validated_data)
        # notify when transitioning to PAID
        if actor and ticket.status == PenaltyTicket.Status.PAID and old_status != PenaltyTicket.Status.PAID:
            recipient = getattr(ticket.employee, "user", None)
            if recipient:
                create_notification(
                    actor=actor,
                    recipient=recipient,
                    verb="penalty_ticket_paid",
                    target=ticket,
                    message=_("Your penalty ticket {code} has been marked as paid.").format(code=ticket.code),
                    extra_data={
                        "ticket_id": str(ticket.id),
                        "code": ticket.code,
                        "status": ticket.status,
                    },
                    delivery_method="firebase",
                    target_client="mobile",
                )
        return ticket


class BulkUpdateStatusSerializer(serializers.Serializer):
    """Serializer for bulk payment status updates."""

    ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
        help_text="List of penalty ticket IDs",
    )
    status = serializers.ChoiceField(choices=PenaltyTicket.Status.choices, help_text="Desired payment status")
    payment_date = serializers.DateField(required=True, help_text="Payment date to set when marking as PAID")

    def validate_payment_date(self, value):
        """Ensure payment date is not in the future and not before penalty month."""
        if value:
            if value > timezone.localdate():
                raise serializers.ValidationError(_("Payment date cannot be in the future."))
        return value

    def validate_ids(self, value):
        existing_ids = set(PenaltyTicket.objects.filter(id__in=value).values_list("id", flat=True))
        missing_ids = sorted(set(value) - existing_ids)
        if missing_ids:
            raise serializers.ValidationError(_("Tickets not found: {missing_ids}").format(missing_ids=missing_ids))
        return value

    def bulk_update_status(self):
        """Bulk update payment status for given ticket IDs."""
        ids = self.validated_data["ids"]
        new_status = self.validated_data["status"]
        payment_date = self.validated_data.get("payment_date")
        actor = self.context["request"].user

        tickets = PenaltyTicket.objects.filter(id__in=ids)
        updated_count = 0
        for ticket in tickets:
            old_status = ticket.status
            ticket.status = new_status
            ticket.updated_by = actor
            if new_status == PenaltyTicket.Status.PAID:
                ticket.payment_date = payment_date
            else:
                ticket.payment_date = None
            ticket.save(update_fields=["status", "payment_date", "updated_by"])
            updated_count += 1

            # Send notification when marked as PAID from a different status
            if new_status == PenaltyTicket.Status.PAID and old_status != PenaltyTicket.Status.PAID:
                recipient = getattr(ticket.employee, "user", None)
                if recipient:
                    create_notification(
                        actor=actor,
                        recipient=recipient,
                        verb="penalty_ticket_paid",
                        target=ticket,
                        message=(_("Your penalty ticket {code} has been marked as paid.").format(code=ticket.code)),
                        extra_data={
                            "ticket_id": str(ticket.id),
                            "code": ticket.code,
                            "status": ticket.status,
                        },
                        delivery_method="firebase",
                        target_client="mobile",
                    )
        return updated_count
