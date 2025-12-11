from rest_framework import serializers


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
                raise serializers.ValidationError(
                    {"default_code": "default_code must be one of the possible_codes"}
                )

        return data


class UnitControlSerializer(serializers.Serializer):
    """Serializer for unit control rules."""

    max_pct_A = serializers.FloatField(min_value=0.0, max_value=1.0)
    max_pct_B = serializers.FloatField(min_value=0.0, max_value=1.0)
    max_pct_C = serializers.FloatField(min_value=0.0, max_value=1.0)
    min_pct_D = serializers.FloatField(min_value=0.0, max_value=1.0, allow_null=True, required=False)


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
