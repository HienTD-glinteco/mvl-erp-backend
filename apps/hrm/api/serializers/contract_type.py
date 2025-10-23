from rest_framework import serializers

from apps.hrm.models import ContractType


class ContractTypeSerializer(serializers.ModelSerializer):
    """Serializer for ContractType model."""

    class Meta:
        model = ContractType
        fields = [
            "id",
            "name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]
