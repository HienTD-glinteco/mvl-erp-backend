"""
Serializers for XLSX import responses.
"""

from rest_framework import serializers


class ImportAsyncResponseSerializer(serializers.Serializer):
    """Serializer for async import response"""

    task_id = serializers.CharField(help_text="Celery task ID for tracking import progress")
    status = serializers.CharField(help_text="Task status (PENDING, PROCESSING, SUCCESS, FAILED)")
    message = serializers.CharField(help_text="Human-readable status message")


class ImportResultSerializer(serializers.Serializer):
    """Serializer for import result"""

    success_count = serializers.IntegerField(help_text="Number of successfully imported rows")
    error_count = serializers.IntegerField(help_text="Number of rows with errors")
    errors = serializers.ListField(
        child=serializers.DictField(),
        help_text="List of error details with row numbers and error messages",
    )
    detail = serializers.CharField(help_text="Overall result message")
    error_file_url = serializers.CharField(
        required=False,
        help_text="URL to download error report XLSX file (if errors exist)",
    )


class ImportPreviewResponseSerializer(serializers.Serializer):
    """Serializer for import preview response"""

    valid_count = serializers.IntegerField(help_text="Number of valid rows")
    invalid_count = serializers.IntegerField(help_text="Number of invalid rows")
    errors = serializers.ListField(
        child=serializers.DictField(),
        help_text="List of validation errors",
    )
    preview_data = serializers.ListField(
        child=serializers.DictField(),
        help_text="Preview of first few rows that would be imported",
        required=False,
    )
    detail = serializers.CharField(help_text="Preview result message")
