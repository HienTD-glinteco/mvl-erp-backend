from rest_framework import serializers

from apps.hrm.models import RecruitmentSource


class RecruitmentSourceSerializer(serializers.ModelSerializer):
    """Serializer for RecruitmentSource model"""

    class Meta:
        model = RecruitmentSource
        fields = [
            "id",
            "name",
            "code",
            "description",
            "allow_referral",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "code", "created_at", "updated_at"]
