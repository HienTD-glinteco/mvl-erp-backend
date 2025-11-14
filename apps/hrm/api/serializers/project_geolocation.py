from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.core.api.serializers.user import SimpleUserSerializer
from apps.hrm.api.serializers.common_nested import SimpleNestedSerializerFactory
from apps.hrm.models import Project, ProjectGeolocation

ProjectNestedSerializer = SimpleNestedSerializerFactory(
    Project,
    ["id", "code", "name"],
)


class ProjectGeolocationSerializer(serializers.ModelSerializer):
    """Serializer for ProjectGeolocation model"""

    # Nested serializers for read operations
    project = ProjectNestedSerializer(read_only=True)
    created_by = SimpleUserSerializer(read_only=True)
    updated_by = SimpleUserSerializer(read_only=True)

    # Write-only fields for create/update operations
    project_id = serializers.IntegerField(write_only=True, required=True)

    class Meta:
        model = ProjectGeolocation
        fields = [
            "id",
            "code",
            "name",
            "project",
            "project_id",
            "address",
            "latitude",
            "longitude",
            "radius_m",
            "status",
            "notes",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "code",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]

    def validate_radius_m(self, value):
        """Validate that radius is at least 1 meter"""
        if value < 1:
            raise serializers.ValidationError("Radius must be at least 1 meter")
        return value

    def validate(self, attrs):
        """Ensure code cannot be changed on update"""
        if self.instance and "code" in attrs:
            # Remove code from attrs if it's being updated
            attrs.pop("code", None)
        return attrs

    def create(self, validated_data):
        """Create a new ProjectGeolocation with audit fields"""
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            validated_data["created_by"] = request.user
            validated_data["updated_by"] = request.user

        try:
            return super().create(validated_data)
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.message_dict)

    def update(self, instance, validated_data):
        """Update ProjectGeolocation with audit fields"""
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            validated_data["updated_by"] = request.user

        try:
            return super().update(instance, validated_data)
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.message_dict)
