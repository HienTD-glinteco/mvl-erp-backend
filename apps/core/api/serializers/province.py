from rest_framework import serializers

from apps.core.models import Province


class ProvinceSerializer(serializers.ModelSerializer):
    """Serializer for Province model"""

    level_display = serializers.CharField(source="get_level_display", read_only=True)

    class Meta:
        model = Province
        fields = [
            "id",
            "code",
            "name",
            "english_name",
            "level",
            "level_display",
            "decree",
            "enabled",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "level_display"]
