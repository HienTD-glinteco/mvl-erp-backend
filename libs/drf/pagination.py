"""
Custom pagination classes for the API.

Provides pagination classes with configurable page size via query parameters.
"""

from rest_framework.pagination import PageNumberPagination


class PageNumberWithSizePagination(PageNumberPagination):
    """
    Custom pagination class that allows clients to control page size.

    Query Parameters:
        - page: Page number (default: 1)
        - page_size: Number of items per page (default: 25, max: 100)

    Example:
        GET /api/endpoint/?page=2&page_size=50
    """

    page_size_query_param = "page_size"
    max_page_size = 100
