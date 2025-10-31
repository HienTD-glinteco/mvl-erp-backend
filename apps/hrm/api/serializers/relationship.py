from rest_framework import serializers

from apps.files.api.serializers import FileSerializer
from apps.hrm.models import Relationship
from libs.drf.serializers import FileConfirmSerializerMixin


class RelationshipSerializer(FileConfirmSerializerMixin, serializers.ModelSerializer):
    """Serializer for Relationship model with file upload support"""

    file_confirm_fields = ["attachment"]
    attachment = FileSerializer(read_only=True)

    class Meta:
        model = Relationship
        fields = [
            "id",
            "employee",
            "employee_code",
            "employee_name",
            "relative_name",
            "relation_type",
            "date_of_birth",
            "national_id",
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
