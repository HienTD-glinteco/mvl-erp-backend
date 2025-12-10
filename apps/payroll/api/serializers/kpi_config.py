from rest_framework import serializers

from apps.payroll.models import KPIConfig

from .kpi_config_schemas import KPIConfigSchemaSerializer


class KPIConfigSerializer(serializers.ModelSerializer):
    """Serializer for KPIConfig model.

    This serializer includes validation of the config JSON field
    using the KPIConfigSchemaSerializer.
    """

    config = KPIConfigSchemaSerializer()

    class Meta:
        model = KPIConfig
        fields = ["id", "version", "config", "updated_at", "created_at"]
        read_only_fields = ["id", "version", "updated_at", "created_at"]

    def validate_config(self, value):
        """Validate config structure using nested serializers."""
        serializer = KPIConfigSchemaSerializer(data=value)
        serializer.is_valid(raise_exception=True)
        return value
