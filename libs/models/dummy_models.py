"""
Test utilities for audit_logging tests.

This module provides helper functions for creating dynamic test models
to avoid model registration warnings.
"""

import uuid

from django.db import models


def create_dummy_model(base_name="DummyModel", app_label="audit_logging", fields=None):
    """
    Create a dynamic Django model with a unique name.

    This function creates a new model class using type() with a dynamically
    generated unique name to avoid model registration warnings when running tests.

    Args:
        base_name: Base name for the model (default: "DummyModel")
        app_label: Django app label for the model (default: "audit_logging")
        fields: Dictionary of field names to field instances (default: None)

    Returns:
        A new model class that inherits from models.Model

    Example:
        >>> TestModel = create_dummy_model(
        ...     base_name="TestModel",
        ...     fields={
        ...         'name': models.CharField(max_length=100),
        ...         'value': models.IntegerField(default=0)
        ...     }
        ... )
    """
    fields = fields or {}
    # Generate a unique name using UUID to avoid registration conflicts
    name = f"{base_name}_{uuid.uuid4().hex}"

    # Create the Meta class
    meta_class = type("Meta", (), {"app_label": app_label})

    # Combine all attributes for the model class
    attrs = {
        "__module__": __name__,
        "Meta": meta_class,
        **fields,
    }

    # Create and return the model class
    return type(name, (models.Model,), attrs)
