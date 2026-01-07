from django.utils.translation import gettext as _
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


class ProjectExportXLSXSerializer(ProjectSerializer):
    """Serializer for exporting Project to XLSX format."""

    class Meta(ProjectSerializer.Meta):
        fields = [
            "code",
            "name",
            "address",
            "description",
        ]
        extra_kwargs = {
            "code": {"label": _("Project code")},
            "name": {"label": _("Project name")},
            "address": {"label": _("Address")},
            "description": {"label": _("Note")},
        }
