from rest_framework import serializers

from apps.payroll.models import KPIConfig


class GradeThresholdSerializer(serializers.Serializer):
    """Serializer for a single grade threshold entry."""

    min = serializers.FloatField()
    max = serializers.FloatField()
    possible_codes = serializers.ListField(child=serializers.CharField(), min_length=1)
    label = serializers.CharField(required=False, allow_blank=True)
    default_code = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        """Validate threshold data."""
        # Validate min < max
        if data["min"] >= data["max"]:
            raise serializers.ValidationError({"min": "min must be less than max"})

        # Validate default_code is in possible_codes if provided
        if "default_code" in data and data["default_code"]:
            if data["default_code"] not in data["possible_codes"]:
                raise serializers.ValidationError({"default_code": "default_code must be one of the possible_codes"})

        return data


class UnitControlPercentageSerializr(serializers.Serializer):
    """Serializer for unit control percentage rules."""

    min = serializers.FloatField(min_value=0.0, max_value=1.0, allow_null=True, required=False)
    max = serializers.FloatField(min_value=0.0, max_value=1.0, allow_null=True, required=False)
    target = serializers.FloatField(min_value=0.0, max_value=1.0, allow_null=True, required=False)


class UnitControlSerializer(serializers.Serializer):
    """Serializer for unit control rules."""

    A = UnitControlPercentageSerializr()
    B = UnitControlPercentageSerializr()
    C = UnitControlPercentageSerializr()
    D = UnitControlPercentageSerializr()


class KPIConfigSchemaSerializer(serializers.Serializer):
    """Complete KPI configuration schema serializer.

    This serializer validates the entire config JSON structure.
    """

    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    ambiguous_assignment = serializers.ChoiceField(
        choices=["manual", "auto_prefer_default", "auto_prefer_highest", "auto_prefer_first"]
    )
    grade_thresholds = GradeThresholdSerializer(many=True)
    unit_control = serializers.DictField(child=UnitControlSerializer())
    meta = serializers.DictField(required=False)


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
