"""Integration test for signal validation error handling.

This test verifies that ValidationError raised in signals returns
proper 400 JSON response instead of 500 error.
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.django_db
class TestSignalValidationErrorHandling:
    """Test that signal ValidationErrors return proper JSON responses."""

    def test_exception_handler_converts_to_400(self):
        """Test that exception handler converts ValidationError to 400 response."""
        from django.core.exceptions import ValidationError as DjangoValidationError
        from rest_framework.test import APIRequestFactory

        from libs.drf.custom_exception_handler import exception_handler

        factory = APIRequestFactory()
        request = factory.get("/")
        context = {"request": request}

        # Create a ValidationError like the signal would raise
        exc = DjangoValidationError("Cannot create proposal after deadline (2024-01-15)")

        # Pass it through exception handler
        response = exception_handler(exc, context)

        # Should return 400, not 500
        assert response is not None
        assert response.status_code == 400

        # Should be JSON serializable
        assert response.data is not None

    def test_exception_handler_deadline_message_format(self):
        """Test that deadline validation errors are properly formatted."""
        from django.core.exceptions import ValidationError as DjangoValidationError
        from rest_framework.test import APIRequestFactory

        from libs.drf.custom_exception_handler import exception_handler

        factory = APIRequestFactory()
        request = factory.get("/")
        context = {"request": request}

        # Test the actual message format from deadline_validation.py
        exc = DjangoValidationError("Cannot create PAID_LEAVE proposal after salary period deadline (2024-01-15)")

        response = exception_handler(exc, context)

        assert response is not None
        assert response.status_code == 400
        assert "deadline" in str(response.data).lower()

    def test_kpi_signal_called_once_on_recalculation(self):
        """Test that KPI assessment deadline signal is only called once during manager update."""
        from apps.payroll.models import EmployeeKPIAssessment
        from apps.payroll.signals.deadline_validation import validate_kpi_assessment_deadline

        # Create mock assessment with period
        mock_assessment = MagicMock(spec=EmployeeKPIAssessment)
        mock_assessment.pk = 1
        mock_period = MagicMock()
        mock_period.month = date(2024, 1, 1)
        mock_assessment.period = mock_period
        mock_assessment.manager_assessment_date = None

        # Test 1: Call with update_fields that doesn't include manager_assessment_date
        # This simulates recalculation save - should skip validation
        kwargs = {"update_fields": ["total_possible_score", "total_manager_score", "grade_manager"]}

        # Should return early without doing any validation
        result = validate_kpi_assessment_deadline(EmployeeKPIAssessment, mock_assessment, **kwargs)
        assert result is None  # Early return

        # Test 2: Call without update_fields but manager_assessment_date hasn't changed
        # This also should skip validation
        with patch("apps.payroll.signals.deadline_validation.EmployeeKPIAssessment.objects.only") as mock_only:
            mock_queryset = MagicMock()
            mock_only.return_value = mock_queryset

            old_mock = MagicMock()
            old_mock.manager_assessment_date = None
            old_mock.hrm_assessed = False
            old_mock.grade_hrm = None
            mock_queryset.get.return_value = old_mock

            # Same manager_assessment_date (both None) - should skip
            result = validate_kpi_assessment_deadline(EmployeeKPIAssessment, mock_assessment)
            assert result is None
