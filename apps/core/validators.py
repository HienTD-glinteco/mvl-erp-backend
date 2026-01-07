import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

SPECIAL_CHARS_PATTERN = r'[!@#$%^&*(),.?":{}|<>]'
SPECIAL_CHARS_RE = re.compile(SPECIAL_CHARS_PATTERN)


class ComplexPasswordValidator:
    """
    Validate that the password contains at least one uppercase letter,
    one lowercase letter, one digit, and one special character.
    """

    def validate(self, password, user=None):
        if not re.search(r"[A-Z]", password):
            raise ValidationError(
                _("Password must contain at least one uppercase letter."),
                code="password_no_upper",
            )
        if not re.search(r"[a-z]", password):
            raise ValidationError(
                _("Password must contain at least one lowercase letter."),
                code="password_no_lower",
            )
        if not re.search(r"[0-9]", password):
            raise ValidationError(
                _("Password must contain at least one digit."),
                code="password_no_digit",
            )
        if not SPECIAL_CHARS_RE.search(password):
            raise ValidationError(
                # xgettext:no-python-format
                _('Password must contain at least one special character (!@#$%^&*(),.?":{}|<>).'),
                code="password_no_special",
            )

    def get_help_text(self):
        return _(
            "Password must be at least 8 characters long and include uppercase, lowercase, digits and special characters."
        )
