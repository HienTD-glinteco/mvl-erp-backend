"""
Enhanced AutoSchema for automatic API documentation generation.

This module provides a custom AutoSchema class that extends drf-spectacular's
AutoSchema with additional features like automatic field filtering documentation.
The design is extensible to support more features in the future.
"""

from drf_spectacular.extensions import OpenApiSerializerExtension
from drf_spectacular.openapi import AutoSchema
from drf_spectacular.utils import OpenApiParameter

from libs.serializers.mixins import FieldFilteringSerializerMixin


class EnhancedAutoSchema(AutoSchema):
    """
    Enhanced AutoSchema that automatically documents various API features.

    This custom AutoSchema extends drf-spectacular's AutoSchema to provide
    automatic documentation for features like field filtering. The design
    is modular and extensible to support additional features in the future.

    Currently supported features:
    - Field filtering via FieldFilteringSerializerMixin
    """

    def get_override_parameters(self):
        """
        Override to add custom query parameters to API documentation.

        This method extends the base implementation by adding documentation
        for various features based on the serializer and view configuration.
        """
        parameters = super().get_override_parameters()

        # Add field filtering documentation if applicable
        parameters = self._add_field_filtering_parameter(parameters)

        return parameters

    def _add_field_filtering_parameter(self, parameters):
        """
        Add 'fields' query parameter documentation if serializer uses FieldFilteringSerializerMixin.

        Args:
            parameters: Existing list of parameters

        Returns:
            Updated list of parameters with field filtering documentation if applicable
        """
        # Only add fields parameter for read operations (GET, HEAD, OPTIONS)
        if self.method.upper() not in ["GET", "HEAD", "OPTIONS"]:
            return parameters

        # Get the serializer class
        serializer = self._get_serializer()
        if not serializer:
            return parameters

        serializer_class = serializer.__class__

        # Check if serializer uses FieldFilteringSerializerMixin
        if not issubclass(serializer_class, FieldFilteringSerializerMixin):
            return parameters

        # Get all available fields from the serializer
        all_fields = list(serializer.fields.keys())

        if not all_fields:
            return parameters

        # Check if serializer has default_fields
        default_fields = getattr(serializer_class, "default_fields", None)

        # Build description
        field_list = ", ".join(f"`{f}`" for f in sorted(all_fields))
        description = (
            f"Comma-separated list of fields to include in the response.\n\n"
            f"**Available fields:** {field_list}\n\n"
            f"**Usage:** Specify field names separated by commas (e.g., `?fields=id,name,email`)\n\n"
        )

        if default_fields:
            default_field_list = ", ".join(f"`{f}`" for f in default_fields)
            description += (
                f"**Default fields (when not specified):** {default_field_list}\n\n"
                f"If the `fields` parameter is not provided, only the default fields will be returned.\n"
            )
        else:
            description += "If the `fields` parameter is not provided, all available fields will be returned."

        # Create the parameter using OpenApiParameter
        fields_parameter = OpenApiParameter(
            name="fields",
            type=str,
            location="query",
            required=False,
            description=description,
        )

        return parameters + [fields_parameter]


class FieldFilteringSerializerExtension(OpenApiSerializerExtension):
    """
    Serializer extension for FieldFilteringSerializerMixin.

    This extension helps drf-spectacular understand that serializers using
    FieldFilteringSerializerMixin have dynamic fields based on request parameters.
    """

    target_class = "libs.serializers.mixins.FieldFilteringSerializerMixin"

    def map_serializer(self, auto_schema, direction):
        """
        Map the serializer, noting that fields may be filtered dynamically.

        This method is called by drf-spectacular when processing serializers.
        We don't need to modify the schema here as the AutoSchema extension
        handles the query parameter documentation.
        """
        # Let the default serializer mapping handle this
        return None


# Backward compatibility alias
FieldFilteringAutoSchema = EnhancedAutoSchema
