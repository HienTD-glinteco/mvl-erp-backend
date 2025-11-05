"""Serializers for import API."""

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.files.models import FileModel
from apps.imports.constants import (
    ALLOWED_OPTION_KEYS,
    ALLOWED_OUTPUT_FORMATS,
    DEFAULT_BATCH_SIZE,
    DEFAULT_COUNT_TOTAL_FIRST,
    DEFAULT_CREATE_RESULT_FILE_RECORDS,
    DEFAULT_HEADER_ROWS,
    DEFAULT_OUTPUT_FORMAT,
    ERROR_FILE_NOT_CONFIRMED,
    ERROR_FILE_NOT_FOUND,
    ERROR_INVALID_OPTION_KEY,
    MAX_BATCH_SIZE,
    MAX_HEADER_ROWS,
    MIN_BATCH_SIZE,
    MIN_HEADER_ROWS,
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
        help_text=_(
            "Import options: batch_size (int, 1-100000, default 500), "
            "count_total_first (bool, default true), header_rows (int, 0-100, default 1), "
            "output_format (csv|xlsx, default csv), create_result_file_records (bool, default true), "
            "handler_path (str|null, optional), handler_options (dict, default {}), "
            "result_file_prefix (str, optional)"
        ),
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

    def validate_options(self, value):
        """Validate the options parameter with strict key and value validation."""
        if not isinstance(value, dict):
            raise serializers.ValidationError(_("Options must be a dictionary"))

        # Check for unknown keys
        unknown_keys = set(value.keys()) - ALLOWED_OPTION_KEYS
        if unknown_keys:
            allowed_keys_str = ", ".join(sorted(ALLOWED_OPTION_KEYS))
            raise serializers.ValidationError(
                _(ERROR_INVALID_OPTION_KEY.format(key=", ".join(unknown_keys), allowed_keys=allowed_keys_str))
            )

        # Validate and set defaults for each option
        validated_options = {}

        # batch_size: integer, 1-100000, default 500
        if "batch_size" in value:
            batch_size = value["batch_size"]
            if not isinstance(batch_size, int):
                raise serializers.ValidationError(_("batch_size must be an integer"))
            if batch_size < MIN_BATCH_SIZE or batch_size > MAX_BATCH_SIZE:
                raise serializers.ValidationError(
                    _(f"batch_size must be between {MIN_BATCH_SIZE} and {MAX_BATCH_SIZE}")
                )
            validated_options["batch_size"] = batch_size
        else:
            validated_options["batch_size"] = DEFAULT_BATCH_SIZE

        # count_total_first: boolean, default true
        if "count_total_first" in value:
            count_total_first = value["count_total_first"]
            if not isinstance(count_total_first, bool):
                raise serializers.ValidationError(_("count_total_first must be a boolean"))
            validated_options["count_total_first"] = count_total_first
        else:
            validated_options["count_total_first"] = DEFAULT_COUNT_TOTAL_FIRST

        # header_rows: integer, 0-100, default 1
        if "header_rows" in value:
            header_rows = value["header_rows"]
            if not isinstance(header_rows, int):
                raise serializers.ValidationError(_("header_rows must be an integer"))
            if header_rows < MIN_HEADER_ROWS or header_rows > MAX_HEADER_ROWS:
                raise serializers.ValidationError(_(f"header_rows must be between {MIN_HEADER_ROWS} and {MAX_HEADER_ROWS}"))
            validated_options["header_rows"] = header_rows
        else:
            validated_options["header_rows"] = DEFAULT_HEADER_ROWS

        # output_format: string, "csv" or "xlsx", default "csv"
        if "output_format" in value:
            output_format = value["output_format"]
            if not isinstance(output_format, str):
                raise serializers.ValidationError(_("output_format must be a string"))
            # Case-insensitive comparison
            output_format_lower = output_format.lower()
            if output_format_lower not in ALLOWED_OUTPUT_FORMATS:
                raise serializers.ValidationError(
                    _(f"output_format must be one of: {', '.join(ALLOWED_OUTPUT_FORMATS)}")
                )
            validated_options["output_format"] = output_format_lower
        else:
            validated_options["output_format"] = DEFAULT_OUTPUT_FORMAT

        # create_result_file_records: boolean, default true
        if "create_result_file_records" in value:
            create_result_file_records = value["create_result_file_records"]
            if not isinstance(create_result_file_records, bool):
                raise serializers.ValidationError(_("create_result_file_records must be a boolean"))
            validated_options["create_result_file_records"] = create_result_file_records
        else:
            validated_options["create_result_file_records"] = DEFAULT_CREATE_RESULT_FILE_RECORDS

        # handler_path: string or null, optional
        if "handler_path" in value:
            handler_path = value["handler_path"]
            if handler_path is not None:
                if not isinstance(handler_path, str):
                    raise serializers.ValidationError(_("handler_path must be a string or null"))
                if not handler_path.strip():
                    raise serializers.ValidationError(_("handler_path cannot be an empty string"))
            validated_options["handler_path"] = handler_path

        # handler_options: dict, default {}
        if "handler_options" in value:
            handler_options = value["handler_options"]
            if not isinstance(handler_options, dict):
                raise serializers.ValidationError(_("handler_options must be a dictionary"))
            validated_options["handler_options"] = handler_options
        else:
            validated_options["handler_options"] = {}

        # result_file_prefix: string, optional
        if "result_file_prefix" in value:
            result_file_prefix = value["result_file_prefix"]
            if not isinstance(result_file_prefix, str):
                raise serializers.ValidationError(_("result_file_prefix must be a string"))
            validated_options["result_file_prefix"] = result_file_prefix

        return validated_options


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


class ImportTemplateResponseSerializer(serializers.Serializer):
    """Serializer for import template response."""

    file_id = serializers.IntegerField(
        help_text=_("ID of the template file"),
    )
    file_name = serializers.CharField(
        help_text=_("Name of the template file"),
    )
    download_url = serializers.URLField(
        help_text=_("Presigned download URL for the template file"),
    )
    size = serializers.IntegerField(
        help_text=_("File size in bytes"),
        allow_null=True,
    )
    created_at = serializers.DateTimeField(
        help_text=_("Timestamp when the template was created"),
    )
