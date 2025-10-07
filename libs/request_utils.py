"""Utility functions for processing HTTP requests."""

from typing import Optional

from django.http import HttpRequest

# Constants
UNKNOWN_IP = "Unknown"


def get_client_ip(request: HttpRequest) -> Optional[str]:
    """Extract the client's IP address from the request.

    Checks the X-Forwarded-For header first (for proxied requests),
    then falls back to REMOTE_ADDR.

    Args:
        request: The Django HTTP request object

    Returns:
        The client's IP address, or None if not available

    Example:
        >>> from django.http import HttpRequest
        >>> request = HttpRequest()
        >>> request.META['REMOTE_ADDR'] = '192.168.1.1'
        >>> get_client_ip(request)
        '192.168.1.1'
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        # X-Forwarded-For can contain multiple IPs, take the first one
        ip_address = x_forwarded_for.split(",")[0].strip()
    else:
        ip_address = request.META.get("REMOTE_ADDR")

    return ip_address


def get_user_agent(request: HttpRequest) -> str:
    """Extract the user agent string from the request.

    Args:
        request: The Django HTTP request object

    Returns:
        The user agent string, or empty string if not available

    Example:
        >>> from django.http import HttpRequest
        >>> request = HttpRequest()
        >>> request.META['HTTP_USER_AGENT'] = 'Mozilla/5.0'
        >>> get_user_agent(request)
        'Mozilla/5.0'
    """
    return request.META.get("HTTP_USER_AGENT", "")
