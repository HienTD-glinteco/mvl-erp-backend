from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.hrm.models import AttendanceExemption, Employee

from .common_nested import (
    BlockNestedSerializer,
    BranchNestedSerializer,
    DepartmentNestedSerializer,
    PositionNestedSerializer,
)


class EmployeeDetailNestedSerializer(serializers.ModelSerializer):
    """Nested serializer for Employee with organizational details."""

    position = PositionNestedSerializer(read_only=True)
    branch = BranchNestedSerializer(read_only=True)
    block = BlockNestedSerializer(read_only=True)
    department = DepartmentNestedSerializer(read_only=True)

    class Meta:
        model = Employee
        fields = [
            "id",
            "code",
            "fullname",
            "email",
            "position",
            "branch",
            "block",
            "department",
        ]
        read_only_fields = fields


class AttendanceExemptionSerializer(serializers.ModelSerializer):
    """Serializer for AttendanceExemption model."""

    employee = EmployeeDetailNestedSerializer(read_only=True)
    employee_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(),
        source="employee",
        write_only=True,
        help_text="Employee ID to be exempt from attendance tracking",
    )
    created_by = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceExemption
        fields = [
            "id",
            "employee",
            "employee_id",
            "effective_date",
            "end_date",
            "status",
            "notes",
            "created_at",
            "updated_at",
            "created_by",
        ]
        read_only_fields = [
            "id",
            "employee",
            "created_at",
            "updated_at",
            "created_by",
            "end_date",
            "status",
        ]

    def get_created_by(self, obj):
        """Get user who created the exemption."""
        if hasattr(obj, "created_by") and obj.created_by:
            return {
                "id": obj.created_by.id,
                "username": obj.created_by.username,
                "fullname": obj.created_by.get_full_name() or obj.created_by.username,
            }
        return None

    def validate(self, attrs):
        """Validate the exemption data."""
        employee = attrs.get("employee")

        # Validate employee status
        if employee and employee.status not in [Employee.Status.ACTIVE, Employee.Status.ONBOARDING]:
            raise serializers.ValidationError(
                {"employee_id": _("Only active or onboarding employees can be exempt from attendance tracking")}
            )

        # Check for duplicate exemption when creating
        if not self.instance and employee:
            if AttendanceExemption.objects.filter(
                employee=employee, status=AttendanceExemption.Status.ENABLED
            ).exists():
                raise serializers.ValidationError({"employee_id": _("Employee already has an active exemption.")})

        return attrs


class AttendanceExemptionExportSerializer(serializers.ModelSerializer):
    """Serializer for exporting AttendanceExemption data to Excel."""

    employee__code = serializers.CharField(source="employee.code", read_only=True)
    employee__fullname = serializers.CharField(source="employee.fullname", read_only=True)
    employee__position__name = serializers.CharField(source="employee.position.name", read_only=True)

    class Meta:
        model = AttendanceExemption
        fields = [
            "employee__code",
            "employee__fullname",
            "employee__position__name",
            "effective_date",
            "notes",
        ]
