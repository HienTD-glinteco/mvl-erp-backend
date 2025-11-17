from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.hrm.models import AttendanceExemption, Employee


class EmployeeDetailNestedSerializer(serializers.ModelSerializer):
    """Nested serializer for Employee with organizational details."""

    position = serializers.SerializerMethodField()
    branch = serializers.SerializerMethodField()
    block = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()

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

    def get_position(self, obj):
        """Get position details."""
        if obj.position:
            return {
                "id": obj.position.id,
                "code": obj.position.code,
                "name": obj.position.name,
            }
        return None

    def get_branch(self, obj):
        """Get branch details."""
        if obj.branch:
            return {
                "id": obj.branch.id,
                "code": obj.branch.code,
                "name": obj.branch.name,
            }
        return None

    def get_block(self, obj):
        """Get block details."""
        if obj.block:
            return {
                "id": obj.block.id,
                "code": obj.block.code,
                "name": obj.block.name,
            }
        return None

    def get_department(self, obj):
        """Get department details."""
        if obj.department:
            return {
                "id": obj.department.id,
                "code": obj.department.code,
                "name": obj.department.name,
            }
        return None


class AttendanceExemptionSerializer(serializers.ModelSerializer):
    """Serializer for AttendanceExemption model."""

    employee = EmployeeDetailNestedSerializer(read_only=True)
    employee_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(),
        source="employee",
        write_only=True,
        help_text=_("Employee ID to be exempt from attendance tracking"),
    )
    created_by = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceExemption
        fields = [
            "id",
            "employee",
            "employee_id",
            "effective_date",
            "notes",
            "created_at",
            "updated_at",
            "created_by",
        ]
        read_only_fields = ["id", "employee", "created_at", "updated_at", "created_by"]

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
            if AttendanceExemption.objects.filter(employee=employee).exists():
                raise serializers.ValidationError(
                    {"employee_id": _("Employee already has an active exemption.")}
                )

        return attrs
