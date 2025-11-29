import nh3


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
