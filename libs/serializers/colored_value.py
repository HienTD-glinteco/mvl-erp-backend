"""Serializer for colored value representation."""

from rest_framework import serializers

from libs.constants import ColorVariant


class ColoredValueSerializer(serializers.Serializer):
    """Serializer for status with color variant.

    This serializer provides a standardized format for returning
    status or other choice field values along with their associated
    color variants for UI display purposes.

    Example:
        {"value": "OPEN", "variant": "GREEN"}
    """

    value = serializers.CharField(read_only=True)
    variant = serializers.ChoiceField(choices=ColorVariant.choices, read_only=True)
