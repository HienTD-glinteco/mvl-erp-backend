"""Reusable nested serializers for Real Estate models.

This module provides predefined nested serializers to reduce duplication
across Real Estate serializers. All nested serializers are read-only and
provide compact representations of related models.
"""

from apps.core.api.serializers.common_nested import SimpleNestedSerializerFactory
from apps.realestate.models import Project

# Predefined nested serializers for common use cases
ProjectNestedSerializer = SimpleNestedSerializerFactory(
    Project,
    ["id", "code", "name"],
)
