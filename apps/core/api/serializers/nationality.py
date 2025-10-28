from rest_framework import serializers

from apps.core.models import Nationality


class NationalitySerializer(serializers.ModelSerializer):
    """Serializer for Nationality model"""

    class Meta:
        model = Nationality
        fields = [
            "id",
            "name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
