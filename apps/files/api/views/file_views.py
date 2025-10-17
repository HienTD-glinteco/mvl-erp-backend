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

from apps.files.api.serializers import (
    ConfirmMultipleFilesResponseSerializer,
    ConfirmMultipleFilesSerializer,
    FileSerializer,
    PresignRequestSerializer,
)
from apps.files.constants import (
    ALLOWED_FILE_TYPES,
    API_CONFIRM_MULTI_DESCRIPTION,
    API_CONFIRM_MULTI_SUMMARY,
    API_CONFIRM_MULTI_TAG,
    API_PRESIGN_DESCRIPTION,
    API_PRESIGN_SUMMARY,
    API_PRESIGN_TAG,
    CACHE_KEY_PREFIX,
    CACHE_TIMEOUT,
    ERROR_CONTENT_TYPE_MISMATCH,
    ERROR_FILE_ALREADY_CONFIRMED,
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
    summary=API_CONFIRM_MULTI_SUMMARY,
    description=API_CONFIRM_MULTI_DESCRIPTION,
    tags=[API_CONFIRM_MULTI_TAG],
    request=ConfirmMultipleFilesSerializer,
    responses={201: ConfirmMultipleFilesResponseSerializer},
    examples=[
        OpenApiExample(
            "Confirm multiple files request",
            description="Example request to confirm multiple file uploads",
            value={
                "file_tokens": ["f7e3c91a-b32a-4c6d-bbe2-8c9f2a6a9f32", "a2b5d8e1-c43f-4a7d-9be3-7d8e3f5a6b21"],
                "related_object": {"app_label": "hrm", "model": "jobdescription", "object_id": 15},
            },
            request_only=True,
        ),
        OpenApiExample(
            "Confirm multiple files success",
            description="Example successful response after confirmation",
            value={
                "success": True,
                "data": {
                    "confirmed_files": [
                        {
                            "id": 112,
                            "purpose": "job_description",
                            "file_name": "JD.pdf",
                            "file_path": "uploads/job_description/15/JD.pdf",
                            "size": 123456,
                            "checksum": None,
                            "is_confirmed": True,
                            "uploaded_by": 5,
                            "uploaded_by_username": "john_doe",
                            "view_url": "https://s3.amazonaws.com/bucket/uploads/job_description/15/JD.pdf?AWSAccessKeyId=...",
                            "download_url": "https://s3.amazonaws.com/bucket/uploads/job_description/15/JD.pdf?response-content-disposition=attachment...",
                            "created_at": "2025-10-16T04:00:00Z",
                            "updated_at": "2025-10-16T04:00:00Z",
                        },
                        {
                            "id": 113,
                            "purpose": "job_description",
                            "file_name": "Estimate.pdf",
                            "file_path": "uploads/job_description/15/Estimate.pdf",
                            "size": 234567,
                            "checksum": None,
                            "is_confirmed": True,
                            "uploaded_by": 5,
                            "uploaded_by_username": "john_doe",
                            "view_url": "https://s3.amazonaws.com/bucket/uploads/job_description/15/Estimate.pdf?AWSAccessKeyId=...",
                            "download_url": "https://s3.amazonaws.com/bucket/uploads/job_description/15/Estimate.pdf?response-content-disposition=attachment...",
                            "created_at": "2025-10-16T04:00:00Z",
                            "updated_at": "2025-10-16T04:00:00Z",
                        },
                    ]
                },
                "error": None,
            },
            response_only=True,
        ),
        OpenApiExample(
            "Confirm multiple files error - invalid token",
            description="Example error response for invalid or expired token",
            value={
                "success": False,
                "data": None,
                "error": {"detail": "Invalid or expired file token: abc123"},
            },
            response_only=True,
            status_codes=["400"],
        ),
        OpenApiExample(
            "Confirm multiple files error - already confirmed",
            description="Example error response when file is already confirmed",
            value={
                "success": False,
                "data": None,
                "error": {"detail": "File has already been confirmed: abc123"},
            },
            response_only=True,
            status_codes=["409"],
        ),
        OpenApiExample(
            "Confirm multiple files error - related object not found",
            description="Example error response when related object doesn't exist",
            value={
                "success": False,
                "data": None,
                "error": {"object_id": ["Object with ID 99999 not found"]},
            },
            response_only=True,
            status_codes=["400"],
        ),
    ],
)
class ConfirmMultipleFilesView(APIView):
    """
    Confirm multiple file uploads in a single transaction.

    This endpoint verifies all files exist in S3, moves them from temporary to
    permanent storage, and creates FileModel records linked to the related object.
    All operations are performed in a single database transaction.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Confirm multiple file uploads and create FileModel records."""
        serializer = ConfirmMultipleFilesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        file_tokens = serializer.validated_data["file_tokens"]
        related_object = serializer.validated_data["related_object"]

        app_label = related_object["app_label"]
        model_name = related_object["model"]
        object_id = related_object["object_id"]

        # Get model class and content type
        model_class = apps.get_model(app_label, model_name)
        content_type = ContentType.objects.get_for_model(model_class)

        # Initialize S3 service
        s3_service = S3FileUploadService()

        # Collect file metadata for all tokens
        files_to_confirm = []
        for file_token in file_tokens:
            cache_key = f"{CACHE_KEY_PREFIX}{file_token}"
            cached_data = cache.get(cache_key)

            if not cached_data:
                return Response(
                    {"detail": _(ERROR_INVALID_FILE_TOKEN) + f": {file_token}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            file_metadata = json.loads(cached_data)
            temp_file_path = file_metadata["file_path"]
            file_name = file_metadata["file_name"]
            file_type = file_metadata["file_type"]
            purpose = file_metadata["purpose"]

            # Check if file already exists in database (already confirmed)
            if FileModel.objects.filter(file_path=temp_file_path, is_confirmed=True).exists():
                return Response(
                    {"detail": _(ERROR_FILE_ALREADY_CONFIRMED) + f": {file_token}"},
                    status=status.HTTP_409_CONFLICT,
                )

            # Verify file exists in S3
            if not s3_service.check_file_exists(temp_file_path):
                return Response(
                    {"detail": _(ERROR_FILE_NOT_FOUND_S3) + f": {file_token}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get file metadata to verify actual content type
            temp_file_metadata = s3_service.get_file_metadata(temp_file_path)
            if temp_file_metadata:
                actual_content_type = temp_file_metadata.get("content_type")
                expected_content_type = file_type

                # Verify content type matches what was declared during presign
                if purpose in ALLOWED_FILE_TYPES:
                    allowed_types = ALLOWED_FILE_TYPES[purpose]
                    if actual_content_type != expected_content_type or actual_content_type not in allowed_types:
                        # Delete the uploaded file as it doesn't match expected type
                        s3_service.delete_file(temp_file_path)
                        cache.delete(cache_key)
                        return Response(
                            {
                                "detail": _(ERROR_CONTENT_TYPE_MISMATCH) + f": {file_token}",
                                "expected": expected_content_type,
                                "actual": actual_content_type,
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )

            files_to_confirm.append(
                {
                    "file_token": file_token,
                    "cache_key": cache_key,
                    "temp_file_path": temp_file_path,
                    "file_name": file_name,
                    "purpose": purpose,
                    "temp_metadata": temp_file_metadata,
                }
            )

        # Process all files in a transaction
        from django.db import transaction

        confirmed_files = []
        with transaction.atomic():
            for file_info in files_to_confirm:
                # Generate permanent path
                permanent_path = s3_service.generate_permanent_path(
                    purpose=file_info["purpose"],
                    object_id=object_id,
                    file_name=file_info["file_name"],
                )

                # Move file from temp to permanent location
                s3_service.move_file(file_info["temp_file_path"], permanent_path)

                # Get file metadata from S3
                s3_metadata = s3_service.get_file_metadata(permanent_path)

                # Create FileModel record
                file_record = FileModel.objects.create(
                    purpose=file_info["purpose"],
                    file_name=file_info["file_name"],
                    file_path=permanent_path,
                    size=s3_metadata.get("size") if s3_metadata else None,
                    checksum=s3_metadata.get("etag") if s3_metadata else None,
                    is_confirmed=True,
                    content_type=content_type,
                    object_id=object_id,
                    uploaded_by=request.user if request.user.is_authenticated else None,
                )

                confirmed_files.append(file_record)

                # Delete cache entry
                cache.delete(file_info["cache_key"])

        # Return confirmed files
        file_serializer = FileSerializer(confirmed_files, many=True)
        return Response({"confirmed_files": file_serializer.data}, status=status.HTTP_201_CREATED)
