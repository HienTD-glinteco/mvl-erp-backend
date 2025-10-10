"""
Schema builder for auto-generating export schemas from Django models.
"""

from django.db import models
from django.db.models.fields import AutoField

from .constants import DEFAULT_EXCLUDED_FIELDS


class SchemaBuilder:
    """
    Builder for auto-generating export schemas from Django models.
    """

    def __init__(self, excluded_fields=None):
        """
        Initialize schema builder.

        Args:
            excluded_fields: Set of field names to exclude from export
        """
        self.excluded_fields = excluded_fields or DEFAULT_EXCLUDED_FIELDS

    def build_from_model(self, model_class, queryset=None):
        """
        Build export schema from a Django model.

        Args:
            model_class: Django model class
            queryset: Optional queryset to get data from

        Returns:
            dict: Export schema with structure:
                {
                    "sheets": [{
                        "name": "ModelName",
                        "headers": ["field1", "field2", ...],
                        "data": [...]
                    }]
                }
        """
        # Get model fields
        fields = self._get_model_fields(model_class)

        # Build schema
        schema = {
            "sheets": [
                {
                    "name": model_class._meta.verbose_name_plural.title()
                    if hasattr(model_class._meta, "verbose_name_plural")
                    else model_class.__name__,
                    "headers": [self._get_field_label(field) for field in fields],
                    "field_names": [field.name for field in fields],
                    "data": [],
                }
            ]
        }

        # Add data if queryset provided
        if queryset is not None:
            schema["sheets"][0]["data"] = self._serialize_queryset(queryset, fields)

        return schema

    def _get_model_fields(self, model_class):
        """
        Get exportable fields from a Django model.

        Args:
            model_class: Django model class

        Returns:
            list: List of field objects to export
        """
        fields = []
        for field in model_class._meta.get_fields():
            # Skip excluded fields
            if field.name in self.excluded_fields:
                continue

            # Skip auto fields (except if explicitly included)
            if isinstance(field, AutoField):
                continue

            # Skip reverse relations
            if field.one_to_many or field.many_to_many:
                continue

            # Skip private fields
            if field.name.startswith("_"):
                continue

            fields.append(field)

        return fields

    def _get_field_label(self, field):
        """
        Get human-readable label for a field.

        Args:
            field: Django model field

        Returns:
            str: Field label
        """
        if hasattr(field, "verbose_name") and field.verbose_name:
            return str(field.verbose_name).title()
        return field.name.replace("_", " ").title()

    def _serialize_queryset(self, queryset, fields):
        """
        Serialize queryset to list of dictionaries.

        Args:
            queryset: Django queryset
            fields: List of fields to include

        Returns:
            list: List of dictionaries with field values
        """
        data = []
        for obj in queryset:
            row = {}
            for field in fields:
                value = getattr(obj, field.name, None)

                # Handle special field types
                if value is None:
                    row[field.name] = ""
                elif isinstance(field, models.ForeignKey):
                    row[field.name] = str(value) if value else ""
                elif isinstance(field, models.DateTimeField):
                    row[field.name] = value.isoformat() if value else ""
                elif isinstance(field, models.DateField):
                    row[field.name] = value.isoformat() if value else ""
                elif isinstance(field, models.BooleanField):
                    row[field.name] = "Yes" if value else "No"
                elif isinstance(field, (models.DecimalField, models.FloatField)):
                    row[field.name] = float(value) if value is not None else ""
                elif isinstance(field, models.IntegerField):
                    row[field.name] = int(value) if value is not None else ""
                else:
                    row[field.name] = str(value)

            data.append(row)

        return data
