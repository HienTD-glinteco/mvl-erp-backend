from rest_framework import serializers

from apps.files.api.serializers import FileSerializer
from apps.hrm.models import JobDescription
from libs.serializers import FileConfirmSerializerMixin


class JobDescriptionSerializer(FileConfirmSerializerMixin, serializers.ModelSerializer):
    """Serializer for JobDescription model"""

    attachment = FileSerializer(read_only=True)

    class Meta:
        model = JobDescription
        fields = [
            "id",
            "code",
            "title",
            "responsibility",
            "requirement",
            "preferred_criteria",
            "benefit",
            "proposed_salary",
            "note",
            "attachment",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "code", "attachment", "created_at", "updated_at"]
