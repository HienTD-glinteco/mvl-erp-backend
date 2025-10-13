from rest_framework import serializers

from apps.core.models import AdministrativeUnit
from libs import FieldFilteringSerializerMixin


class AdministrativeUnitSerializer(FieldFilteringSerializerMixin, serializers.ModelSerializer):
    """Serializer for AdministrativeUnit model"""

    level_display = serializers.CharField(source="get_level_display", read_only=True)
    province_code = serializers.CharField(source="parent_province.code", read_only=True)
    province_name = serializers.CharField(source="parent_province.name", read_only=True)

    class Meta:
        model = AdministrativeUnit
        fields = [
            "id",
            "code",
            "name",
            "english_name",
            "parent_province",
            "province_code",
            "province_name",
            "level",
            "level_display",
            "enabled",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "level_display", "province_code", "province_name"]
