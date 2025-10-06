# audit_logging/tests/test_api_views.py
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from ..exceptions import AuditLogException

User = get_user_model()


class TestAuditLogViewSet(TestCase):
    """Test cases for audit log ViewSet."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @patch("apps.audit_logging.api.serializers.get_opensearch_client")
    def test_search_audit_logs_success(self, mock_get_client):
        """Test successful audit log search."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.search_logs.return_value = {
            "items": [
                {
                    "log_id": "test-123",
                    "timestamp": "2023-12-15T10:30:00Z",
                    "action": "test_action",
                    "user_id": "1",
                    "object_type": "test_object",
                }
            ],
            "total": 1,
            "next_offset": None,
            "has_next": False,
        }

        url = "/api/audit-logs/search/"
        response = self.client.get(url, {"action": "test_action", "page_size": "10", "from_offset": "0"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        data = response_data["data"]
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["total"], 1)

        # Verify OpenSearch client was called with correct parameters including summary_fields_only
        mock_client.search_logs.assert_called_once_with(
            filters={"action": "test_action"},
            page_size=10,
            from_offset=0,
            sort_order="desc",
            summary_fields_only=True,
        )

    @patch("apps.audit_logging.api.serializers.get_opensearch_client")
    def test_search_audit_logs_with_filters(self, mock_get_client):
        """Test audit log search with multiple filters."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.search_logs.return_value = {
            "items": [],
            "total": 0,
            "next_offset": None,
            "has_next": False,
        }

        url = "/api/audit-logs/search/"
        response = self.client.get(
            url,
            {
                "from_date": "2023-12-01",
                "to_date": "2023-12-31",
                "user_id": "123",
                "search_term": "test query",
                "page_size": "25",
                "sort_order": "asc",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify filters were passed correctly
        mock_client.search_logs.assert_called_once()
        call_kwargs = mock_client.search_logs.call_args.kwargs
        self.assertEqual(call_kwargs["page_size"], 25)
        self.assertEqual(call_kwargs["sort_order"], "asc")
        self.assertTrue(call_kwargs["summary_fields_only"])
        self.assertIn("user_id", call_kwargs["filters"])
        self.assertIn("search_term", call_kwargs["filters"])

    def test_search_audit_logs_invalid_sort_order(self):
        """Test search with invalid sort order."""
        url = "/api/audit-logs/search/"
        response = self.client.get(url, {"sort_order": "invalid"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = response.json()
        self.assertFalse(response_data["success"])
        self.assertIsNotNone(response_data["error"])

    def test_search_audit_logs_invalid_page_size(self):
        """Test search with invalid page size."""
        url = "/api/audit-logs/search/"
        response = self.client.get(url, {"page_size": "invalid"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("apps.audit_logging.api.serializers.get_opensearch_client")
    def test_search_audit_logs_opensearch_exception(self, mock_get_client):
        """Test search when OpenSearch raises an exception."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.search_logs.side_effect = AuditLogException("OpenSearch error")

        url = "/api/audit-logs/search/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        response_data = response.json()
        self.assertFalse(response_data["success"])
        self.assertIn("Failed to search audit logs", str(response_data["error"]))

    def test_search_audit_logs_unauthenticated(self):
        """Test that unauthenticated requests are rejected."""
        unauthenticated_client = APIClient()
        url = "/api/audit-logs/search/"
        response = unauthenticated_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_page_size_limit(self):
        """Test that page size over the limit is rejected."""
        url = "/api/audit-logs/search/"
        response = self.client.get(url, {"page_size": "200"})  # Over the limit

        # Should return 400 because serializer validates max_value=100
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = response.json()
        self.assertFalse(response_data["success"])
        self.assertIsNotNone(response_data["error"])

    @patch("apps.audit_logging.api.views.get_opensearch_client")
    def test_detail_audit_log_success(self, mock_get_client):
        """Test successful retrieval of a specific audit log."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.get_log_by_id.return_value = {
            "log_id": "test-123",
            "timestamp": "2023-12-15T10:30:00Z",
            "user_id": "1",
            "username": "testuser",
            "action": "CREATE",
            "object_type": "Customer",
            "object_id": "456",
            "object_repr": "John Smith",
            "change_message": "Created new customer",
            "ip_address": "192.168.1.1",
            "user_agent": "Mozilla/5.0...",
            "session_key": "session_key_here",
        }

        url = "/api/audit-logs/detail/test-123/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        data = response_data["data"]
        self.assertEqual(data["log_id"], "test-123")
        self.assertEqual(data["action"], "CREATE")
        self.assertIn("change_message", data)
        self.assertIn("ip_address", data)
        self.assertIn("user_agent", data)
        self.assertIn("session_key", data)

        # Verify OpenSearch client was called with correct log_id
        mock_client.get_log_by_id.assert_called_once_with("test-123")

    @patch("apps.audit_logging.api.views.get_opensearch_client")
    def test_detail_audit_log_not_found(self, mock_get_client):
        """Test retrieval of non-existent audit log."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.get_log_by_id.side_effect = AuditLogException("Log with id test-999 not found")

        url = "/api/audit-logs/detail/test-999/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        response_data = response.json()
        self.assertFalse(response_data["success"])
        self.assertIn("not found", str(response_data["error"]))

    @patch("apps.audit_logging.api.views.get_opensearch_client")
    def test_detail_audit_log_opensearch_exception(self, mock_get_client):
        """Test detail when OpenSearch raises an exception."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.get_log_by_id.side_effect = AuditLogException("OpenSearch error")

        url = "/api/audit-logs/detail/test-123/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        response_data = response.json()
        self.assertFalse(response_data["success"])
        self.assertIn("Failed to retrieve audit log", str(response_data["error"]))

    def test_detail_audit_log_unauthenticated(self):
        """Test that unauthenticated detail requests are rejected."""
        unauthenticated_client = APIClient()
        url = "/api/audit-logs/detail/test-123/"
        response = unauthenticated_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("apps.audit_logging.api.serializers.get_opensearch_client")
    def test_search_with_from_date_to_date(self, mock_get_client):
        """Test search with from_date and to_date parameters."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.search_logs.return_value = {
            "items": [],
            "total": 0,
            "next_offset": None,
            "has_next": False,
        }

        url = "/api/audit-logs/search/"
        response = self.client.get(
            url,
            {
                "from_date": "2023-12-01",
                "to_date": "2023-12-31",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify filters were passed correctly with from_date/to_date
        mock_client.search_logs.assert_called_once()
        call_kwargs = mock_client.search_logs.call_args.kwargs
        self.assertIn("from_date", call_kwargs["filters"])
        self.assertIn("to_date", call_kwargs["filters"])

    @patch("apps.audit_logging.api.views.get_opensearch_client")
    def test_detail_includes_new_fields(self, mock_get_client):
        """Test that detail endpoint includes full_name and HR fields."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.get_log_by_id.return_value = {
            "log_id": "test-123",
            "timestamp": "2023-12-15T10:30:00Z",
            "user_id": "1",
            "username": "testuser",
            "full_name": "Test User",
            "action": "CREATE",
            "object_type": "Customer",
            "object_id": "456",
            "object_repr": "John Smith",
            "change_message": "Created new customer",
            "ip_address": "192.168.1.1",
            "user_agent": "Mozilla/5.0...",
            "session_key": "session_key_here",
        }

        url = "/api/audit-logs/detail/test-123/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        data = response_data["data"]
        self.assertEqual(data["full_name"], "Test User")

    @patch("apps.audit_logging.api.serializers.get_opensearch_client")
    def test_search_default_sort_order_desc(self, mock_get_client):
        """Test that default sort order is descending (newest first)."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.search_logs.return_value = {
            "items": [],
            "total": 0,
            "next_offset": None,
            "has_next": False,
        }

        url = "/api/audit-logs/search/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify default sort order is desc
        call_kwargs = mock_client.search_logs.call_args.kwargs
        self.assertEqual(call_kwargs["sort_order"], "desc")
