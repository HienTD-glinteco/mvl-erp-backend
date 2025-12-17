import random

import nh3
from django.utils.crypto import get_random_string


def clean_html(html: str) -> str:
    return nh3.clean(html)


def normalize_header(header: str) -> str:
    """Normalize header name by stripping and lowercasing.

    Used to normalize Excel/CSV column headers for consistent mapping.

    Args:
        header: Raw header string from import file

    Returns:
        Lowercase, stripped header string

    Example:
        >>> normalize_header("  Mã Nhân Viên  ")
        "mã nhân viên"
    """
    if not header:
        return ""
    return str(header).strip().lower()


def generate_valid_password() -> str:
    """Generate a valid random password meeting complexity requirements.

    The password will contain at least one uppercase letter, one lowercase letter,
    one digit, and one special character. The total length will be 8 characters.

    Returns:
        A randomly generated valid password string.
    """
    special_chars = "!@#$%^&*()-_=+[]{}|;:,.<>?/"
    letters = "abcdefghijklmnopqrstuvwxyz"
    uppercase_letters = letters.upper()
    numbers = "0123456789"

    parts = [
        get_random_string(1, uppercase_letters),
        get_random_string(5, letters),
        get_random_string(1, numbers),
        get_random_string(1, special_chars),
    ]

    random.shuffle(parts)
    return "".join(parts)
