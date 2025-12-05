from rest_framework import serializers

from apps.payroll.models import SalaryConfig

from .config_schemas import SalaryConfigSchemaSerializer


class SalaryConfigSerializer(serializers.ModelSerializer):
    """Serializer for SalaryConfig model.

    This serializer includes validation of the config JSON field
    using the SalaryConfigSchemaSerializer.
    """

    config = SalaryConfigSchemaSerializer()

    class Meta:
        model = SalaryConfig
        fields = ["id", "version", "config", "updated_at", "created_at"]
        read_only_fields = ["id", "version", "updated_at", "created_at"]

    def validate_config(self, value):
        """Validate config structure using nested serializers."""
        serializer = SalaryConfigSchemaSerializer(data=value)
        serializer.is_valid(raise_exception=True)
        return value
