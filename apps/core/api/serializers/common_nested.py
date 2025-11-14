"""Reusable nested serializer factory for creating simple read-only nested serializers.

This module provides a factory function that can be used across all apps
to create consistent nested serializers for related models.
"""

from rest_framework import serializers


def SimpleNestedSerializerFactory(model, fields):
    """Factory function to create simple read-only nested serializers.

    This factory dynamically creates read-only ModelSerializer classes for
    nested representations of models. The generated serializers are lightweight
    and designed for consistent API responses across the application.

    Args:
        model: Django model class
        fields: List of field names to include in the serializer

    Returns:
        A ModelSerializer class with specified fields as read-only

    Example:
        >>> from apps.core.api.serializers.common_nested import SimpleNestedSerializerFactory
        >>> from apps.hrm.models import Employee
        >>> EmployeeNestedSerializer = SimpleNestedSerializerFactory(
        ...     Employee, ["id", "code", "fullname"]
        ... )
    """
    meta_attrs = {
        "model": model,
        "fields": fields,
        "read_only_fields": fields,
    }
    Meta = type("Meta", (), meta_attrs)
    serializer_name = f"{model.__name__}NestedSerializer"
    cls = type(
        serializer_name,
        (serializers.ModelSerializer,),
        {
            "Meta": Meta,
            "__module__": __name__,  # Improve debugging by setting correct module
        },
    )
    return cls
