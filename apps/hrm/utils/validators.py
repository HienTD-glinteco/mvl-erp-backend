"""Validators for HRM models

Reusable validation functions for common fields like phone numbers and national IDs.
"""
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from ..constants import (
    NATIONAL_ID_LENGTH_12,
    NATIONAL_ID_LENGTH_9,
    PHONE_INTL_LENGTH,
    PHONE_LOCAL_LENGTH,
)


def validate_national_id(value):
    """Validate that national ID is exactly 9 or 12 digits"""
    if value:
        if not value.isdigit():
            raise ValidationError(_("National ID must contain only digits."))
        if len(value) not in [NATIONAL_ID_LENGTH_9, NATIONAL_ID_LENGTH_12]:
            raise ValidationError(_("National ID must be exactly 9 or 12 digits."))


def validate_phone(value):
    """Validate Vietnamese phone number format"""
    if value:
        # Remove spaces for validation
        cleaned = value.replace(" ", "").replace("-", "")

        # Check for valid characters (digits and optional leading +)
        if not cleaned.replace("+", "").isdigit():
            raise ValidationError(_("Phone number must contain only digits and optional leading '+'."))

        # Vietnamese phone validation
        if cleaned.startswith("+84"):
            # International format: +84 followed by 9 digits
            if len(cleaned) != PHONE_INTL_LENGTH:
                raise ValidationError(_("Phone number with +84 must be followed by 9 digits."))
        elif cleaned.startswith("0"):
            # Local format: 0 followed by 9 digits (total 10)
            if len(cleaned) != PHONE_LOCAL_LENGTH:
                raise ValidationError(_("Phone number starting with 0 must be exactly 10 digits."))
        else:
            raise ValidationError(_("Phone number must start with 0 or +84."))
