"""
Mixins for file handling in Django REST Framework serializers.

This module provides mixins that enable automatic file confirmation and
multi-token support for file upload operations.
"""

import json
import logging
from typing import Union

from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.db import transaction
from django.utils.translation import gettext as _
from rest_framework import serializers

logger = logging.getLogger(__name__)


class _FileTokenField(serializers.Field):
    """
    Custom field that accepts either a single string token or a list of string tokens.

    This field provides flexibility for file upload APIs by accepting both:
    - Single token: "token_abc"
    - Multiple tokens: ["token_1", "token_2"]

    The field normalizes the input to always return a list of tokens internally,
    making it easier for the mixin to process multiple files uniformly.
    """

    default_error_messages = {
        "invalid_type": _("Expected a string or list of strings."),
        "invalid_item": _("All items must be strings."),
    }

    def to_internal_value(self, data) -> list:
        """
        Validate and normalize input to a list of strings.

        Args:
            data: Either a string token or a list of string tokens

        Returns:
            list: List of string tokens (single token wrapped in list)
        """
        if isinstance(data, str):
            return [data]
        if isinstance(data, list):
            # Validate all items are strings
            for item in data:
                if not isinstance(item, str):
                    self.fail("invalid_item")
            return data
        return self.fail("invalid_type")

    def to_representation(self, value) -> Union[str, list]:
        """
        Return the value as-is for representation.

        Args:
            value: List of tokens or single token

        Returns:
            The original value
        """
        return value


class FileConfirmSerializerMixin:
    """
    Mixin for DRF serializers that enables automatic file confirmation.

    This mixin allows serializers to automatically confirm uploaded files
    when saving the model instance. Files are linked to the saved instance
    via Django's generic relations (content_type and object_id).

    The mixin automatically adds a 'files' field to the serializer. For better
    OpenAPI/Swagger documentation, it can show concrete file field names instead
    of a generic dictionary by using auto-detection or explicit configuration.

    Auto-Detection Features:
        The mixin intelligently detects file-related fields from your model:
        - CharField fields with file-related names (attachment, document, file, upload, photo, image, avatar)
        - ForeignKey/OneToOneField pointing to apps.files.models.FileModel
        - ForeignKey/OneToOneField to any model with "file" in its class name
        - GenericRelation fields (commonly used for file associations)
        - ManyToManyField pointing to FileModel

        For models with ambiguous field patterns or GenericForeignKey setups,
        explicit configuration via file_confirm_fields is recommended.

    Multiple File Tokens Support:
        The mixin accepts both single token strings and arrays of token strings
        for each field. This allows uploading multiple files for a single field:

        Single token:   files: { "document": "token_abc" }
        Multiple:       files: { "attachments": ["token_1", "token_2"] }
        Mixed:          files: { "document": "token_1", "attachments": ["token_2", "token_3"] }

        For multi-valued relation fields (ManyToManyField, GenericRelation), the OpenAPI
        schema shows an array of strings. For single-valued fields (ForeignKey, OneToOne),
        the schema shows a single string.

        Default behavior for multi-valued fields is to ADD (append) newly confirmed files
        to existing related files, rather than replace them.

    Usage:
        # Basic usage with auto-detection
        class JobDescriptionSerializer(FileConfirmSerializerMixin, serializers.ModelSerializer):
            class Meta:
                model = JobDescription  # Has ForeignKey to FileModel
                fields = '__all__'
            # Auto-detects 'attachment' field from model

        # With explicit file fields (overrides auto-detection)
        class JobDescriptionSerializer(FileConfirmSerializerMixin, serializers.ModelSerializer):
            file_confirm_fields = ['attachment', 'document']

            class Meta:
                model = JobDescription
                fields = '__all__'

        # With explicit multi-valued fields specification
        class DecisionSerializer(FileConfirmSerializerMixin, serializers.ModelSerializer):
            file_confirm_fields = ['attachment']
            file_multi_valued_fields = ['attachments']  # GenericRelation - will show as array

            class Meta:
                model = Decision
                fields = '__all__'

    Workflow:
        1. User uploads files via presigned URLs and receives file_tokens
        2. User submits form with files dict mapping field names to tokens (single or array)
        3. On serializer save, the mixin confirms the files automatically
        4. Files are linked to the saved model instance and assigned to specified fields

    Attributes:
        file_tokens_field (str): Name of the field containing file token mappings.
                                Default is 'files'. Can be overridden
                                in the serializer class.
        file_confirm_fields (list, optional): Explicit list of field names that represent
                                             files. If provided, creates a structured
                                             schema showing specific field names instead
                                             of a generic dict. If not provided, attempts
                                             auto-detection from model fields (CharField,
                                             ForeignKey, OneToOneField, GenericRelation).
        file_multi_valued_fields (list, optional): Explicit list of field names that accept
                                                   multiple file tokens. These fields will
                                                   have array schema in OpenAPI. If not provided,
                                                   auto-detected from ManyToManyField and
                                                   GenericRelation fields.

    Example Request:
        POST /api/hrm/job-descriptions/
        {
            "title": "Senior Developer",
            "responsibility": "...",
            "files": {
                "attachment": "abc123",
                "document": "xyz789"
            }
        }

        POST /api/hrm/decisions/
        {
            "name": "Decision 1",
            "files": {
                "attachments": ["token_1", "token_2", "token_3"]
            }
        }

    OpenAPI Schema:
        With file_confirm_fields or auto-detection:
        {
            "files": {
                "attachment": "string (file token)",
                "attachments": ["string"] (array of file tokens for multi-valued)
            }
        }

        Without file_confirm_fields (fallback):
        {
            "files": {
                "additionalProperties": "string or array of strings"
            }
        }

    Notes:
        - File tokens must be valid and not expired (1 hour TTL in cache)
        - Files must exist in S3 temporary storage
        - All files are confirmed in a single database transaction
        - If confirmation fails, the entire save operation is rolled back
        - The 'files' field is automatically added by the mixin
        - Each file is assigned to the corresponding field on the model instance
        - For multi-valued fields, new files are ADDED to existing (append behavior)
        - Auto-detection now supports ForeignKey, OneToOneField, ManyToManyField, and GenericRelation
        - Import failures for apps.files.models.FileModel are handled gracefully with fallback detection
    """

    file_tokens_field = "files"

    def __init_subclass__(cls, **kwargs):
        """
        Set up class-level declared files field for drf-spectacular schema generation.

        This method is called when a subclass is created, allowing us to add the
        files field at class definition time rather than instance initialization time.
        This ensures drf-spectacular and other schema generators can detect the field.
        """
        super().__init_subclass__(**kwargs)

        # Only process if file_confirm_fields is explicitly declared
        file_confirm_fields = getattr(cls, "file_confirm_fields", None)
        if not file_confirm_fields:
            return

        # Get multi-valued fields (explicit or empty)
        file_multi_valued_fields = set(getattr(cls, "file_multi_valued_fields", []))

        # Get the field name for file tokens (default: "files")
        field_name = getattr(cls, "file_tokens_field", "files")

        # Create field definitions with appropriate types
        field_definitions = {}
        for fname in file_confirm_fields:
            if fname in file_multi_valued_fields:
                # Multi-valued field: accepts array of strings
                field_definitions[fname] = serializers.ListField(
                    child=serializers.CharField(),
                    required=False,
                    write_only=True,
                    allow_empty=True,
                    help_text=_("File tokens for {field} (array of tokens)").format(field=fname),
                )
            else:
                # Single-valued field: accepts string or array (validated at runtime)
                # Using custom field that accepts both for flexibility
                field_definitions[fname] = _FileTokenField(
                    required=False,
                    write_only=True,
                    help_text=_("File token(s) for {field}").format(field=fname),
                )

        # Create a nested serializer class with explicit fields
        # Truncate class name if too long to avoid overly verbose names
        base_name = cls.__name__[:50] if len(cls.__name__) > 50 else cls.__name__
        file_fields_serializer_class = type(
            f"{base_name}FileFieldsSerializer",
            (serializers.Serializer,),
            field_definitions,
        )

        # Store the serializer class on the class for later instantiation
        cls._file_fields_serializer_class = file_fields_serializer_class

    def get_fields(self):
        """
        Override get_fields to add the files field when file_confirm_fields is set.

        This ensures the files field is available at schema generation time.
        """
        fields = super().get_fields()

        # Check if we have a pre-configured files serializer class
        if hasattr(self.__class__, "_file_fields_serializer_class"):
            # Use the pre-configured serializer class
            fields[self.file_tokens_field] = self.__class__._file_fields_serializer_class(
                required=False,
                write_only=True,
                help_text=_("File tokens for uploading files. Each key corresponds to a file field on the model."),
            )
        elif self.file_tokens_field not in fields:
            # Fallback to runtime detection/creation
            file_fields_info = self._get_file_confirm_fields_with_info()

            if file_fields_info:
                # Create field definitions with appropriate types based on detection
                field_definitions = {}
                for field_name, is_multi in file_fields_info:
                    if is_multi:
                        field_definitions[field_name] = serializers.ListField(
                            child=serializers.CharField(),
                            required=False,
                            allow_empty=True,
                            help_text=_("File tokens for {field} (array of tokens)").format(field=field_name),
                        )
                    else:
                        field_definitions[field_name] = _FileTokenField(
                            required=False,
                            help_text=_("File token(s) for {field}").format(field=field_name),
                        )

                file_fields_serializer_class = type(
                    "FileFieldsSerializer",
                    (serializers.Serializer,),
                    field_definitions,
                )

                fields[self.file_tokens_field] = file_fields_serializer_class(
                    required=False,
                    write_only=True,
                    help_text=_("File tokens for uploading files. Each key corresponds to a file field on the model."),
                )
            else:
                # Fallback to generic dict field for backward compatibility
                fields[self.file_tokens_field] = serializers.DictField(
                    child=_FileTokenField(),
                    required=False,
                    write_only=True,
                    help_text=_("Dictionary mapping field names to file tokens (string or array of strings)"),
                )

        return fields

    def _get_file_confirm_fields_with_info(self):  # noqa: C901
        """
        Auto-detect file-related field names and their multi-valued status.

        This method intelligently identifies fields that are likely to be used for file uploads
        by examining the model's field definitions, and also determines if each field
        accepts multiple files.

        Detection Rules (in order of precedence):
            1. **CharField** with file-related names - single-valued
            2. **ForeignKey/OneToOneField** pointing to FileModel - single-valued
            3. **ManyToManyField** pointing to FileModel - multi-valued
            4. **GenericRelation** fields - multi-valued
            5. Any field name matching file patterns - single-valued (fallback)

        Returns:
            list[tuple[str, bool]]: List of (field_name, is_multi_valued) tuples

        Notes:
            - GenericRelation and ManyToManyField are detected as multi-valued
            - ForeignKey and OneToOneField are single-valued
            - Explicit file_multi_valued_fields attribute overrides detection
        """
        # 1. Check for explicit override
        if hasattr(self, "file_confirm_fields") and self.file_confirm_fields:
            multi_valued = set(getattr(self, "file_multi_valued_fields", []))
            return [(fname, fname in multi_valued) for fname in self.file_confirm_fields]

        # 2. Ensure model exists
        if not (hasattr(self, "Meta") and hasattr(self.Meta, "model")):
            return []

        model = self.Meta.model
        file_fields_info = []  # List of (field_name, is_multi_valued)

        # Common file field name patterns
        file_patterns = ["attachment", "document", "file", "upload", "photo", "image", "avatar"]

        # Import field types
        from django.contrib.contenttypes.fields import GenericRelation
        from django.db.models import CharField, ForeignKey, ManyToManyField, OneToOneField

        # Try to import FileModel; if it fails, fall back to name-based detection
        try:
            from apps.files.models import FileModel
        except Exception:
            FileModel = None

        # Track added fields to avoid duplicates
        added_fields = set()

        # Iterate through model fields
        for field in model._meta.get_fields():
            field_name = getattr(field, "name", None)
            if not field_name or field_name in added_fields:
                continue

            # Rule 1: CharField with file-related pattern (single-valued)
            if isinstance(field, CharField):
                if any(pattern in field_name.lower() for pattern in file_patterns):
                    file_fields_info.append((field_name, False))
                    added_fields.add(field_name)
                continue

            # Rule 2: ForeignKey or OneToOneField (single-valued)
            if isinstance(field, (ForeignKey, OneToOneField)):
                remote = getattr(getattr(field, "remote_field", None), "model", None)
                if remote:
                    # Direct match to FileModel if available
                    if FileModel is not None and remote == FileModel:
                        file_fields_info.append((field_name, False))
                        added_fields.add(field_name)
                        continue
                    # Fallback: related class name contains 'file'
                    if "file" in getattr(remote, "__name__", "").lower():
                        file_fields_info.append((field_name, False))
                        added_fields.add(field_name)
                        continue

            # Rule 3: ManyToManyField (multi-valued)
            if isinstance(field, ManyToManyField):
                remote = getattr(getattr(field, "remote_field", None), "model", None)
                if remote:
                    # Direct match to FileModel if available
                    if FileModel is not None and remote == FileModel:
                        file_fields_info.append((field_name, True))
                        added_fields.add(field_name)
                        continue
                    # Fallback: related class name contains 'file'
                    if "file" in getattr(remote, "__name__", "").lower():
                        file_fields_info.append((field_name, True))
                        added_fields.add(field_name)
                        continue

            # Rule 4: GenericRelation (multi-valued)
            if isinstance(field, GenericRelation):
                file_fields_info.append((field_name, True))
                added_fields.add(field_name)
                continue

            # Rule 5: Optional last-resort name match (single-valued by default)
            if any(pattern in field_name.lower() for pattern in file_patterns):
                if field_name not in added_fields:
                    file_fields_info.append((field_name, False))
                    added_fields.add(field_name)

        return file_fields_info

    def _get_file_confirm_fields(self):
        """
        Auto-detect file-related field names for schema generation.

        This is a convenience method that returns just the field names
        without the multi-valued information.

        Returns:
            list: Deduplicated list of field names that should appear in the files schema
        """
        return [name for name, _ in self._get_file_confirm_fields_with_info()]

    def _is_multi_valued_field(self, field_name):
        """
        Check if a field is multi-valued (GenericRelation or ManyToManyField).

        Args:
            field_name: Name of the field to check

        Returns:
            bool: True if the field is multi-valued
        """
        # Check explicit override first
        multi_valued = getattr(self, "file_multi_valued_fields", None)
        if multi_valued is not None:
            return field_name in multi_valued

        # Check model field type
        if not (hasattr(self, "Meta") and hasattr(self.Meta, "model")):
            return False

        model = self.Meta.model

        from django.contrib.contenttypes.fields import GenericRelation
        from django.db.models import ManyToManyField

        try:
            field = model._meta.get_field(field_name)
            return isinstance(field, (GenericRelation, ManyToManyField))
        except Exception:
            return False

    def _normalize_file_mappings(self, file_mappings):
        """
        Normalize file mappings: convert single tokens to lists for uniform processing.

        Args:
            file_mappings: Dictionary mapping field names to tokens (string or list)

        Returns:
            dict: Dictionary mapping field names to lists of tokens
        """
        normalized = {}
        for field_name, tokens in file_mappings.items():
            if isinstance(tokens, str):
                normalized[field_name] = [tokens]
            elif isinstance(tokens, list):
                normalized[field_name] = tokens
            else:
                # Should not happen due to validation, but handle gracefully
                normalized[field_name] = [tokens] if tokens else []
        return normalized

    def _validate_and_collect_file_info(self, normalized_mappings, s3_service):
        """
        Validate file tokens and collect file metadata from cache.

        Args:
            normalized_mappings: Dictionary mapping field names to lists of tokens
            s3_service: S3FileUploadService instance

        Returns:
            list: List of file info dictionaries

        Raises:
            ValidationError: If any token is invalid or file doesn't exist
        """
        from apps.files.constants import (
            ALLOWED_FILE_TYPES,
            CACHE_KEY_PREFIX,
            ERROR_CONTENT_TYPE_MISMATCH,
            ERROR_FILE_NOT_FOUND_S3,
            ERROR_INVALID_FILE_TOKEN,
        )

        files_to_confirm = []
        for field_name, token_list in normalized_mappings.items():
            for file_token in token_list:
                if not file_token:
                    continue

                file_info = self._validate_single_token(
                    field_name,
                    file_token,
                    s3_service,
                    CACHE_KEY_PREFIX,
                    ALLOWED_FILE_TYPES,
                    ERROR_INVALID_FILE_TOKEN,
                    ERROR_FILE_NOT_FOUND_S3,
                    ERROR_CONTENT_TYPE_MISMATCH,
                )
                files_to_confirm.append(file_info)

        return files_to_confirm

    def _validate_single_token(
        self,
        field_name,
        file_token,
        s3_service,
        cache_prefix,
        allowed_types_map,
        err_invalid,
        err_not_found,
        err_mismatch,
    ):
        """
        Validate a single file token and return file info.

        Args:
            field_name: Name of the field
            file_token: File token string
            s3_service: S3FileUploadService instance
            cache_prefix: Cache key prefix
            allowed_types_map: Dictionary of allowed file types by purpose
            err_invalid: Error message for invalid token
            err_not_found: Error message for file not found
            err_mismatch: Error message for content type mismatch

        Returns:
            dict: File info dictionary

        Raises:
            ValidationError: If token is invalid or file doesn't exist
        """
        from rest_framework.exceptions import ValidationError

        cache_key = f"{cache_prefix}{file_token}"
        cached_data = cache.get(cache_key)

        if not cached_data:
            raise ValidationError({self.file_tokens_field: [_(err_invalid) + f": {file_token}"]})

        file_metadata = json.loads(cached_data)
        temp_file_path = file_metadata["file_path"]
        purpose = file_metadata["purpose"]

        # Verify file exists in S3
        if not s3_service.check_file_exists(temp_file_path):
            raise ValidationError({self.file_tokens_field: [_(err_not_found) + f": {file_token}"]})

        # Get file metadata to verify actual content type
        temp_file_metadata = s3_service.get_file_metadata(temp_file_path)
        if temp_file_metadata and purpose in allowed_types_map:
            self._verify_content_type(
                temp_file_metadata,
                file_metadata["file_type"],
                purpose,
                allowed_types_map,
                s3_service,
                temp_file_path,
                cache_key,
                file_token,
                err_mismatch,
            )

        return {
            "field_name": field_name,
            "file_token": file_token,
            "cache_key": cache_key,
            "temp_file_path": temp_file_path,
            "file_name": file_metadata["file_name"],
            "purpose": purpose,
            "temp_metadata": temp_file_metadata,
        }

    def _verify_content_type(
        self,
        temp_metadata,
        expected_type,
        purpose,
        allowed_types_map,
        s3_service,
        temp_path,
        cache_key,
        file_token,
        err_mismatch,
    ):
        """
        Verify content type matches what was declared during presign.

        Raises:
            ValidationError: If content type doesn't match
        """
        from rest_framework.exceptions import ValidationError

        actual_type = temp_metadata.get("content_type")
        allowed_types = allowed_types_map[purpose]

        if actual_type != expected_type or actual_type not in allowed_types:
            # Delete the uploaded file as it doesn't match expected type
            s3_service.delete_file(temp_path)
            cache.delete(cache_key)
            raise ValidationError({self.file_tokens_field: [_(err_mismatch) + f": {file_token}"]})

    def _confirm_related_files(self, instance):
        """
        Confirm files associated with the instance and assign to model fields.

        This method handles both single token strings and lists of token strings
        for each field. For multi-valued fields (GenericRelation, ManyToManyField),
        new files are ADDED to existing files rather than replacing them.

        Args:
            instance: The saved model instance to link files to

        Raises:
            ValidationError: If any file token is invalid or file doesn't exist
        """
        from apps.files.models import FileModel
        from apps.files.utils import S3FileUploadService

        # Get file token mappings from validated data
        file_mappings = self.validated_data.get(self.file_tokens_field, {})
        if not file_mappings:
            return

        # Get content type for the instance
        content_type = ContentType.objects.get_for_model(instance.__class__)

        # Initialize S3 service
        s3_service = S3FileUploadService()

        # Normalize and validate file mappings
        normalized_mappings = self._normalize_file_mappings(file_mappings)
        files_to_confirm = self._validate_and_collect_file_info(normalized_mappings, s3_service)

        # Get request user if available
        request = self.context.get("request")
        uploaded_by = request.user if request and request.user.is_authenticated else None

        # Group files by field for multi-valued field handling
        files_by_field: dict[str, list] = {}
        for file_info in files_to_confirm:
            field_name = file_info["field_name"]
            if field_name not in files_by_field:
                files_by_field[field_name] = []
            files_by_field[field_name].append(file_info)

        # Process all files
        for field_name, field_files in files_by_field.items():
            file_records = self._process_field_files(
                field_files, instance, content_type, uploaded_by, s3_service, FileModel
            )
            # Assign file(s) to the model field
            self._assign_files_to_field(instance, field_name, file_records)

        logger.info(f"Confirmed {len(files_to_confirm)} files for {instance.__class__.__name__} {instance.pk}")

    def _process_field_files(self, field_files, instance, content_type, uploaded_by, s3_service, FileModel):
        """
        Process files for a single field and create FileModel records.

        Args:
            field_files: List of file info dictionaries for a field
            instance: Model instance
            content_type: ContentType for the instance
            uploaded_by: User who uploaded the files
            s3_service: S3FileUploadService instance
            FileModel: FileModel class

        Returns:
            list: List of created FileModel records
        """
        file_records = []

        for file_info in field_files:
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
            file_record = FileModel.objects.create(
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
            file_records.append(file_record)

            # Delete cache entry
            cache.delete(file_info["cache_key"])

        return file_records

    def _assign_files_to_field(self, instance, field_name, file_records):
        """
        Assign file record(s) to a model field.

        For multi-valued fields (GenericRelation, ManyToManyField), files are
        ADDED to existing files. For single-valued fields, the last file record
        is assigned (replacing any existing value).

        Args:
            instance: The model instance
            field_name: Name of the field to assign to
            file_records: List of FileModel records to assign
        """
        if not file_records or not hasattr(instance, field_name):
            return

        is_multi = self._is_multi_valued_field(field_name)

        if is_multi:
            # Multi-valued field: ADD new files to existing ones
            # GenericRelation and ManyToManyField both support .add()
            field = getattr(instance, field_name)
            if hasattr(field, "add"):
                # Use add() to append files (not replace)
                field.add(*file_records)
        else:
            # Single-valued field: assign the last file record
            # If multiple tokens were provided for a single-valued field,
            # we use the last one (this is an edge case)
            file_record = file_records[-1] if file_records else None
            if file_record:
                setattr(instance, field_name, file_record)
                # Save only the specific field to avoid triggering other logic
                instance.save(update_fields=[field_name])

    def save(self, **kwargs):
        """
        Save the instance and confirm related files.

        This method wraps the parent save in a transaction to ensure
        that file confirmation is rolled back if the save fails.

        Returns:
            The saved model instance
        """
        # Remove files field from validated_data to avoid passing it to model constructor
        # Store it temporarily for file confirmation
        file_mappings = self.validated_data.pop(self.file_tokens_field, {})

        with transaction.atomic():
            instance = super().save(**kwargs)
            # Restore file_mappings to validated_data for _confirm_related_files
            self.validated_data[self.file_tokens_field] = file_mappings
            self._confirm_related_files(instance)
        return instance
