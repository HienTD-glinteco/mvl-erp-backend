from rest_framework import serializers

from apps.hrm.models import RecruitmentChannel
from libs import FieldFilteringSerializerMixin


class RecruitmentChannelSerializer(FieldFilteringSerializerMixin, serializers.ModelSerializer):
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
        read_only_fields = ["id", "code", "created_at", "updated_at"]
