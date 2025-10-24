"""
Response serializers for XLSX export API documentation.

These serializers are used ONLY for drf-spectacular to generate accurate
API documentation. They are not used for actual serialization/validation.
"""

from rest_framework import serializers


class ExportS3DeliveryResponseSerializer(serializers.Serializer):
    """Response for S3 delivery mode export."""

    url = serializers.URLField(help_text="Presigned S3 URL for downloading the file")
    filename = serializers.CharField(help_text="Name of the exported file")
    expires_in = serializers.IntegerField(help_text="Time in seconds until the presigned URL expires")
    storage_backend = serializers.CharField(help_text="Storage backend used (always 's3' for this response)")
    size_bytes = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="Size of the exported file in bytes (if available)",
    )


class ExportAsyncResponseSerializer(serializers.Serializer):
    """Response for async export request."""

    task_id = serializers.CharField(help_text="Celery task ID for tracking export progress")
    status = serializers.CharField(help_text="Task status (PENDING, SUCCESS, FAILURE)")
    message = serializers.CharField(help_text="Human-readable message with instructions")


class ExportStatusResponseSerializer(serializers.Serializer):
    """Response for export status check."""

    task_id = serializers.CharField(help_text="Celery task ID")
    status = serializers.CharField(help_text="Task status (PENDING, PROGRESS, SUCCESS, FAILURE)")
    file_url = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Download URL for the generated file (available when status is SUCCESS)",
    )
    file_path = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="File path in storage (available when status is SUCCESS)",
    )
    error = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Error message (available when status is FAILURE)",
    )
    percent = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="Export progress percentage (0-100, available when status is PROGRESS or SUCCESS)",
    )
    processed_rows = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="Number of rows processed (available when status is PROGRESS or SUCCESS)",
    )
    total_rows = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="Total number of rows to process (available when status is PROGRESS or SUCCESS)",
    )
    speed_rows_per_sec = serializers.FloatField(
        required=False,
        allow_null=True,
        help_text="Processing speed in rows per second (available when status is PROGRESS)",
    )
    eta_seconds = serializers.FloatField(
        required=False,
        allow_null=True,
        help_text="Estimated time to completion in seconds (available when status is PROGRESS)",
    )
    updated_at = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Last progress update timestamp (ISO format)",
    )
