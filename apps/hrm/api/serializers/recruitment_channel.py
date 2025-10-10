from rest_framework import serializers

from apps.hrm.models import RecruitmentChannel


class RecruitmentChannelSerializer(serializers.ModelSerializer):
    """Serializer for RecruitmentChannel model"""

    class Meta:
        model = RecruitmentChannel
        fields = [
            "id",
            "name",
            "code",
            "belong_to",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
