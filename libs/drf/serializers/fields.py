"""
Flexible serializer fields for import handlers.

These fields handle various input formats for dates, decimals, and booleans
commonly found in Excel/CSV imports.
"""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from rest_framework import serializers


class FlexibleDateField(serializers.DateField):
    """Date field that accepts multiple input formats.

    Supports:
    - date objects
    - datetime objects (extracts date)
    - ISO format strings (YYYY-MM-DD)
    - Vietnamese format strings (DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY)
    """

    DATE_FORMATS = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y/%m/%d",
        "%d.%m.%Y",
    ]

    def to_internal_value(self, value: Any) -> date | None:
        """Convert input value to date object."""
        if not value:
            return None

        if isinstance(value, date):
            return value

        if isinstance(value, datetime):
            return value.date()

        value_str = str(value).strip()
        if not value_str or value_str == "-":
            return None

        # Try standard DRF parsing first
        try:
            return super().to_internal_value(value_str)
        except serializers.ValidationError:
            pass

        # Try additional formats
        for fmt in self.DATE_FORMATS:
            try:
                return datetime.strptime(value_str, fmt).date()
            except (ValueError, TypeError):
                continue

        self.fail("invalid", format="YYYY-MM-DD or DD/MM/YYYY")
        return None


class FlexibleDecimalField(serializers.DecimalField):
    """Decimal field that accepts comma as decimal separator.

    Supports:
    - int, float, Decimal objects
    - String with dot as decimal separator (e.g., "1000.50")
    - String with comma as decimal separator (e.g., "1000,50")
    """

    def to_internal_value(self, value: Any) -> Decimal | None:
        """Convert input value to Decimal object."""
        if value is None or value == "":
            return None

        if isinstance(value, Decimal):
            return value

        if isinstance(value, (int, float)):
            return Decimal(str(value))

        value_str = str(value).strip()
        if not value_str:
            return None

        try:
            # Replace comma with dot for decimal separator
            value_str = value_str.replace(",", ".")
            return Decimal(value_str)
        except InvalidOperation:
            self.fail("invalid")
            return None


class FlexibleBooleanField(serializers.BooleanField):
    """Boolean field that accepts Vietnamese text values.

    Supports:
    - bool objects
    - "có", "yes", "true", "1" → True
    - "không", "no", "false", "0" → False
    """

    BOOLEAN_MAPPING = {
        "có": True,
        "yes": True,
        "true": True,
        "1": True,
        "không": False,
        "no": False,
        "false": False,
        "0": False,
    }

    def to_internal_value(self, value: Any) -> bool | None:
        """Convert input value to boolean."""
        if value is None or value == "":
            return None

        if isinstance(value, bool):
            return value

        value_str = str(value).strip().lower()
        if not value_str:
            return None

        if value_str in self.BOOLEAN_MAPPING:
            return self.BOOLEAN_MAPPING[value_str]

        # Try standard DRF parsing
        return super().to_internal_value(value)
