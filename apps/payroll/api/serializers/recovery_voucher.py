from datetime import date

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.hrm.api.serializers.common_nested import (
    BlockNestedSerializer,
    BranchNestedSerializer,
    DepartmentNestedSerializer,
    EmployeeNestedSerializer,
    PositionNestedSerializer,
)
from apps.hrm.models import Employee
from apps.payroll.models import RecoveryVoucher


class RecoveryVoucherSerializer(serializers.ModelSerializer):
    """Serializer for recovery and back pay vouchers."""

    voucher_type_display = serializers.CharField(source="get_voucher_type_display", read_only=True)
    employee = EmployeeNestedSerializer(read_only=True)
    employee_code = serializers.CharField(read_only=True)
    employee_name = serializers.CharField(read_only=True)
    block = BlockNestedSerializer(source="employee.block", read_only=True)
    branch = BranchNestedSerializer(source="employee.branch", read_only=True)
    department = DepartmentNestedSerializer(source="employee.department", read_only=True)
    position = PositionNestedSerializer(source="employee.position", read_only=True)
    employee_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(),
        source="employee",
        write_only=True,
    )
    month = serializers.CharField(
        max_length=7,
        help_text="Month in MM/YYYY format (e.g., 09/2025)",
    )

    class Meta:
        model = RecoveryVoucher
        fields = [
            "id",
            "code",
            "name",
            "voucher_type",
            "voucher_type_display",
            "employee",
            "employee_code",
            "employee_name",
            "block",
            "branch",
            "department",
            "position",
            "amount",
            "month",
            "employee_id",
            "status",
            "note",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "code",
            "block",
            "branch",
            "department",
            "position",
            "employee_code",
            "employee_name",
            "status",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]

    def to_representation(self, instance):
        """Format month as MM/YYYY when returning data."""
        data = super().to_representation(instance)

        if instance.month:
            data["month"] = f"{instance.month.month:02d}/{instance.month.year}"
        return data

    def validate_month(self, value):
        """Validate that month is provided in MM/YYYY format."""
        if not value:
            raise serializers.ValidationError(_("Month is required."))

        try:
            month_str, year_str = value.split("/")
            month = int(month_str)
            year = int(year_str)

            if month < 1 or month > 12:
                raise serializers.ValidationError(_("Month must be between 1 and 12."))

            return date(year, month, 1)
        except (ValueError, TypeError):
            raise serializers.ValidationError(_("Month must be in MM/YYYY format."))

    def validate_employee_id(self, value):
        """Validate that employee exists and is active."""
        if not value:
            raise serializers.ValidationError(_("Employee is required."))
        if value.status not in Employee.Status.get_working_statuses():
            raise serializers.ValidationError(_("Employee must be in active or onboarding status."))

        return value

    def validate_amount(self, value):
        """Validate that amount is greater than 0."""
        if value <= 0:
            raise serializers.ValidationError(_("Amount must be greater than 0."))
        return value

    def validate_name(self, value):
        """Validate name field."""
        if not value or not value.strip():
            raise serializers.ValidationError(_("Name is required."))
        if len(value) > 250:
            raise serializers.ValidationError(_("Name must not exceed 250 characters."))
        return value.strip()

    def validate_note(self, value):
        """Validate note field."""
        if value and len(value) > 500:
            raise serializers.ValidationError(_("Note must not exceed 500 characters."))
        return value

    def create(self, validated_data):
        """Create a new recovery voucher."""
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            validated_data["created_by"] = request.user
            validated_data["updated_by"] = request.user

        try:
            instance = RecoveryVoucher.objects.create(**validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict)

        return instance

    def update(self, instance, validated_data):
        """Update an existing recovery voucher."""
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            validated_data["updated_by"] = request.user

        validated_data["status"] = RecoveryVoucher.RecoveryVoucherStatus.NOT_CALCULATED

        for field, value in validated_data.items():
            setattr(instance, field, value)

        try:
            instance.save()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict)

        return instance
