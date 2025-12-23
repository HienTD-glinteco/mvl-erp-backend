from datetime import date

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
from apps.payroll.models import TravelExpense


class TravelExpenseSerializer(serializers.ModelSerializer):
    """Serializer for TravelExpense model.

    Handles validation, serialization, and formatting of travel expense data.
    Supports month input in MM/YYYY format and auto-generates code.

    For read operations, returns nested employee object with id, code, and fullname.
    For write operations, accepts employee_id.
    """

    # Nested read-only serializer for full object representation
    employee = EmployeeNestedSerializer(read_only=True)
    block = BlockNestedSerializer(source="employee.block", read_only=True)
    branch = BranchNestedSerializer(source="employee.branch", read_only=True)
    department = DepartmentNestedSerializer(source="employee.department", read_only=True)
    position = PositionNestedSerializer(source="employee.position", read_only=True)

    # Write-only field for POST/PUT/PATCH operations
    employee_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(),
        source="employee",
        write_only=True,
    )

    month = serializers.CharField(
        max_length=7,
        help_text="Month in MM/YYYY format (e.g., 11/2025)",
    )

    class Meta:
        model = TravelExpense
        fields = [
            "id",
            "code",
            "name",
            "expense_type",
            "employee",
            "block",
            "branch",
            "department",
            "position",
            "employee_id",
            "amount",
            "month",
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
            "status",
            "block",
            "branch",
            "department",
            "position",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]

    def validate_name(self, value):
        """Validate name field."""
        if not value or not value.strip():
            raise serializers.ValidationError(_("Name is required"))
        if len(value) > 250:
            raise serializers.ValidationError(_("Name must not exceed 250 characters"))
        return value.strip()

    def validate_amount(self, value):
        """Validate amount field."""
        if value is None:
            raise serializers.ValidationError(_("Amount is required"))
        if value < 1:
            raise serializers.ValidationError(_("Amount must be greater than 0"))
        return value

    def validate_employee_id(self, value):
        """Validate employee field."""
        if not value:
            raise serializers.ValidationError(_("Employee is required"))

#        if value.status != Employee.Status.ACTIVE:
#            raise serializers.ValidationError(_("Employee must be active"))

        return value

    def validate_month(self, value):
        """Validate and convert month from MM/YYYY to date (first day of month)."""
        if not value:
            raise serializers.ValidationError(_("Month is required"))

        # Parse MM/YYYY format
        try:
            parts = value.split("/")
            if len(parts) != 2:
                raise ValueError("Invalid format")

            month_str, year_str = parts
            month = int(month_str)
            year = int(year_str)

            if month < 1 or month > 12:
                raise serializers.ValidationError(_("Month must be between 1 and 12"))

            if year < 1900 or year > 2100:
                raise serializers.ValidationError(_("Year must be between 1900 and 2100"))

            # Return as first day of the month
            return date(year, month, 1)

        except (ValueError, TypeError):
            raise serializers.ValidationError(_("Month must be in MM/YYYY format (e.g., 11/2025)"))

    def to_representation(self, instance):
        """Convert date month back to MM/YYYY format for output."""
        data = super().to_representation(instance)

        # Convert month date to MM/YYYY format
        if instance.month:
            data["month"] = f"{instance.month.month:02d}/{instance.month.year}"

        return data

    def validate(self, data):
        """Perform cross-field validation."""
        # Validation is already done in individual field validators
        return data

    def update(self, instance, validated_data):
        """Override update to reset status to NOT_CALCULATED."""
        # Status is automatically reset to NOT_CALCULATED on update per business rules
        validated_data["status"] = TravelExpense.TravelExpenseStatus.NOT_CALCULATED
        return super().update(instance, validated_data)
