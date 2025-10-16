from rest_framework import serializers

from apps.hrm.models import JobDescription


class JobDescriptionSerializer(serializers.ModelSerializer):
    """Serializer for JobDescription model"""

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
        read_only_fields = ["id", "code", "created_at", "updated_at"]
