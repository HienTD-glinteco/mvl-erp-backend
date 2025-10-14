"""Constants for serializer mixins and utilities."""

# Field filtering mixin messages
LOG_FIELD_FILTERING_APPLIED = "Applied field filtering: requested=%s, final=%s"
LOG_NO_REQUEST_CONTEXT = "No request in serializer context, skipping field filtering"
LOG_NO_FIELDS_PARAM = "No fields parameter in request, using all fields"
LOG_USING_DEFAULT_FIELDS = "Using default_fields attribute from serializer"
WARNING_INVALID_FIELD = "Invalid field '%s' requested but not in serializer fields"
