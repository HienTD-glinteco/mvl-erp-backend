from rest_framework import serializers

from apps.hrm.models import RecruitmentChannel


class RecruitmentChannelSerializer(serializers.ModelSerializer):
    """Serializer for RecruitmentChannel model"""

    belong_to_display = serializers.CharField(source="get_belong_to_display", read_only=True)

    class Meta:
        model = RecruitmentChannel
        fields = [
            "id",
            "name",
            "code",
            "belong_to",
            "belong_to_display",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
