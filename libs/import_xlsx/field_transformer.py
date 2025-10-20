"""
Field transformation utilities for XLSX imports.

This module provides the FieldTransformer class for combining, transforming,
and validating field values according to mapping configuration.
"""

import logging
from datetime import datetime
from typing import Any

from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)

# Transformation error messages
ERROR_COMBINE_MISSING_VALUE = "Missing value for combine field: {field}"
ERROR_INVALID_DATE_FORMAT = "Invalid date format for field '{field}': {value}"
ERROR_TRANSFORMATION_FAILED = "Transformation failed for field '{field}': {error}"


class FieldTransformer:
    """
    Transform and combine field values according to configuration.

    Supports:
    - Combining multiple fields into one (e.g., day/month/year → date)
    - Date format parsing and validation
    - Custom transformations

    Example usage:
        transformer = FieldTransformer()

        # Combine date fields
        date_value = transformer.combine_fields(
            ["2024", "01", "15"],
            format="YYYY-MM-DD"
        )
        # Returns: "2024-01-15"

        # Transform with config
        value = transformer.transform_field(
            field_name="start_date",
            field_config={
                "combine": ["Start Day", "Start Month", "Start Year"],
                "format": "YYYY-MM-DD"
            },
            row_data={
                "Start Day": "15",
                "Start Month": "01",
                "Start Year": "2024"
            }
        )
    """

    # Supported date format patterns
    DATE_FORMATS = {
        "YYYY-MM-DD": "%Y-%m-%d",
        "DD/MM/YYYY": "%d/%m/%Y",
        "MM/DD/YYYY": "%m/%d/%Y",
        "DD-MM-YYYY": "%d-%m-%Y",
        "YYYY/MM/DD": "%Y/%m/%d",
        "DD.MM.YYYY": "%d.%m.%Y",
    }

    def transform_field(
        self,
        field_name: str,
        field_config: dict | str,
        row_data: dict,
    ) -> Any:
        """
        Transform a field value according to configuration.

        Args:
            field_name: Target field name
            field_config: Field configuration (string for simple mapping, dict for complex)
            row_data: Dictionary of row data from Excel

        Returns:
            Transformed field value

        Raises:
            ValueError: If transformation fails
        """
        # Simple string mapping - just get the value
        if isinstance(field_config, str):
            column_name = field_config
            return row_data.get(column_name)

        # Complex field configuration
        if isinstance(field_config, dict):
            # Handle combine fields (e.g., day/month/year → date)
            if "combine" in field_config:
                return self._combine_fields(
                    field_name=field_name,
                    field_config=field_config,
                    row_data=row_data,
                )

            # Handle lookup column for relational fields
            if "lookup" in field_config:
                column_name = field_config["lookup"]
                return row_data.get(column_name)

        return None

    def _combine_fields(
        self,
        field_name: str,
        field_config: dict,
        row_data: dict,
    ) -> Any:
        """
        Combine multiple field values into one.

        Args:
            field_name: Target field name
            field_config: Field configuration with 'combine' key
            row_data: Dictionary of row data

        Returns:
            Combined field value

        Raises:
            ValueError: If combination fails
        """
        try:
            combine_fields = field_config["combine"]
            values = []

            for source_field in combine_fields:
                value = row_data.get(source_field)
                if value is None or value == "":
                    raise ValueError(_(ERROR_COMBINE_MISSING_VALUE).format(field=source_field))
                values.append(str(value).strip())

            # Get format if specified
            format_pattern = field_config.get("format")

            # If format is a date format, parse and combine
            if format_pattern and format_pattern in self.DATE_FORMATS:
                return self._parse_date(
                    values=values,
                    format_pattern=format_pattern,
                    field_name=field_name,
                )

            # Default: join with separator
            separator = field_config.get("separator", "-")
            return separator.join(values)

        except Exception as e:
            logger.error(f"Error combining fields for {field_name}: {e}")
            raise ValueError(_(ERROR_TRANSFORMATION_FAILED).format(field=field_name, error=str(e)))

    def _parse_date(
        self,
        values: list[str],
        format_pattern: str,
        field_name: str,
    ) -> str:
        """
        Parse date from multiple values.

        Args:
            values: List of date component values
            format_pattern: Date format pattern (e.g., "YYYY-MM-DD")
            field_name: Field name for error messages

        Returns:
            Formatted date string

        Raises:
            ValueError: If date parsing fails
        """
        try:
            # For common patterns like YYYY-MM-DD with 3 values
            if format_pattern == "YYYY-MM-DD" and len(values) == 3:
                year, month, day = values
                # Validate and format
                date_obj = datetime(int(year), int(month), int(day))
                return date_obj.strftime("%Y-%m-%d")

            # For DD/MM/YYYY with 3 values
            elif format_pattern == "DD/MM/YYYY" and len(values) == 3:
                day, month, year = values
                date_obj = datetime(int(year), int(month), int(day))
                return date_obj.strftime("%Y-%m-%d")

            # For MM/DD/YYYY with 3 values
            elif format_pattern == "MM/DD/YYYY" and len(values) == 3:
                month, day, year = values
                date_obj = datetime(int(year), int(month), int(day))
                return date_obj.strftime("%Y-%m-%d")

            # Generic: try to join and parse
            else:
                separator = "-" if "-" in format_pattern else "/"
                date_string = separator.join(values)
                strptime_format = self.DATE_FORMATS.get(format_pattern, "%Y-%m-%d")
                date_obj = datetime.strptime(date_string, strptime_format)
                return date_obj.strftime("%Y-%m-%d")

        except (ValueError, IndexError) as e:
            logger.error(f"Error parsing date for {field_name}: {e}")
            raise ValueError(
                _(ERROR_INVALID_DATE_FORMAT).format(
                    field=field_name,
                    value=", ".join(values),
                )
            )

    def transform_row(
        self,
        fields_config: dict,
        row_data: dict,
    ) -> dict:
        """
        Transform all fields in a row according to configuration.

        Args:
            fields_config: Fields configuration dictionary
            row_data: Dictionary of row data from Excel

        Returns:
            dict: Transformed row data with model field names as keys
        """
        transformed_data = {}

        for field_name, field_config in fields_config.items():
            try:
                value = self.transform_field(
                    field_name=field_name,
                    field_config=field_config,
                    row_data=row_data,
                )
                transformed_data[field_name] = value
            except ValueError as e:
                # Log error but continue processing other fields
                logger.warning(f"Error transforming field {field_name}: {e}")
                transformed_data[field_name] = None

        return transformed_data
