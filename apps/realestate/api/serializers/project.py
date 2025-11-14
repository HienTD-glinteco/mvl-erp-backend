from rest_framework import serializers

from apps.realestate.models import Project


class ProjectSerializer(serializers.ModelSerializer):
    """Serializer for Project model"""

    class Meta:
        model = Project
        fields = [
            "id",
            "code",
            "name",
            "address",
            "description",
            "status",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "code",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        """Ensure code cannot be changed on update"""
        if self.instance and "code" in attrs:
            attrs.pop("code", None)
        return attrs
