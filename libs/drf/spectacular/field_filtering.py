"""
Enhanced AutoSchema for automatic API documentation generation.

This module provides a custom AutoSchema class that extends drf-spectacular's
AutoSchema with additional features like automatic field filtering documentation.
The design is extensible to support more features in the future.
"""

import django_filters
from drf_spectacular.extensions import OpenApiSerializerExtension
from drf_spectacular.openapi import AutoSchema
from drf_spectacular.utils import OpenApiParameter

from libs.drf.serializers.mixins import FieldFilteringSerializerMixin


class EnhancedAutoSchema(AutoSchema):
    """
    Enhanced AutoSchema that automatically documents various API features.

    This custom AutoSchema extends drf-spectacular's AutoSchema to provide
    automatic documentation for features like field filtering. The design
    is modular and extensible to support additional features in the future.

    Currently supported features:
    - Field filtering via FieldFilteringSerializerMixin
    - Filterset parameters for ExportXLSXMixin's export action
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

        # Add filterset parameters for export action if applicable
        parameters = self._add_export_filterset_parameters(parameters)

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

        # Get all available fields from the serializer Meta class, not just instantiated fields
        # This ensures we show all fields that could be requested, even if some are filtered by default
        all_fields = []
        if hasattr(serializer_class, "Meta") and hasattr(serializer_class.Meta, "fields"):
            fields_attr = serializer_class.Meta.fields
            # Handle both __all__ and explicit field lists
            if fields_attr == "__all__":
                # If fields is __all__, get from the current serializer instance
                all_fields = list(serializer.fields.keys())
            else:
                # Otherwise, use the explicit field list from Meta
                all_fields = list(fields_attr) if isinstance(fields_attr, (list, tuple)) else [fields_attr]
        else:
            # Fallback to instantiated fields
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

    def _add_export_filterset_parameters(self, parameters):
        """
        Add filterset parameters to export action documentation.

        This method checks if:
        1. The current operation is the 'export' action (from ExportXLSXMixin)
        2. The view has a filterset_class defined
        
        If both conditions are met, it extracts filter parameters from the filterset
        and adds them to the OpenAPI documentation for the export endpoint.

        Args:
            parameters: Existing list of parameters

        Returns:
            Updated list of parameters with filterset parameters if applicable
        """
        # Only process GET requests
        if self.method.upper() != "GET":
            return parameters

        # Check if this is the export action
        view = getattr(self, "view", None)
        if not view:
            return parameters

        # Get the action name - for @action decorated methods
        action_name = getattr(view, "action", None)
        if action_name != "export":
            return parameters

        # Check if the view has a filterset_class
        filterset_class = getattr(view, "filterset_class", None)
        if not filterset_class:
            return parameters

        # Check if filterset_class is a django_filters.FilterSet subclass
        if not (isinstance(filterset_class, type) and issubclass(filterset_class, django_filters.FilterSet)):
            return parameters

        # Extract filter parameters from the filterset
        filter_params = self._extract_filterset_parameters(filterset_class)

        return parameters + filter_params

    def _extract_filterset_parameters(self, filterset_class):
        """
        Extract OpenAPI parameters from a django-filter FilterSet class.

        Args:
            filterset_class: The FilterSet class to extract parameters from

        Returns:
            List of OpenApiParameter objects representing the filters
        """
        parameters = []

        # Get all filters from the filterset
        filters = getattr(filterset_class, "base_filters", {})

        for filter_name, filter_instance in filters.items():
            # Build parameter description based on filter type
            description = self._build_filter_description(filter_instance, filter_name)

            # Determine parameter type
            param_type = self._get_filter_param_type(filter_instance)

            # Determine if the filter has choices (enum)
            enum_values = self._get_filter_enum_values(filter_instance)

            # Create OpenApiParameter
            param = OpenApiParameter(
                name=filter_name,
                type=param_type,
                location="query",
                required=False,
                description=description,
                enum=enum_values if enum_values else None,
            )

            parameters.append(param)

        return parameters

    def _build_filter_description(self, filter_instance, filter_name):
        """
        Build a description for a filter parameter.

        Args:
            filter_instance: The filter instance
            filter_name: The name of the filter

        Returns:
            Description string
        """
        # Get the field name if different from filter name
        field_name = getattr(filter_instance, "field_name", filter_name)

        # Get the lookup expression
        lookup_expr = getattr(filter_instance, "lookup_expr", "exact")

        # Build base description
        if lookup_expr == "exact":
            description = f"Filter by {field_name}"
        elif lookup_expr == "icontains":
            description = f"Filter by {field_name} (case-insensitive partial match)"
        elif lookup_expr == "gte":
            description = f"Filter by {field_name} (greater than or equal)"
        elif lookup_expr == "lte":
            description = f"Filter by {field_name} (less than or equal)"
        elif lookup_expr == "gt":
            description = f"Filter by {field_name} (greater than)"
        elif lookup_expr == "lt":
            description = f"Filter by {field_name} (less than)"
        else:
            description = f"Filter by {field_name} ({lookup_expr})"

        # Add help text if available
        help_text = getattr(filter_instance, "extra", {}).get("help_text")
        if help_text:
            description = f"{description}. {help_text}"

        return description

    def _get_filter_param_type(self, filter_instance):
        """
        Determine the OpenAPI parameter type for a filter.

        Args:
            filter_instance: The filter instance

        Returns:
            OpenAPI type (str, int, bool, etc.)
        """
        # Map django-filter types to OpenAPI types
        if isinstance(filter_instance, django_filters.BooleanFilter):
            return bool
        elif isinstance(filter_instance, django_filters.NumberFilter):
            return int
        elif isinstance(filter_instance, (django_filters.DateFilter, django_filters.DateTimeFilter)):
            return str  # OpenAPI represents dates as strings
        elif isinstance(filter_instance, django_filters.BaseInFilter):
            return str  # Comma-separated values
        elif isinstance(filter_instance, django_filters.MultipleChoiceFilter):
            return str  # Can specify multiple values
        else:
            return str  # Default to string

    def _get_filter_enum_values(self, filter_instance):
        """
        Extract enum values from a filter if it has choices.

        Args:
            filter_instance: The filter instance

        Returns:
            List of enum values or None
        """
        # Check if filter has choices
        if isinstance(filter_instance, (django_filters.ChoiceFilter, django_filters.MultipleChoiceFilter)):
            choices = getattr(filter_instance, "extra", {}).get("choices")
            if choices:
                # Extract choice values (first element of each tuple)
                return [str(choice[0]) for choice in choices]

        return None


class FieldFilteringSerializerExtension(OpenApiSerializerExtension):
    """
    Serializer extension for FieldFilteringSerializerMixin.

    This extension helps drf-spectacular understand that serializers using
    FieldFilteringSerializerMixin have dynamic fields based on request parameters.
    """

    target_class = "libs.drf.serializers.mixins.FieldFilteringSerializerMixin"

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
