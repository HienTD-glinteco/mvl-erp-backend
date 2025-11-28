from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.files.api.serializers import FileSerializer
from apps.files.models import FileModel
from apps.hrm.models import Decision, Employee
from libs.drf.serializers import ColoredValueSerializer, FieldFilteringSerializerMixin, FileConfirmSerializerMixin


class DecisionSignerNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested signer (Employee) references."""

    class Meta:
        model = Employee
        fields = ["id", "code", "fullname", "email"]
        read_only_fields = ["id", "code", "fullname", "email"]


class DecisionSerializer(FileConfirmSerializerMixin, serializers.ModelSerializer):
    """Serializer for Decision model.

    This serializer provides nested object representation for read operations
    and accepts ID fields for write operations.

    Read operations return full nested objects for signer and attachments.
    Write operations (POST/PUT/PATCH) require signer_id and optional attachment_ids.

    File upload workflow:
        1. User uploads files via presigned URLs
        2. User calls /api/files/confirm/ to confirm files and get file IDs
        3. User submits form with attachment_ids: [1, 2, 3]
        4. On save, the serializer links the files to the Decision
    """

    # Nested read-only serializers for full object representation
    signer = DecisionSignerNestedSerializer(read_only=True)
    attachments = FileSerializer(many=True, read_only=True)

    # Write-only field for POST/PUT/PATCH operations
    signer_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(),
        source="signer",
        write_only=True,
        required=True,
        help_text="ID of the employee who signs the decision",
    )

    # Write-only field for attachment IDs
    attachment_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=True,
        allow_empty=False,
        help_text="List of confirmed file IDs to attach to this decision",
    )

    # Color representation for signing status using ColoredValueSerializer
    colored_signing_status = ColoredValueSerializer(read_only=True)

    class Meta:
        model = Decision
        fields = [
            "id",
            "decision_number",
            "name",
            "signing_date",
            "signer",
            "signer_id",
            "effective_date",
            "reason",
            "content",
            "note",
            "signing_status",
            "colored_signing_status",
            "attachments",
            "attachment_ids",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "signer",
            "colored_signing_status",
            "attachments",
            "created_at",
            "updated_at",
        ]

    def validate_attachment_ids(self, value):
        """Validate that all attachment IDs exist in the database."""
        if not value:
            return value

        # Get existing file IDs
        existing_ids = set(FileModel.objects.filter(id__in=value, is_confirmed=True).values_list("id", flat=True))
        provided_ids = set(value)

        # Check for missing IDs
        missing_ids = provided_ids - existing_ids
        if missing_ids:
            raise serializers.ValidationError(
                _("File IDs not found or not confirmed: {ids}").format(ids=list(missing_ids))
            )

        return value

    def create(self, validated_data):
        """Create Decision and link attachments."""
        attachment_ids = validated_data.pop("attachment_ids", [])
        instance = super().create(validated_data)

        if attachment_ids:
            self._link_attachments(instance, attachment_ids)

        return instance

    def update(self, instance, validated_data):
        """Update Decision and link attachments."""
        attachment_ids = validated_data.pop("attachment_ids", None)
        instance = super().update(instance, validated_data)

        # Only update attachments if attachment_ids was provided in the request
        if attachment_ids is not None:
            self._link_attachments(instance, attachment_ids)

        return instance

    def _link_attachments(self, instance, attachment_ids):
        """Link file attachments to the Decision instance.

        Uses GenericRelation's set() method to efficiently replace all attachments.

        Args:
            instance: The Decision instance to link files to
            attachment_ids: List of FileModel IDs to link
        """
        # Get the FileModel instances to link
        files_to_link = FileModel.objects.filter(id__in=attachment_ids)

        # Use GenericRelation's set() method to replace all attachments
        instance.attachments.set(files_to_link)


class DecisionExportSerializer(FieldFilteringSerializerMixin, serializers.ModelSerializer):
    """Serializer for Decision XLSX export."""

    signer_name = serializers.CharField(source="signer.fullname", read_only=True)
    signer_code = serializers.CharField(source="signer.code", read_only=True)

    class Meta:
        model = Decision
        fields = [
            "decision_number",
            "name",
            "signing_date",
            "signer_code",
            "signer_name",
            "effective_date",
            "reason",
            "content",
            "note",
            "signing_status",
            "created_at",
        ]
