from rest_framework import serializers

from apps.files.api.serializers import FileSerializer
from apps.files.api.serializers.mixins import FileConfirmSerializerMixin
from apps.hrm.models import Employee, EmployeeRelationship
from libs.drf.serializers.mixins import FieldFilteringSerializerMixin

from .common_nested import EmployeeNestedSerializer


class EmployeeRelationshipSerializer(FileConfirmSerializerMixin, serializers.ModelSerializer):
    """Serializer for EmployeeRelationship model with file upload support"""

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

    code = serializers.CharField(read_only=True)
    occupation = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    tax_code = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = EmployeeRelationship
        fields = [
            "id",
            "code",
            "employee",
            "employee_id",
            "employee_code",
            "employee_name",
            "relative_name",
            "relation_type",
            "date_of_birth",
            "citizen_id",
            "occupation",
            "tax_code",
            "address",
            "phone",
            "attachment",
            "note",
            "is_active",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "code",
            "employee",
            "employee_code",
            "employee_name",
            "attachment",
            "is_active",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        """Create relationship with current user as creator"""
        request = self.context.get("request")
        if request and request.user:
            validated_data["created_by"] = request.user
        return super().create(validated_data)


class EmployeeRelationshipExportXLSXSerializer(FieldFilteringSerializerMixin, serializers.ModelSerializer):
    """Serializer for exporting EmployeeRelationship to XLSX format."""

    relation_type = serializers.SerializerMethodField()

    default_fields = [
        "employee_code",
        "employee_name",
        "relative_name",
        "relation_type",
        "date_of_birth",
        "citizen_id",
        "address",
        "phone",
        "occupation",
        "note",
    ]

    class Meta:
        model = EmployeeRelationship
        fields = [
            "employee_code",
            "employee_name",
            "relative_name",
            "relation_type",
            "date_of_birth",
            "citizen_id",
            "address",
            "phone",
            "occupation",
            "note",
        ]

    def get_relation_type(self, obj: EmployeeRelationship) -> str:
        """Get the display value of relation type."""
        return obj.get_relation_type_display()
