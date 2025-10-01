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
                _("Mật khẩu phải chứa ít nhất một chữ cái viết hoa."),
                code="password_no_upper",
            )
        if not re.search(r"[a-z]", password):
            raise ValidationError(
                _("Mật khẩu phải chứa ít nhất một chữ cái viết thường."),
                code="password_no_lower",
            )
        if not re.search(r"[0-9]", password):
            raise ValidationError(
                _("Mật khẩu phải chứa ít nhất một chữ số."),
                code="password_no_digit",
            )
        if not SPECIAL_CHARS_RE.search(password):
            raise ValidationError(
                _('Mật khẩu phải chứa ít nhất một ký tự đặc biệt (!@#$%^&*(),.?":{}|<>).'),
                code="password_no_special",
            )

    def get_help_text(self):
        return _("Mật khẩu phải có tối thiểu 8 ký tự, bao gồm chữ hoa, chữ thường, số và ký tự đặc biệt.")
