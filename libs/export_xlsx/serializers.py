"""
Response serializers for XLSX export API documentation.

These serializers are used ONLY for drf-spectacular to generate accurate
API documentation. They are not used for actual serialization/validation.
"""

from rest_framework import serializers


class ExportAsyncResponseSerializer(serializers.Serializer):
    """Response for async export request."""

    task_id = serializers.CharField(help_text="Celery task ID for tracking export progress")
    status = serializers.CharField(help_text="Task status (PENDING, SUCCESS, FAILURE)")
    message = serializers.CharField(help_text="Human-readable message with instructions")


class ExportStatusResponseSerializer(serializers.Serializer):
    """Response for export status check."""

    task_id = serializers.CharField(help_text="Celery task ID")
    status = serializers.CharField(help_text="Task status (PENDING, SUCCESS, FAILURE)")
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
