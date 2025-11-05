"""Serializers for import API."""

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.files.models import FileModel
from apps.imports.constants import (
    ERROR_FILE_NOT_CONFIRMED,
    ERROR_FILE_NOT_FOUND,
)
from apps.imports.models import ImportJob


class ImportStartSerializer(serializers.Serializer):
    """Serializer for starting an import job."""

    file_id = serializers.IntegerField(
        required=True,
        help_text=_("ID of the confirmed FileModel to import"),
    )
    options = serializers.JSONField(
        required=False,
        default=dict,
        help_text=_("Import options including allow_update, batch_size, handler_path, etc."),
    )
    async_field = serializers.BooleanField(
        required=False,
        default=True,
        source="async",  # Map to 'async' field name
        help_text=_("Whether to process import asynchronously (always true for imports)"),
    )

    def validate_file_id(self, value):
        """Validate that the file exists and is confirmed."""
        try:
            file_obj = FileModel.objects.get(id=value)
        except FileModel.DoesNotExist:
            raise serializers.ValidationError(_(ERROR_FILE_NOT_FOUND))

        if not file_obj.is_confirmed:
            raise serializers.ValidationError(_(ERROR_FILE_NOT_CONFIRMED))

        return value


class ImportJobSerializer(serializers.ModelSerializer):
    """Serializer for ImportJob model."""

    file_id = serializers.IntegerField(source="file.id", read_only=True)
    created_by_id = serializers.IntegerField(source="created_by.id", read_only=True, allow_null=True)
    result_files = serializers.SerializerMethodField()

    class Meta:
        model = ImportJob
        fields = [
            "id",
            "file_id",
            "status",
            "celery_task_id",
            "created_by_id",
            "created_at",
            "started_at",
            "finished_at",
            "total_rows",
            "processed_rows",
            "success_count",
            "failure_count",
            "percentage",
            "result_files",
            "error_message",
        ]
        read_only_fields = fields

    def get_result_files(self, obj):
        """Get result file information."""
        return {
            "success_file": {
                "file_id": obj.result_success_file.id if obj.result_success_file else None,
                "url": obj.result_success_file.download_url if obj.result_success_file else None,
            },
            "failed_file": {
                "file_id": obj.result_failed_file.id if obj.result_failed_file else None,
                "url": obj.result_failed_file.download_url if obj.result_failed_file else None,
            },
        }


class ImportStartResponseSerializer(serializers.Serializer):
    """Serializer for import start response."""

    import_job_id = serializers.UUIDField(
        help_text=_("UUID of the created import job"),
    )
    celery_task_id = serializers.CharField(
        help_text=_("Celery task ID for tracking"),
    )
    status = serializers.CharField(
        help_text=_("Initial status of the import job"),
    )
    created_at = serializers.DateTimeField(
        help_text=_("Timestamp when the job was created"),
    )


class ImportCancelResponseSerializer(serializers.Serializer):
    """Serializer for import cancel response."""

    message = serializers.CharField(
        help_text=_("Cancellation result message"),
    )
    status = serializers.CharField(
        help_text=_("Current status of the import job"),
    )
