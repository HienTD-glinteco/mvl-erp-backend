"""
AutoSchema extension for documenting field filtering query parameters.

This module provides automatic documentation generation for APIs that use
FieldFilteringSerializerMixin. It adds the 'fields' query parameter to the
OpenAPI schema with detailed information about available fields.
"""

from typing import List

from drf_spectacular.drainage import warn
from drf_spectacular.extensions import OpenApiSerializerExtension
from drf_spectacular.openapi import AutoSchema
from drf_spectacular.plumbing import build_parameter_type

from libs.serializers.mixins import FieldFilteringSerializerMixin


class FieldFilteringAutoSchema(AutoSchema):
    """
    Custom AutoSchema that adds 'fields' query parameter documentation
    when serializer uses FieldFilteringSerializerMixin.
    """

    def get_operation_id(self):
        """Get operation ID (delegated to parent)."""
        return super().get_operation_id()

    def get_override_parameters(self):
        """
        Add 'fields' query parameter to API documentation if serializer
        uses FieldFilteringSerializerMixin.
        """
        parameters = super().get_override_parameters()

        # Only add fields parameter for read operations (GET, HEAD, OPTIONS)
        if self.method.upper() not in ["GET", "HEAD", "OPTIONS"]:
            return parameters

        # Get the serializer class
        serializer = self.get_serializer()
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
            description += (
                "If the `fields` parameter is not provided, all available fields will be returned."
            )

        # Create the parameter schema
        fields_parameter = build_parameter_type(
            name="fields",
            schema={"type": "string"},
            location="query",
            required=False,
            description=description,
        )

        # Add example to the parameter
        if len(all_fields) >= 3:
            example_fields = sorted(all_fields)[:3]
        else:
            example_fields = sorted(all_fields)
        
        fields_parameter["example"] = ",".join(example_fields)

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
