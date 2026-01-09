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
from apps.payroll.models import SalesRevenue


class SalesRevenueSerializer(serializers.ModelSerializer):
    """Serializer for SalesRevenue model.

    Handles validation, serialization, and formatting of sales revenue data.
    Supports month input in MM/YYYY format and auto-generates code.

    For read operations, returns nested employee object with organizational info.
    For write operations, accepts employee_id.
    """

    employee = EmployeeNestedSerializer(read_only=True)
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
        help_text="Month in MM/YYYY format (e.g., 11/2025)",
    )

    class Meta:
        model = SalesRevenue
        fields = [
            "id",
            "code",
            "employee",
            "block",
            "branch",
            "department",
            "position",
            "employee_id",
            "kpi_target",
            "revenue",
            "transaction_count",
            "month",
            "status",
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

    def validate_revenue(self, value):
        """Validate revenue field."""
        if value is None:
            raise serializers.ValidationError(_("Revenue is required"))
        if value < 0:
            raise serializers.ValidationError(_("Revenue must be non-negative"))
        return value

    def validate_transaction_count(self, value):
        """Validate transaction_count field."""
        if value is None:
            raise serializers.ValidationError(_("Transaction count is required"))
        if value < 0:
            raise serializers.ValidationError(_("Transaction count must be non-negative"))
        return value

    def validate_employee_id(self, value):
        """Validate employee field."""
        if not value:
            raise serializers.ValidationError(_("Employee is required"))

        if value.status != "Active":
            raise serializers.ValidationError(_("Employee must be active"))

        return value

    def validate_month(self, value):
        """Validate and convert month from MM/YYYY to date (first day of month)."""
        if not value:
            raise serializers.ValidationError(_("Month is required"))

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

            return date(year, month, 1)

        except (ValueError, TypeError):
            raise serializers.ValidationError(_("Month must be in MM/YYYY format (e.g., 11/2025)"))

    def to_representation(self, instance):
        """Convert date month back to MM/YYYY format for output."""
        data = super().to_representation(instance)

        if instance.month:
            data["month"] = f"{instance.month.month:02d}/{instance.month.year}"

        return data

    def validate(self, data):
        """Perform cross-field validation."""
        employee = data.get("employee")
        month = data.get("month")

        if employee and month and self.instance is None:
            if SalesRevenue.objects.filter(employee=employee, month=month).exists():
                raise serializers.ValidationError(_("Sales revenue for this employee and month already exists"))

        if employee and month and self.instance:
            if SalesRevenue.objects.filter(employee=employee, month=month).exclude(pk=self.instance.pk).exists():
                raise serializers.ValidationError(_("Sales revenue for this employee and month already exists"))

        return data

    def update(self, instance, validated_data):
        """Override update to reset status to NOT_CALCULATED."""
        validated_data["status"] = SalesRevenue.SalesRevenueStatus.NOT_CALCULATED
        return super().update(instance, validated_data)


class SalesRevenueExportSerializer(serializers.ModelSerializer):
    """Serializer for SalesRevenue XLSX export with flattened nested objects."""

    employee_code = serializers.CharField(source="employee.code", read_only=True, label="Employee Code")
    employee_name = serializers.CharField(source="employee.fullname", read_only=True, label="Employee Name")
    block_name = serializers.SerializerMethodField(label="Block")
    branch_name = serializers.SerializerMethodField(label="Branch")
    department_name = serializers.SerializerMethodField(label="Department")
    position_name = serializers.SerializerMethodField(label="Position")
    status_display = serializers.CharField(source="get_status_display", read_only=True, label="Status")

    def get_block_name(self, obj):
        """Get block name, handling None."""
        return obj.employee.block.name if obj.employee.block else None

    def get_branch_name(self, obj):
        """Get branch name, handling None."""
        return obj.employee.branch.name if obj.employee.branch else None

    def get_department_name(self, obj):
        """Get department name, handling None."""
        return obj.employee.department.name if obj.employee.department else None

    def get_position_name(self, obj):
        """Get position name, handling None."""
        return obj.employee.position.name if obj.employee.position else None

    class Meta:
        model = SalesRevenue
        fields = [
            "code",
            "employee_code",
            "employee_name",
            "block_name",
            "branch_name",
            "department_name",
            "position_name",
            "kpi_target",
            "revenue",
            "transaction_count",
            "month",
            "status_display",
            "created_at",
            "updated_at",
        ]

    def to_representation(self, instance):
        """Convert date month back to MM/YYYY format for output."""
        data = super().to_representation(instance)

        if instance.month:
            data["month"] = f"{instance.month.month:02d}/{instance.month.year}"

        return data
