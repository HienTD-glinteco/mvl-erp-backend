"""Serializers for import API."""

from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.files.models import FileModel
from apps.imports.constants import (
    ALLOWED_OUTPUT_FORMATS,
    DEFAULT_BATCH_SIZE,
    DEFAULT_COUNT_TOTAL_FIRST,
    DEFAULT_CREATE_RESULT_FILE_RECORDS,
    DEFAULT_HEADER_ROWS,
    DEFAULT_OUTPUT_FORMAT,
    ERROR_FILE_NOT_CONFIRMED,
    ERROR_FILE_NOT_FOUND,
    MAX_BATCH_SIZE,
    MAX_HEADER_ROWS,
    MIN_BATCH_SIZE,
    MIN_HEADER_ROWS,
)
from apps.imports.models import ImportJob


class ImportOptionsSerializer(serializers.Serializer):
    """Serializer for import options with strict type validation."""

    batch_size = serializers.IntegerField(
        required=False,
        default=DEFAULT_BATCH_SIZE,
        min_value=MIN_BATCH_SIZE,
        max_value=MAX_BATCH_SIZE,
        help_text=_(
            "Number of rows to process per batch (default: {DEFAULT_BATCH_SIZE}, range: {MIN_BATCH_SIZE}-{MAX_BATCH_SIZE})"
        ).format(
            DEFAULT_BATCH_SIZE=DEFAULT_BATCH_SIZE,
            MIN_BATCH_SIZE=MIN_BATCH_SIZE,
            MAX_BATCH_SIZE=MAX_BATCH_SIZE,
        ),
    )
    count_total_first = serializers.BooleanField(
        required=False,
        default=DEFAULT_COUNT_TOTAL_FIRST,
        help_text="Whether to count total rows before processing (default: true)",
    )
    header_rows = serializers.IntegerField(
        required=False,
        default=DEFAULT_HEADER_ROWS,
        min_value=MIN_HEADER_ROWS,
        max_value=MAX_HEADER_ROWS,
        help_text=_(
            "Number of header rows to skip (default: {DEFAULT_HEADER_ROWS}, range: {MIN_HEADER_ROWS}-{MAX_HEADER_ROWS})"
        ).format(
            DEFAULT_HEADER_ROWS=DEFAULT_HEADER_ROWS,
            MIN_HEADER_ROWS=MIN_HEADER_ROWS,
            MAX_HEADER_ROWS=MAX_HEADER_ROWS,
        ),
    )
    output_format = serializers.CharField(
        required=False,
        default=DEFAULT_OUTPUT_FORMAT,
        help_text="Format for result files (default: csv, choices: csv, xlsx)",
    )
    create_result_file_records = serializers.BooleanField(
        required=False,
        default=DEFAULT_CREATE_RESULT_FILE_RECORDS,
        help_text="Create FileModel records for result files (default: true)",
    )
    handler_path = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=False,
        default=None,
        help_text="Override handler path (optional)",
    )
    handler_options = serializers.JSONField(
        required=False,
        default=dict,
        help_text="Custom options for handler (default: {})",
    )
    result_file_prefix = serializers.CharField(
        required=False,
        allow_blank=False,
        help_text="Custom prefix for result files (optional)",
    )
    allow_update = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Allow updating existing records during import (default: false)",
    )

    def validate_batch_size(self, value):
        """Validate batch_size with strict type checking."""
        # Check if the original input was actually an integer
        if hasattr(self, "initial_data") and self.initial_data and "batch_size" in self.initial_data:
            original_value = self.initial_data["batch_size"]
            if not isinstance(original_value, int) or isinstance(original_value, bool):
                raise serializers.ValidationError(_("batch_size must be an integer"))
        return value

    def validate_count_total_first(self, value):
        """Validate count_total_first with strict type checking."""
        if hasattr(self, "initial_data") and self.initial_data and "count_total_first" in self.initial_data:
            original_value = self.initial_data["count_total_first"]
            if not isinstance(original_value, bool):
                raise serializers.ValidationError(_("count_total_first must be a boolean"))
        return value

    def validate_header_rows(self, value):
        """Validate header_rows with strict type checking."""
        if hasattr(self, "initial_data") and self.initial_data and "header_rows" in self.initial_data:
            original_value = self.initial_data["header_rows"]
            if not isinstance(original_value, int) or isinstance(original_value, bool):
                raise serializers.ValidationError(_("header_rows must be an integer"))
        return value

    def validate_create_result_file_records(self, value):
        """Validate create_result_file_records with strict type checking."""
        if hasattr(self, "initial_data") and self.initial_data and "create_result_file_records" in self.initial_data:
            original_value = self.initial_data["create_result_file_records"]
            if not isinstance(original_value, bool):
                raise serializers.ValidationError(_("create_result_file_records must be a boolean"))
        return value

    def validate_handler_path(self, value):
        """Validate handler_path with strict type checking."""
        if hasattr(self, "initial_data") and self.initial_data and "handler_path" in self.initial_data:
            original_value = self.initial_data["handler_path"]
            if original_value is not None and not isinstance(original_value, str):
                raise serializers.ValidationError(_("handler_path must be a string or null"))
        return value

    def validate_handler_options(self, value):
        """Validate handler_options with strict type checking."""
        if hasattr(self, "initial_data") and self.initial_data and "handler_options" in self.initial_data:
            original_value = self.initial_data["handler_options"]
            if not isinstance(original_value, dict):
                raise serializers.ValidationError(_("handler_options must be a dictionary"))
        return value

    def validate_result_file_prefix(self, value):
        """Validate result_file_prefix with strict type checking."""
        if hasattr(self, "initial_data") and self.initial_data and "result_file_prefix" in self.initial_data:
            original_value = self.initial_data["result_file_prefix"]
            if not isinstance(original_value, str):
                raise serializers.ValidationError(_("result_file_prefix must be a string"))
        return value

    def validate_allow_update(self, value):
        """Validate allow_update with strict type checking."""
        if hasattr(self, "initial_data") and self.initial_data and "allow_update" in self.initial_data:
            original_value = self.initial_data["allow_update"]
            if not isinstance(original_value, bool):
                raise serializers.ValidationError(_("allow_update must be a boolean"))
        return value

    def validate_output_format(self, value):
        """Validate and normalize output_format to lowercase."""
        if value:
            # Normalize to lowercase
            normalized = value.lower()
            # Check if it's in the allowed formats
            if normalized not in ALLOWED_OUTPUT_FORMATS:
                formats_str = ", ".join(ALLOWED_OUTPUT_FORMATS)
                raise serializers.ValidationError(
                    _("output_format must be one of: %(formats)s") % {"formats": formats_str}
                )
            return normalized
        return value

    def validate(self, attrs):
        """Validate the entire options dict and reject unknown keys."""
        # Get all known field names
        known_fields = set(self.fields.keys())
        # Get all provided keys from initial_data
        provided_keys = set(self.initial_data.keys()) if hasattr(self, "initial_data") and self.initial_data else set()
        # Find unknown keys
        unknown_keys = provided_keys - known_fields

        if unknown_keys:
            # Raise validation error for unknown keys
            raise serializers.ValidationError({key: _("Unknown field") for key in unknown_keys})

        return attrs


class ResultFileInfoSerializer(serializers.Serializer):
    """Serializer for individual result file information."""

    file_id = serializers.IntegerField(
        allow_null=True,
        help_text="ID of the result file, null if not generated",
    )
    url = serializers.URLField(
        allow_null=True,
        help_text="Presigned download URL for the file, null if not available",
    )


class ResultFilesSerializer(serializers.Serializer):
    """Serializer for result files structure."""

    success_file = ResultFileInfoSerializer(
        help_text="Information about the success records file",
    )
    failed_file = ResultFileInfoSerializer(
        help_text="Information about the failed records file",
    )


class ImportStartSerializer(serializers.Serializer):
    """Serializer for starting an import job."""

    file_id = serializers.IntegerField(
        required=True,
        help_text="ID of the confirmed FileModel to import",
    )
    options = ImportOptionsSerializer(
        required=False,
        default=dict,
        help_text="Import options for controlling the import process",
    )
    async_field = serializers.BooleanField(
        required=False,
        default=True,
        source="async",  # Map to 'async' field name
        help_text="Whether to process import asynchronously (always true for imports)",
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

    @extend_schema_field(ResultFilesSerializer)
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
        help_text="UUID of the created import job",
    )
    celery_task_id = serializers.CharField(
        help_text="Celery task ID for tracking",
    )
    status = serializers.CharField(
        help_text="Initial status of the import job",
    )
    created_at = serializers.DateTimeField(
        help_text="Timestamp when the job was created",
    )


class ImportCancelResponseSerializer(serializers.Serializer):
    """Serializer for import cancel response."""

    message = serializers.CharField(
        help_text="Cancellation result message",
    )
    status = serializers.CharField(
        help_text="Current status of the import job",
    )


class ImportTemplateResponseSerializer(serializers.Serializer):
    """Serializer for import template response."""

    file_id = serializers.IntegerField(
        help_text="ID of the template file",
    )
    file_name = serializers.CharField(
        help_text="Name of the template file",
    )
    download_url = serializers.URLField(
        help_text="Presigned download URL for the template file",
    )
    size = serializers.IntegerField(
        help_text="File size in bytes",
        allow_null=True,
    )
    created_at = serializers.DateTimeField(
        help_text="Timestamp when the template was created",
    )
