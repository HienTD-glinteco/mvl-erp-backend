"""Tests for custom exception handler.

This module tests that Django ValidationError raised in signals
is properly converted to DRF ValidationError with 400 status and JSON response.
"""

import pytest
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.test import APIRequestFactory

from libs.drf.custom_exception_handler import exception_handler


@pytest.mark.django_db
class TestExceptionHandler:
    """Test custom exception handler converts Django ValidationError properly."""

    def setup_method(self):
        """Setup test request context."""
        self.factory = APIRequestFactory()
        self.request = self.factory.get("/")
        self.context = {"request": self.request}

    def test_django_validation_error_simple_message(self):
        """Test Django ValidationError with simple string message."""
        exc = DjangoValidationError("Cannot create proposal after deadline")
        response = exception_handler(exc, self.context)

        assert response is not None
        assert response.status_code == 400
        assert "errors" in response.data or "non_field_errors" in response.data

    def test_django_validation_error_message_dict(self):
        """Test Django ValidationError with field-specific errors."""
        exc = DjangoValidationError({"field1": "Error on field1", "field2": "Error on field2"})
        response = exception_handler(exc, self.context)

        assert response is not None
        assert response.status_code == 400

    def test_django_validation_error_message_list(self):
        """Test Django ValidationError with list of messages."""
        exc = DjangoValidationError(["Error 1", "Error 2"])
        response = exception_handler(exc, self.context)

        assert response is not None
        assert response.status_code == 400

    def test_drf_validation_error_unchanged(self):
        """Test that DRF ValidationError is handled normally."""
        exc = DRFValidationError({"field": "This field is required"})
        response = exception_handler(exc, self.context)

        assert response is not None
        assert response.status_code == 400
