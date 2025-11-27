from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.files.api.serializers import FileSerializer
from apps.hrm.models import ContractType
from libs.drf.serializers import FieldFilteringSerializerMixin, FileConfirmSerializerMixin


class ContractTypeSerializer(FileConfirmSerializerMixin, serializers.ModelSerializer):
    """Serializer for ContractType model.

    This serializer provides full CRUD operations for contract types.
    It includes nested serialization for template file using FileConfirmSerializerMixin.

    Read operations return full nested objects for template_file.
    Write operations (POST/PUT/PATCH) use file tokens via the 'files' field.
    """

    file_confirm_fields = ["template_file"]

    # Nested read-only serializers for full object representation
    template_file = FileSerializer(read_only=True)

    # Computed field for duration display
    duration_display = serializers.CharField(read_only=True)

    class Meta:
        model = ContractType
        fields = [
            "id",
            "code",
            "name",
            "symbol",
            "duration_type",
            "duration_months",
            "duration_display",
            "base_salary",
            "lunch_allowance",
            "phone_allowance",
            "other_allowance",
            "net_percentage",
            "tax_calculation_method",
            "working_time_type",
            "annual_leave_days",
            "has_social_insurance",
            "working_conditions",
            "rights_and_obligations",
            "terms",
            "note",
            "template_file",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "code",
            "duration_display",
            "template_file",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        """Validate contract type data.

        Ensures that:
        - duration_months is required when duration_type is 'fixed'
        - duration_months is set to None when duration_type is 'indefinite'
        """
        # Get duration_type from attrs or fallback to instance value
        instance_duration_type = getattr(self.instance, "duration_type", None) if self.instance else None
        duration_type = attrs.get("duration_type", instance_duration_type)
        duration_months = attrs.get("duration_months")

        if duration_type == ContractType.DurationType.FIXED:
            if duration_months is None:
                raise serializers.ValidationError(
                    {"duration_months": _("Duration in months is required for fixed-term contracts.")}
                )
        elif duration_type == ContractType.DurationType.INDEFINITE:
            # Clear duration_months for indefinite contracts
            attrs["duration_months"] = None

        return attrs


class ContractTypeListSerializer(serializers.ModelSerializer):
    """Serializer for ContractType list view with minimal fields."""

    duration_display = serializers.CharField(read_only=True)

    class Meta:
        model = ContractType
        fields = [
            "id",
            "code",
            "name",
            "duration_display",
            "base_salary",
            "created_at",
        ]
        read_only_fields = fields


class ContractTypeExportSerializer(FieldFilteringSerializerMixin, serializers.ModelSerializer):
    """Serializer for ContractType XLSX export."""

    duration_display = serializers.CharField(read_only=True)
    net_percentage_display = serializers.CharField(source="get_net_percentage_display", read_only=True)
    tax_method_display = serializers.CharField(source="get_tax_calculation_method_display", read_only=True)
    working_time_display = serializers.CharField(source="get_working_time_type_display", read_only=True)
    social_insurance_display = serializers.SerializerMethodField()

    class Meta:
        model = ContractType
        fields = [
            "code",
            "name",
            "symbol",
            "duration_display",
            "base_salary",
            "lunch_allowance",
            "phone_allowance",
            "other_allowance",
            "net_percentage_display",
            "tax_method_display",
            "working_time_display",
            "annual_leave_days",
            "social_insurance_display",
            "working_conditions",
            "rights_and_obligations",
            "terms",
            "note",
            "created_at",
        ]

    def get_social_insurance_display(self, obj):
        """Return human-readable social insurance status."""
        return _("Yes") if obj.has_social_insurance else _("No")
