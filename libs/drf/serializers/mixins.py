"""
Mixins for Django REST Framework serializers.

These mixins provide additional functionality for serializers, such as
dynamic field filtering based on request parameters.

Note: FileConfirmSerializerMixin has been moved to apps.files.api.serializers.mixins
"""

import logging

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


# Re-export FileConfirmSerializerMixin from its new location for backward compatibility
# This allows existing code using `from libs.drf.serializers.mixins import FileConfirmSerializerMixin`
# to continue working
from apps.files.api.serializers.mixins import (  # noqa: E402, F401
    FileConfirmSerializerMixin,
    _FileTokenField,
)
