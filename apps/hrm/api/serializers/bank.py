from rest_framework import serializers

from apps.hrm.models import Bank


class BankSerializer(serializers.ModelSerializer):
    """Serializer for Bank model (read-only)"""

    class Meta:
        model = Bank
        fields = [
            "id",
            "name",
            "code",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "name",
            "code",
            "created_at",
            "updated_at",
        ]
