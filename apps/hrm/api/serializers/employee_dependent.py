from rest_framework import serializers

from apps.files.api.serializers import FileSerializer
from apps.hrm.models import Employee, EmployeeDependent
from libs.drf.serializers import FileConfirmSerializerMixin

from .common_nested import EmployeeNestedSerializer


class EmployeeDependentSerializer(FileConfirmSerializerMixin, serializers.ModelSerializer):
    """Serializer for EmployeeDependent model with file upload support."""

    file_confirm_fields = ["attachment"]
    attachment = FileSerializer(read_only=True)

    # Nested employee representation for read operations
    employee = EmployeeNestedSerializer(read_only=True)
    # Write-only field for POST/PUT/PATCH operations
    employee_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(),
        source="employee",
        write_only=True,
    )

    # Include display fields for better API responses
    relationship_display = serializers.CharField(
        source="get_relationship_display",
        read_only=True,
        help_text="Human-readable relationship label",
    )

    class Meta:
        model = EmployeeDependent
        fields = [
            "id",
            "employee",
            "employee_id",
            "dependent_name",
            "relationship",
            "relationship_display",
            "date_of_birth",
            "citizen_id",
            "attachment",
            "note",
            "is_active",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "employee",
            "relationship_display",
            "attachment",
            "is_active",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        """Create dependent with current user as creator."""
        request = self.context.get("request")
        if request and request.user:
            validated_data["created_by"] = request.user
        return super().create(validated_data)
