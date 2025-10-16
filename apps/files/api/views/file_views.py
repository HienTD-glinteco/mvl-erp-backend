"""API views for file upload management."""

import json

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.files.api.serializers import ConfirmFileSerializer, FileSerializer, PresignRequestSerializer
from apps.files.constants import (
    API_CONFIRM_DESCRIPTION,
    API_CONFIRM_SUMMARY,
    API_CONFIRM_TAG,
    API_PRESIGN_DESCRIPTION,
    API_PRESIGN_SUMMARY,
    API_PRESIGN_TAG,
    CACHE_KEY_PREFIX,
    CACHE_TIMEOUT,
    ERROR_FILE_NOT_FOUND_S3,
    ERROR_INVALID_FILE_TOKEN,
)
from apps.files.models import FileModel
from apps.files.utils import S3FileUploadService


@extend_schema(
    summary=API_PRESIGN_SUMMARY,
    description=API_PRESIGN_DESCRIPTION,
    tags=[API_PRESIGN_TAG],
    request=PresignRequestSerializer,
    examples=[
        OpenApiExample(
            "Presign request",
            description="Example request to generate presigned URL",
            value={
                "file_name": "JD.pdf",
                "file_type": "application/pdf",
                "purpose": "job_description",
            },
            request_only=True,
        ),
        OpenApiExample(
            "Presign success",
            description="Example successful response with presigned URL",
            value={
                "success": True,
                "data": {
                    "upload_url": "https://s3.amazonaws.com/bucket/uploads/tmp/uuid/JD.pdf?AWSAccessKeyId=...",
                    "file_path": "uploads/tmp/uuid/JD.pdf",
                    "file_token": "f7e3c91a-b32a-4c6d-bbe2-8c9f2a6a9f32",
                },
                "error": None,
            },
            response_only=True,
        ),
        OpenApiExample(
            "Presign error",
            description="Example error response for invalid request",
            value={
                "success": False,
                "data": None,
                "error": {"file_size": ["Ensure this value is greater than or equal to 1."]},
            },
            response_only=True,
            status_codes=["400"],
        ),
    ],
)
class PresignURLView(APIView):
    """
    Generate presigned URL for direct S3 upload.

    This endpoint generates a presigned URL that allows clients to upload files
    directly to S3 without sending binary data through Django. The URL is valid
    for 1 hour and the file token is stored in cache for later confirmation.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Generate presigned URL for file upload."""
        serializer = PresignRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        file_name = serializer.validated_data["file_name"]
        file_type = serializer.validated_data["file_type"]
        purpose = serializer.validated_data["purpose"]

        # Generate presigned URL
        s3_service = S3FileUploadService()
        presign_data = s3_service.generate_presigned_url(
            file_name=file_name,
            file_type=file_type,
            purpose=purpose,
        )

        # Store file metadata in cache for later confirmation
        cache_key = f"{CACHE_KEY_PREFIX}{presign_data['file_token']}"
        cache_data = {
            "file_name": file_name,
            "file_type": file_type,
            "purpose": purpose,
            "file_path": presign_data["file_path"],
        }
        cache.set(cache_key, json.dumps(cache_data), CACHE_TIMEOUT)

        return Response(presign_data, status=status.HTTP_200_OK)


@extend_schema(
    summary=API_CONFIRM_SUMMARY,
    description=API_CONFIRM_DESCRIPTION,
    tags=[API_CONFIRM_TAG],
    request=ConfirmFileSerializer,
    examples=[
        OpenApiExample(
            "Confirm request",
            description="Example request to confirm file upload",
            value={
                "file_token": "f7e3c91a-b32a-4c6d-bbe2-8c9f2a6a9f32",
                "related_model": "hrm.JobDescription",
                "related_object_id": 42,
                "purpose": "job_description",
            },
            request_only=True,
        ),
        OpenApiExample(
            "Confirm success",
            description="Example successful response after confirmation",
            value={
                "success": True,
                "data": {
                    "id": 112,
                    "purpose": "job_description",
                    "file_name": "JD.pdf",
                    "file_path": "uploads/job_description/42/JD.pdf",
                    "size": 123456,
                    "checksum": None,
                    "is_confirmed": True,
                    "created_at": "2025-10-16T04:00:00Z",
                    "updated_at": "2025-10-16T04:00:00Z",
                },
                "error": None,
            },
            response_only=True,
        ),
        OpenApiExample(
            "Confirm error - invalid token",
            description="Example error response for invalid or expired token",
            value={
                "success": False,
                "data": None,
                "error": {"detail": "Invalid or expired file token"},
            },
            response_only=True,
            status_codes=["400"],
        ),
        OpenApiExample(
            "Confirm error - file not found",
            description="Example error response when file not found in S3",
            value={
                "success": False,
                "data": None,
                "error": {"detail": "File not found in S3"},
            },
            response_only=True,
            status_codes=["400"],
        ),
    ],
)
class ConfirmFileUploadView(APIView):
    """
    Confirm file upload and move to permanent storage.

    This endpoint verifies the file exists in S3, moves it from temporary to
    permanent storage, and creates a FileModel record linked to the related object.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Confirm file upload and create FileModel record."""
        serializer = ConfirmFileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        file_token = serializer.validated_data["file_token"]
        related_model = serializer.validated_data["related_model"]
        related_object_id = serializer.validated_data["related_object_id"]
        purpose = serializer.validated_data["purpose"]
        related_field = serializer.validated_data.get("related_field")

        # Retrieve file metadata from cache
        cache_key = f"{CACHE_KEY_PREFIX}{file_token}"
        cached_data = cache.get(cache_key)

        if not cached_data:
            return Response(
                {"detail": _(ERROR_INVALID_FILE_TOKEN)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Parse cached data
        file_metadata = json.loads(cached_data)
        temp_file_path = file_metadata["file_path"]
        file_name = file_metadata["file_name"]

        # Verify file exists in S3
        s3_service = S3FileUploadService()
        if not s3_service.check_file_exists(temp_file_path):
            return Response(
                {"detail": _(ERROR_FILE_NOT_FOUND_S3)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Generate permanent path
        permanent_path = s3_service.generate_permanent_path(
            purpose=purpose,
            object_id=related_object_id,
            file_name=file_name,
        )

        # Move file from temp to permanent location
        s3_service.move_file(temp_file_path, permanent_path)

        # Get file metadata from S3
        s3_metadata = s3_service.get_file_metadata(permanent_path)

        # Get ContentType for the related model
        model_class = apps.get_model(related_model)
        content_type = ContentType.objects.get_for_model(model_class)

        # Create FileModel record
        file_record = FileModel.objects.create(
            purpose=purpose,
            file_name=file_name,
            file_path=permanent_path,
            size=s3_metadata.get("size") if s3_metadata else None,
            checksum=s3_metadata.get("etag") if s3_metadata else None,
            is_confirmed=True,
            content_type=content_type,
            object_id=related_object_id,
        )

        # If related_field is specified, set it as ForeignKey on related object
        if related_field:
            related_object = model_class.objects.get(pk=related_object_id)
            if hasattr(related_object, related_field):
                setattr(related_object, related_field, file_record)
                related_object.save(update_fields=[related_field])

        # Delete cache entry
        cache.delete(cache_key)

        # Return file record
        file_serializer = FileSerializer(file_record)
        return Response(file_serializer.data, status=status.HTTP_201_CREATED)
