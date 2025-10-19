from rest_framework import serializers

from apps.core.api.serializers import SimpleUserSerializer
from apps.hrm.models import Block, Branch, Department, Employee
from libs import FieldFilteringSerializerMixin


class EmployeeBranchNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested branch references in employee context"""

    class Meta:
        model = Branch
        fields = ["id", "name", "code"]
        read_only_fields = ["id", "name", "code"]
        ref_name = "EmployeeBranchNested"


class EmployeeBlockNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested block references in employee context"""

    class Meta:
        model = Block
        fields = ["id", "name", "code"]
        read_only_fields = ["id", "name", "code"]
        ref_name = "EmployeeBlockNested"


class EmployeeDepartmentNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested department references in employee context"""

    class Meta:
        model = Department
        fields = ["id", "name", "code"]
        read_only_fields = ["id", "name", "code"]
        ref_name = "EmployeeDepartmentNested"


class EmployeeSerializer(FieldFilteringSerializerMixin, serializers.ModelSerializer):
    """Serializer for Employee model.

    This serializer provides nested object representation for read operations
    and accepts ID fields for write operations.

    Read operations return full nested objects for branch, block, department, and user.
    Write operations (POST/PUT/PATCH) only require department_id.
    Branch and block are automatically set based on the department's organizational structure.
    """

    # Nested read-only serializers for full object representation
    branch = EmployeeBranchNestedSerializer(read_only=True)
    block = EmployeeBlockNestedSerializer(read_only=True)
    department = EmployeeDepartmentNestedSerializer(read_only=True)
    user = SimpleUserSerializer(read_only=True)

    # Write-only field for POST/PUT/PATCH operations
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        source="department",
        write_only=True,
        required=True,
    )

    default_fields = [
        "id",
        "code",
        "fullname",
        "username",
        "email",
        "phone",
        "branch",
        "block",
        "department",
        "department_id",
        "user",
        "note",
    ]

    class Meta:
        model = Employee
        fields = [
            "id",
            "code",
            "fullname",
            "username",
            "email",
            "phone",
            "branch",
            "block",
            "department",
            "department_id",
            "user",
            "note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "code",
            "branch",
            "block",
            "department",
            "user",
            "created_at",
            "updated_at",
        ]
