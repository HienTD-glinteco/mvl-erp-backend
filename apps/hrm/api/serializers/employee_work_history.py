from rest_framework import serializers

from apps.hrm.models import EmployeeWorkHistory

from .common_nested import (
    BlockNestedSerializer,
    BranchNestedSerializer,
    DepartmentNestedSerializer,
    EmployeeNestedSerializer,
    PositionNestedSerializer,
)


class EmployeeWorkHistorySerializer(serializers.ModelSerializer):
    """Serializer for EmployeeWorkHistory model (read-only)."""

    # Nested representations for read operations
    employee = EmployeeNestedSerializer(read_only=True)
    branch = BranchNestedSerializer(read_only=True)
    block = BlockNestedSerializer(read_only=True)
    department = DepartmentNestedSerializer(read_only=True)
    position = PositionNestedSerializer(read_only=True)

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
            "block",
            "department",
            "position",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "date",
            "name",
            "name_display",
            "detail",
            "employee",
            "branch",
            "block",
            "department",
            "position",
            "created_at",
            "updated_at",
        ]
