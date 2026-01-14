"""
Tests for custom pagination classes.
"""

import pytest
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from libs.drf.pagination import PageNumberWithSizePagination


@pytest.fixture
def pagination_instance():
    """Create a pagination instance for testing."""
    return PageNumberWithSizePagination()


@pytest.fixture
def request_factory():
    """Create an API request factory."""
    return APIRequestFactory()


class TestPageNumberWithSizePagination:
    """Test cases for PageNumberWithSizePagination."""

    def test_default_page_size(self, pagination_instance):
        """Test that default page size is set correctly."""
        assert pagination_instance.page_size == 25

    def test_max_page_size(self, pagination_instance):
        """Test that max page size is set correctly."""
        assert pagination_instance.max_page_size == 100

    def test_page_size_query_param(self, pagination_instance):
        """Test that page_size query parameter is configured."""
        assert pagination_instance.page_size_query_param == "page_size"

    def test_custom_page_size(self, pagination_instance, request_factory):
        """Test that custom page size can be set via query parameter."""
        request = Request(request_factory.get("/", {"page_size": "50"}))
        page_size = pagination_instance.get_page_size(request)
        assert page_size == 50

    def test_page_size_exceeds_max(self, pagination_instance, request_factory):
        """Test that page size is capped at max_page_size."""
        request = Request(request_factory.get("/", {"page_size": "200"}))
        page_size = pagination_instance.get_page_size(request)
        assert page_size == 100

    def test_invalid_page_size(self, pagination_instance, request_factory):
        """Test that invalid page size falls back to default."""
        request = Request(request_factory.get("/", {"page_size": "invalid"}))
        page_size = pagination_instance.get_page_size(request)
        assert page_size == 25

    def test_zero_page_size(self, pagination_instance, request_factory):
        """Test that zero page size falls back to default."""
        request = Request(request_factory.get("/", {"page_size": "0"}))
        page_size = pagination_instance.get_page_size(request)
        assert page_size == 25

    def test_negative_page_size(self, pagination_instance, request_factory):
        """Test that negative page size falls back to default."""
        request = Request(request_factory.get("/", {"page_size": "-10"}))
        page_size = pagination_instance.get_page_size(request)
        assert page_size == 25
