"""
Mixins for Django REST Framework serializers.

These mixins provide additional functionality for serializers, such as
dynamic field filtering based on request parameters and automatic file confirmation.
"""

import json
import logging

from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.db import transaction
from django.utils.translation import gettext as _

from libs.constants.serializers import (
    LOG_FIELD_FILTERING_APPLIED,
    LOG_NO_FIELDS_PARAM,
    LOG_NO_REQUEST_CONTEXT,
    LOG_USING_DEFAULT_FIELDS,
    WARNING_INVALID_FIELD,
)

logger = logging.getLogger(__name__)


class FieldFilteringSerializerMixin:
    """
    Mixin for DRF serializers that enables dynamic field filtering.

    This mixin allows the frontend to specify which fields to include in the
    serializer response via query parameters. This reduces payload size and
    increases flexibility by only returning required fields.

    The mixin extracts the 'fields' parameter from the request query parameters
    and filters the serializer fields accordingly.

    Usage:
        class MySerializer(FieldFilteringSerializerMixin, serializers.ModelSerializer):
            # Optional: define default fields when no filtering is requested
            default_fields = ['id', 'name', 'email']

            class Meta:
                model = MyModel
                fields = '__all__'

    Query Parameters:
        fields (str): Comma-separated list of field names to include.
                     Example: ?fields=id,name,email

    Attributes:
        default_fields (list, optional): List of field names to use when
                                        'fields' parameter is not provided.
                                        If not set, all fields are returned.

    Example API Request:
        GET /api/users/?fields=id,name,email
        # Response will only include id, name, and email fields

        GET /api/users/
        # Response will include all fields (or default_fields if defined)
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize serializer with optional field filtering.

        Extracts 'fields' parameter from request context and filters
        serializer fields accordingly.
        """
        super().__init__(*args, **kwargs)

        # Get request from context
        context = kwargs.get("context", {})
        request = context.get("request")

        if not request:
            logger.debug(LOG_NO_REQUEST_CONTEXT)
            return

        # Get fields parameter from query params
        fields_param = request.query_params.get("fields")

        if not fields_param:
            # Check if serializer has default_fields attribute
            if hasattr(self, "default_fields") and self.default_fields:
                logger.debug(LOG_USING_DEFAULT_FIELDS)
                self._filter_fields(self.default_fields)
            else:
                logger.debug(LOG_NO_FIELDS_PARAM)
            return

        # Parse comma-separated fields
        requested_fields = [field.strip() for field in fields_param.split(",") if field.strip()]

        if requested_fields:
            self._filter_fields(requested_fields)
            logger.debug(LOG_FIELD_FILTERING_APPLIED, requested_fields, list(self.fields.keys()))

    def _filter_fields(self, allowed_fields):
        """
        Filter serializer fields to only include specified fields.

        Args:
            allowed_fields (list): List of field names to keep
        """
        if not allowed_fields:
            return

        # Get current field names
        existing_fields = set(self.fields.keys())
        allowed_fields_set = set(allowed_fields)

        # Log warning for invalid fields
        invalid_fields = allowed_fields_set - existing_fields
        for invalid_field in invalid_fields:
            logger.warning(WARNING_INVALID_FIELD, invalid_field)

        # Remove fields that are not in allowed_fields
        fields_to_remove = existing_fields - allowed_fields_set
        for field_name in fields_to_remove:
            self.fields.pop(field_name)


class FileConfirmSerializerMixin:
    """
    Mixin for DRF serializers that enables automatic file confirmation.

    This mixin allows serializers to automatically confirm uploaded files
    when saving the model instance. Files are linked to the saved instance
    via Django's generic relations (content_type and object_id).

    The mixin extracts file tokens from validated data and confirms all
    associated files in a single transaction when the serializer is saved.

    Usage:
        class JobDescriptionSerializer(FileConfirmSerializerMixin, serializers.ModelSerializer):
            file_tokens = serializers.ListField(
                child=serializers.CharField(),
                required=False,
                write_only=True
            )

            class Meta:
                model = JobDescription
                fields = '__all__'

    Workflow:
        1. User uploads files via presigned URLs and receives file_tokens
        2. User submits form with file_tokens in the request
        3. On serializer save, the mixin confirms the files automatically
        4. Files are linked to the saved model instance

    Attributes:
        file_tokens_field (str): Name of the field containing file tokens.
                                Default is 'file_tokens'. Can be overridden
                                in the serializer class.

    Example Request:
        POST /api/hrm/job-descriptions/
        {
            "title": "Senior Developer",
            "responsibility": "...",
            "file_tokens": ["abc123", "xyz789"]
        }

    Notes:
        - File tokens must be valid and not expired (1 hour TTL in cache)
        - Files must exist in S3 temporary storage
        - All files are confirmed in a single database transaction
        - If confirmation fails, the entire save operation is rolled back
    """

    file_tokens_field = "file_tokens"

    def _confirm_related_files(self, instance):
        """
        Confirm files associated with the instance.

        Args:
            instance: The saved model instance to link files to

        Raises:
            ValidationError: If any file token is invalid or file doesn't exist
        """
        from rest_framework.exceptions import ValidationError

        from apps.files.constants import (
            ALLOWED_FILE_TYPES,
            CACHE_KEY_PREFIX,
            ERROR_CONTENT_TYPE_MISMATCH,
            ERROR_FILE_NOT_FOUND_S3,
            ERROR_INVALID_FILE_TOKEN,
        )
        from apps.files.models import FileModel
        from apps.files.utils import S3FileUploadService

        # Get file tokens from validated data
        tokens = self.validated_data.get(self.file_tokens_field, [])
        if not tokens:
            return

        # Get content type for the instance
        content_type = ContentType.objects.get_for_model(instance.__class__)

        # Initialize S3 service
        s3_service = S3FileUploadService()

        # Collect file metadata for all tokens
        files_to_confirm = []
        for file_token in tokens:
            cache_key = f"{CACHE_KEY_PREFIX}{file_token}"
            cached_data = cache.get(cache_key)

            if not cached_data:
                raise ValidationError({self.file_tokens_field: [_(ERROR_INVALID_FILE_TOKEN) + f": {file_token}"]})

            file_metadata = json.loads(cached_data)
            temp_file_path = file_metadata["file_path"]
            file_name = file_metadata["file_name"]
            file_type = file_metadata["file_type"]
            purpose = file_metadata["purpose"]

            # Verify file exists in S3
            if not s3_service.check_file_exists(temp_file_path):
                raise ValidationError({self.file_tokens_field: [_(ERROR_FILE_NOT_FOUND_S3) + f": {file_token}"]})

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
                        raise ValidationError(
                            {
                                self.file_tokens_field: [
                                    _(ERROR_CONTENT_TYPE_MISMATCH) + f": {file_token}",
                                ]
                            }
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

        # Get request user if available
        request = self.context.get("request")
        uploaded_by = request.user if request and request.user.is_authenticated else None

        # Process all files
        for file_info in files_to_confirm:
            # Generate permanent path
            permanent_path = s3_service.generate_permanent_path(
                purpose=file_info["purpose"],
                object_id=instance.pk,
                file_name=file_info["file_name"],
            )

            # Move file from temp to permanent location
            s3_service.move_file(file_info["temp_file_path"], permanent_path)

            # Get file metadata from S3
            s3_metadata = s3_service.get_file_metadata(permanent_path)

            # Create FileModel record
            FileModel.objects.create(
                purpose=file_info["purpose"],
                file_name=file_info["file_name"],
                file_path=permanent_path,
                size=s3_metadata.get("size") if s3_metadata else None,
                checksum=s3_metadata.get("etag") if s3_metadata else None,
                is_confirmed=True,
                content_type=content_type,
                object_id=instance.pk,
                uploaded_by=uploaded_by,
            )

            # Delete cache entry
            cache.delete(file_info["cache_key"])

        logger.info(f"Confirmed {len(files_to_confirm)} files for {instance.__class__.__name__} {instance.pk}")

    def save(self, **kwargs):
        """
        Save the instance and confirm related files.

        This method wraps the parent save in a transaction to ensure
        that file confirmation is rolled back if the save fails.

        Returns:
            The saved model instance
        """
        with transaction.atomic():
            instance = super().save(**kwargs)
            self._confirm_related_files(instance)
        return instance
