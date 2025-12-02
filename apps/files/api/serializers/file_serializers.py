"""Serializers for file upload API."""

from django.apps import apps
from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.files.constants import ALLOWED_FILE_TYPES, ERROR_INVALID_FILE_TYPE
from apps.files.models import FileModel


class PresignRequestSerializer(serializers.Serializer):
    """Serializer for presign URL request."""

    file_name = serializers.CharField(
        max_length=255,
        help_text="Name of the file being uploaded",
    )
    file_type = serializers.CharField(
        max_length=100,
        help_text="MIME type of the file (e.g., application/pdf, image/png)",
    )
    purpose = serializers.CharField(
        max_length=100,
        help_text="Upload category (e.g., job_description, invoice, employee_cv)",
    )

    def validate(self, attrs):
        """Validate file type is allowed for the given purpose."""
        purpose = attrs.get("purpose")
        file_type = attrs.get("file_type")

        # Check if this purpose has file type restrictions
        if purpose in ALLOWED_FILE_TYPES:
            allowed_types = ALLOWED_FILE_TYPES[purpose]
            if file_type not in allowed_types:
                raise serializers.ValidationError(
                    {
                        "file_type": _(ERROR_INVALID_FILE_TYPE).format(
                            purpose=purpose, allowed_types=", ".join(allowed_types)
                        )
                    }
                )

        return attrs


class PresignResponseSerializer(serializers.Serializer):
    """Serializer for presign URL response."""

    upload_url = serializers.CharField(
        help_text="Presigned PUT URL for direct upload to S3",
    )
    file_path = serializers.CharField(
        help_text="Temporary S3 path (uploads/tmp/...)",
    )
    file_token = serializers.CharField(
        help_text="Token for later confirmation",
    )


class FileSerializer(serializers.ModelSerializer):
    """Serializer for FileModel."""

    view_url = serializers.ReadOnlyField(help_text="Presigned URL for viewing the file (valid for 1 hour)")
    download_url = serializers.ReadOnlyField(help_text="Presigned URL for downloading the file (valid for 1 hour)")
    uploaded_by_username = serializers.CharField(
        source="uploaded_by.username",
        read_only=True,
        help_text="Username of the user who uploaded this file",
    )

    class Meta:
        model = FileModel
        fields = [
            "id",
            "purpose",
            "file_name",
            "file_path",
            "size",
            "checksum",
            "is_confirmed",
            "uploaded_by",
            "uploaded_by_username",
            "view_url",
            "download_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class FileConfirmationSerializer(serializers.Serializer):
    """Serializer for individual file confirmation with optional related object."""

    file_token = serializers.CharField(
        help_text="Token returned by presign endpoint",
    )
    purpose = serializers.CharField(
        help_text="File purpose (e.g., 'job_description', 'invoice')",
    )
    related_model = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Optional Django model label (e.g., 'hrm.JobDescription')",
    )
    related_object_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
        help_text="Optional related object ID",
    )
    related_field = serializers.CharField(
        required=False,
        allow_null=True,
        help_text=_(
            "Optional field name on related model to set as ForeignKey to this file. "
            "If provided, related_object.{related_field} = file_model"
        ),
    )

    def validate_related_model(self, value):
        """Validate that the model exists if provided."""
        if value is None:
            return value

        try:
            apps.get_model(value)
        except (LookupError, ValueError):
            raise serializers.ValidationError(_("Invalid model label: {model}").format(model=value))
        return value

    def validate(self, attrs):
        """Validate that both related_model and related_object_id are provided together."""
        related_model = attrs.get("related_model")
        related_object_id = attrs.get("related_object_id")

        # If one is provided, both must be provided
        if (related_model is None) != (related_object_id is None):
            raise serializers.ValidationError(
                _("Both related_model and related_object_id must be provided together, or both omitted")
            )

        # If both are provided, validate that the object exists
        if related_model and related_object_id:
            try:
                model_class = apps.get_model(related_model)
                if not model_class.objects.filter(pk=related_object_id).exists():
                    raise serializers.ValidationError(
                        {"related_object_id": _("Object with ID {id} not found").format(id=related_object_id)}
                    )
            except (LookupError, ValueError):
                raise serializers.ValidationError({"related_model": _("Invalid model")})

        return attrs


class ConfirmMultipleFilesResponseSerializer(serializers.Serializer):
    """Serializer for multi-file confirmation response."""

    confirmed_files = FileSerializer(
        many=True,
        help_text="List of confirmed files with metadata",
    )


class ConfirmMultipleFilesSerializer(serializers.Serializer):
    """Serializer for confirming multiple file uploads with per-file configuration."""

    files = serializers.ListField(
        child=FileConfirmationSerializer(),
        min_length=1,
        help_text="List of file configurations with tokens and related objects",
    )
