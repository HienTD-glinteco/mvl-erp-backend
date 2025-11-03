from rest_framework import serializers

from apps.files.api.serializers import FileSerializer
from apps.hrm.models import EmployeeCertificate
from libs import ColoredValueSerializer
from libs.drf.serializers import FileConfirmSerializerMixin


class EmployeeCertificateSerializer(FileConfirmSerializerMixin, serializers.ModelSerializer):
    """Serializer for EmployeeCertificate model."""

    file_confirm_fields = ["file"]
    file = FileSerializer(read_only=True)

    certificate_type_display = serializers.CharField(
        source="get_certificate_type_display",
        read_only=True,
        help_text="Human-readable certificate type label",
    )
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
        help_text="Human-readable status label",
    )
    colored_status = ColoredValueSerializer(read_only=True)

    class Meta:
        model = EmployeeCertificate
        fields = [
            "id",
            "employee",
            "certificate_type",
            "certificate_type_display",
            "certificate_code",
            "certificate_name",
            "issue_date",
            "expiry_date",
            "issuing_organization",
            "file",
            "notes",
            "status",
            "status_display",
            "colored_status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "certificate_type_display",
            "file",
            "status",
            "status_display",
            "colored_status",
            "created_at",
            "updated_at",
        ]

    def validate_certificate_type(self, value):
        """Validate that certificate_type is a valid choice."""
        from apps.hrm.constants import CertificateType

        if value not in dict(CertificateType.choices):
            raise serializers.ValidationError("Invalid certificate type")
        return value
