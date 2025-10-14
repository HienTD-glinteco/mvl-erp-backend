from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.core.api.serializers import SimpleUserSerializer
from apps.hrm.models import Block, Branch, Department, Employee
from libs import FieldFilteringSerializerMixin


class BranchNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested branch references"""

    class Meta:
        model = Branch
        fields = ["id", "name", "code"]
        read_only_fields = ["id", "name", "code"]


class BlockNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested block references"""

    class Meta:
        model = Block
        fields = ["id", "name", "code"]
        read_only_fields = ["id", "name", "code"]


class DepartmentNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested department references"""

    class Meta:
        model = Department
        fields = ["id", "name", "code"]
        read_only_fields = ["id", "name", "code"]


class EmployeeSerializer(FieldFilteringSerializerMixin, serializers.ModelSerializer):
    """Serializer for Employee model.

    This serializer provides nested object representation for read operations
    and accepts ID fields for write operations.

    Read operations return full nested objects for branch, block, department, and user.
    Write operations (POST/PUT/PATCH) use _id fields to specify relationships.

    The serializer also validates organizational hierarchy to ensure:
    - Block belongs to the selected Branch
    - Department belongs to the selected Block
    - Department belongs to the selected Branch
    """

    # Nested read-only serializers for full object representation
    branch = BranchNestedSerializer(read_only=True)
    block = BlockNestedSerializer(read_only=True)
    department = DepartmentNestedSerializer(read_only=True)
    user = SimpleUserSerializer(read_only=True)

    # Write-only fields for POST/PUT/PATCH operations
    branch_id = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.all(),
        source="branch",
        write_only=True,
        required=False,
    )
    block_id = serializers.PrimaryKeyRelatedField(
        queryset=Block.objects.all(),
        source="block",
        write_only=True,
        required=False,
    )
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        source="department",
        write_only=True,
        required=False,
    )

    default_fields = [
        "id",
        "code",
        "fullname",
        "username",
        "email",
        "phone",
        "branch",
        "branch_id",
        "block",
        "block_id",
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
            "branch_id",
            "block",
            "block_id",
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

    def validate(self, attrs):
        """Validate organizational hierarchy relationships.

        Ensures that the selected block belongs to the branch, and the
        department belongs to both the block and branch.

        Args:
            attrs: Dictionary of validated field values

        Returns:
            Dictionary of validated attributes

        Raises:
            ValidationError: If organizational hierarchy constraints are violated
        """
        # Validate relationship between branch, block, and department
        branch = attrs.get("branch") or (self.instance.branch if self.instance else None)
        block = attrs.get("block") or (self.instance.block if self.instance else None)
        department = attrs.get("department") or (self.instance.department if self.instance else None)

        if block and branch:
            if block.branch_id != branch.id:
                raise serializers.ValidationError({"block_id": _("Block must belong to the selected branch.")})

        if department and block:
            if department.block_id != block.id:
                raise serializers.ValidationError(
                    {"department_id": _("Department must belong to the selected block.")}
                )

        if department and branch:
            if department.branch_id != branch.id:
                raise serializers.ValidationError(
                    {"department_id": _("Department must belong to the selected branch.")}
                )

        return attrs
