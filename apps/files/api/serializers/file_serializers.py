"""Serializers for file upload API."""

from django.apps import apps
from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.files.models import FileModel


class PresignRequestSerializer(serializers.Serializer):
    """Serializer for presign URL request."""

    file_name = serializers.CharField(
        max_length=255,
        help_text=_("Name of the file being uploaded"),
    )
    file_size = serializers.IntegerField(
        min_value=1,
        help_text=_("Size of the file in bytes"),
    )
    purpose = serializers.CharField(
        max_length=100,
        help_text=_("Upload category (e.g., job_description, invoice, employee_cv)"),
    )


class PresignResponseSerializer(serializers.Serializer):
    """Serializer for presign URL response."""

    upload_url = serializers.CharField(
        help_text=_("Presigned PUT URL for direct upload to S3"),
    )
    file_path = serializers.CharField(
        help_text=_("Temporary S3 path (uploads/tmp/...)"),
    )
    file_token = serializers.CharField(
        help_text=_("Token for later confirmation"),
    )


class ConfirmFileSerializer(serializers.Serializer):
    """Serializer for file upload confirmation."""

    file_token = serializers.CharField(
        help_text=_("Token returned by presign endpoint"),
    )
    related_model = serializers.CharField(
        help_text=_("Django model label (e.g., 'hrm.JobDescription')"),
    )
    related_object_id = serializers.IntegerField(
        min_value=1,
        help_text=_("Related object ID"),
    )
    purpose = serializers.CharField(
        max_length=100,
        help_text=_("File purpose (used to determine final folder)"),
    )

    def validate_related_model(self, value):
        """Validate that the model exists."""
        try:
            apps.get_model(value)
        except (LookupError, ValueError):
            raise serializers.ValidationError(_("Invalid model label: {model}").format(model=value))
        return value

    def validate(self, attrs):
        """Validate that the related object exists."""
        related_model = attrs["related_model"]
        related_object_id = attrs["related_object_id"]

        try:
            model_class = apps.get_model(related_model)
            if not model_class.objects.filter(pk=related_object_id).exists():
                raise serializers.ValidationError(
                    {"related_object_id": _("Object with ID {id} not found").format(id=related_object_id)}
                )
        except (LookupError, ValueError):
            raise serializers.ValidationError({"related_model": _("Invalid model")})

        return attrs


class FileSerializer(serializers.ModelSerializer):
    """Serializer for FileModel."""

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
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
