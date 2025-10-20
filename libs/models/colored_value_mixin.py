"""Mixin for models with colored status fields."""

from django.db import models


class ColoredValueMixin(models.Model):
    """Mixin that provides colored value representation for status fields.

    This mixin allows models to define mappings between status values
    and color variants for UI display purposes. Each model using this
    mixin should define a VARIANT_MAPPING dictionary that maps status
    values to color variants.

    Attributes:
        VARIANT_MAPPING: A dict mapping status values to color variants.
                        Should be defined in the model class.
                        Can have multiple mappings for different fields.
                        Format: {field_name: {value: variant, ...}}
                        or for single field: {value: variant, ...}

    Example:
        class RecruitmentRequest(ColoredValueMixin, BaseModel):
            VARIANT_MAPPING = {
                "status": {
                    "DRAFT": ColorVariant.GREY,
                    "OPEN": ColorVariant.GREEN,
                    "PAUSED": ColorVariant.YELLOW,
                    "CLOSED": ColorVariant.RED,
                },
                "recruitment_type": {
                    "NEW_HIRE": ColorVariant.BLUE,
                    "REPLACEMENT": ColorVariant.PURPLE,
                }
            }

            @property
            def colored_status(self):
                return self.get_colored_value("status")

            @property
            def colored_recruitment_type(self):
                return self.get_colored_value("recruitment_type")
    """

    VARIANT_MAPPING: dict = {}

    class Meta:
        abstract = True

    def get_colored_value(self, field_name: str) -> dict:
        """Get colored value representation for a field.

        Args:
            field_name: Name of the field to get colored value for

        Returns:
            dict: {"value": field_value, "variant": color_variant}
        """
        field_value = getattr(self, field_name, None)

        # Get mapping for the field
        mapping = self.VARIANT_MAPPING.get(field_name, {})

        # Get variant from mapping, default to None if not found
        variant = mapping.get(field_value)

        return {"value": field_value, "variant": variant}
