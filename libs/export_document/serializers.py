"""
Serializers for document export functionality.
"""

from rest_framework import serializers


class ExportDocumentS3ResponseSerializer(serializers.Serializer):
    """Serializer for S3 link delivery response"""

    url = serializers.URLField(help_text="Presigned S3 URL for downloading the document")
    filename = serializers.CharField(help_text="Name of the exported file")
    expires_in = serializers.IntegerField(help_text="URL expiration time in seconds")
    storage_backend = serializers.CharField(help_text="Storage backend used (e.g., 's3')")
    size_bytes = serializers.IntegerField(required=False, help_text="File size in bytes")
