from rest_framework import serializers

from apps.hrm.models import EmployeeWorkHistory

from .common_nested import (
    BlockNestedSerializer,
    BranchNestedSerializer,
    DecisionNestedSerializer,
    DepartmentNestedSerializer,
    EmployeeNestedSerializer,
    PositionNestedSerializer,
)


class EmployeeWorkHistorySerializer(serializers.ModelSerializer):
    """Serializer for EmployeeWorkHistory model."""

    # Nested representations for read operations
    employee = EmployeeNestedSerializer(read_only=True)
    branch = BranchNestedSerializer(read_only=True)
    block = BlockNestedSerializer(read_only=True)
    department = DepartmentNestedSerializer(read_only=True)
    position = PositionNestedSerializer(read_only=True)
    decision = DecisionNestedSerializer(read_only=True)

    # _id fields for update operations (write-only)
    branch_id = serializers.IntegerField(write_only=True)
    block_id = serializers.IntegerField(write_only=True)
    department_id = serializers.IntegerField(write_only=True)
    position_id = serializers.IntegerField(write_only=True)

    # Display field for event type
    name_display = serializers.CharField(
        source="get_name_display",
        read_only=True,
        help_text="Human-readable event type label",
    )

    class Meta:
        model = EmployeeWorkHistory
        fields = [
            "id",
            "date",
            "name",
            "name_display",
            "detail",
            "employee",
            "branch",
            "branch_id",
            "block",
            "block_id",
            "department",
            "department_id",
            "position",
            "position_id",
            "decision",
            "from_date",
            "to_date",
            "retain_seniority",
            "note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "name",
            "name_display",
            "detail",
            "employee",
            "branch",
            "block",
            "department",
            "position",
            "from_date",
            "to_date",
            "retain_seniority",
            "created_at",
            "updated_at",
        ]
