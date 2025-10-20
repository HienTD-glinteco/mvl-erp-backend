"""
Tests for HistoryMixin functionality.
"""

from unittest.mock import MagicMock, patch

import pytest
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from libs import BaseModelViewSet


# Test fixtures - Mock Model and ViewSet
class MockModel:
    """Mock model for testing"""

    class _meta:
        model_name = "mock_model"
        verbose_name = "Mock Model"

    def __init__(self, pk=1):
        self.pk = pk
        self.id = pk


class TestHistoryViewSet(BaseModelViewSet):
    """Test viewset with HistoryMixin (inherited from BaseModelViewSet)"""

    class MockQuerySet:
        model = MockModel

    queryset = MockQuerySet()
    module = "Test Module"
    submodule = "History Testing"
    permission_prefix = "test_history"

    def get_object(self):
        """Override get_object to return a mock instance"""
        return MockModel(pk=123)


class HistoryMixinTestCase(TestCase):
    """Test HistoryMixin action"""

    def setUp(self):
        """Set up test fixtures"""
        self.factory = APIRequestFactory()
        self.viewset = TestHistoryViewSet()

    @patch("apps.audit_logging.api.serializers.AuditLogSearchSerializer")
    def test_history_action_exists(self, mock_serializer_class):
        """Test that history action is defined"""
        # Assert
        self.assertTrue(hasattr(self.viewset, "history"))
        self.assertTrue(callable(self.viewset.history))

    @patch("apps.audit_logging.api.serializers.AuditLogSearchSerializer")
    def test_history_action_returns_audit_logs(self, mock_serializer_class):
        """Test that history action returns audit logs for an object"""
        # Arrange
        mock_result = {
            "results": [
                {
                    "log_id": "abc123",
                    "timestamp": "2025-10-13T14:30:00Z",
                    "action": "CREATE",
                    "object_type": "mock_model",
                    "object_id": "123",
                }
            ],
            "total": 1,
            "page_size": 50,
            "from_offset": 0,
            "has_next": False,
        }

        # Create mock serializer instance
        mock_serializer = MagicMock()
        mock_serializer.is_valid.return_value = True
        mock_serializer.search.return_value = mock_result
        mock_serializer_class.return_value = mock_serializer

        # Create request
        request = self.factory.get("/test/123/history/")
        # Wrap with DRF to get query_params attribute
        from rest_framework.request import Request

        request = Request(request)
        self.viewset.request = request
        self.viewset.format_kwarg = None

        # Act
        response = self.viewset.history(request, pk=123)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, mock_result)

        # Verify serializer was called with correct parameters
        call_args = mock_serializer_class.call_args[1]["data"]
        self.assertEqual(call_args["object_type"], "mock_model")
        self.assertEqual(call_args["object_id"], "123")

    @patch("apps.audit_logging.api.serializers.AuditLogSearchSerializer")
    def test_history_action_with_filters(self, mock_serializer_class):
        """Test that history action supports query parameter filters"""
        # Arrange
        mock_serializer = MagicMock()
        mock_serializer.is_valid.return_value = True
        mock_serializer.search.return_value = {"results": [], "total": 0}
        mock_serializer_class.return_value = mock_serializer

        # Create request with query parameters
        request = self.factory.get(
            "/test/123/history/", {"from_date": "2025-01-01", "to_date": "2025-12-31", "action": "CHANGE"}
        )
        # Wrap with DRF to get query_params attribute
        from rest_framework.request import Request

        request = Request(request)
        self.viewset.request = request
        self.viewset.format_kwarg = None

        # Act
        response = self.viewset.history(request, pk=123)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify filters were passed to serializer
        call_args = mock_serializer_class.call_args[1]["data"]
        self.assertEqual(call_args["from_date"], "2025-01-01")
        self.assertEqual(call_args["to_date"], "2025-12-31")
        self.assertEqual(call_args["action"], "CHANGE")

    def test_history_action_object_not_found(self):
        """Test history action returns 404 when object doesn't exist"""
        # Arrange
        viewset = TestHistoryViewSet()
        viewset.get_object = MagicMock(side_effect=Exception("Not found"))

        request = self.factory.get("/test/999/history/")
        viewset.request = request
        viewset.format_kwarg = None

        # Act
        response = viewset.history(request, pk=999)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data)

    @patch("apps.audit_logging.api.serializers.AuditLogSearchSerializer")
    def test_history_action_validation_error(self, mock_serializer_class):
        """Test history action returns 400 on validation error"""
        # Arrange
        mock_serializer = MagicMock()
        mock_serializer.is_valid.return_value = False
        mock_serializer.errors = {"from_date": ["Invalid date format"]}
        mock_serializer_class.return_value = mock_serializer

        request = self.factory.get("/test/123/history/", {"from_date": "invalid"})
        # Wrap with DRF to get query_params attribute
        from rest_framework.request import Request

        request = Request(request)
        self.viewset.request = request
        self.viewset.format_kwarg = None

        # Act
        response = self.viewset.history(request, pk=123)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    @patch("apps.audit_logging.api.serializers.AuditLogSearchSerializer")
    def test_history_action_audit_exception(self, mock_serializer_class):
        """Test history action handles audit log exceptions"""
        # Arrange
        from apps.audit_logging.exceptions import AuditLogException

        mock_serializer = MagicMock()
        mock_serializer.is_valid.return_value = True
        mock_serializer.search.side_effect = AuditLogException("OpenSearch connection failed")
        mock_serializer_class.return_value = mock_serializer

        request = self.factory.get("/test/123/history/")
        # Wrap with DRF to get query_params attribute
        from rest_framework.request import Request

        request = Request(request)
        self.viewset.request = request
        self.viewset.format_kwarg = None

        # Act
        response = self.viewset.history(request, pk=123)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("error", response.data)
        self.assertIn("Failed to retrieve history", response.data["error"])


class HistoryMixinPermissionRegistrationTestCase(TestCase):
    """Test that HistoryMixin registers permissions correctly"""

    def test_history_action_is_detected_as_custom_action(self):
        """Test that history action is detected in custom actions"""
        # Act
        custom_actions = TestHistoryViewSet.get_custom_actions()

        # Assert
        self.assertIn("history", custom_actions)

    def test_history_permission_is_registered(self):
        """Test that history action generates a permission"""
        # Act
        permissions = TestHistoryViewSet.get_registered_permissions()

        # Assert
        codes = [p["code"] for p in permissions]
        self.assertIn("test_history.history", codes)

    def test_history_permission_metadata(self):
        """Test that history permission has correct metadata"""
        # Act
        permissions = TestHistoryViewSet.get_registered_permissions()
        history_perm = next(p for p in permissions if p["code"] == "test_history.history")

        # Assert
        self.assertEqual(history_perm["module"], "Test Module")
        self.assertEqual(history_perm["submodule"], "History Testing")
        self.assertIn("History", history_perm["name"])
        self.assertIn("Mock Model", history_perm["name"])


@pytest.mark.django_db
class HistoryMixinIntegrationTestCase(TestCase):
    """Integration tests for HistoryMixin with real models"""

    def test_history_mixin_works_with_base_model_viewset(self):
        """Test that HistoryMixin integrates properly with BaseModelViewSet"""
        # This test verifies that the mixin order is correct
        # HistoryMixin should be before BaseModelViewSet in the MRO

        # Act
        mro = [cls.__name__ for cls in BaseModelViewSet.__mro__]

        # Assert
        # HistoryMixin should come before ModelViewSet in the MRO
        history_index = mro.index("HistoryMixin")
        viewset_index = mro.index("ModelViewSet")
        self.assertLess(history_index, viewset_index, "HistoryMixin should come before ModelViewSet in MRO")
