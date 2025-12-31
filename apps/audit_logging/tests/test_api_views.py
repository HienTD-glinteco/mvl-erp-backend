# audit_logging/tests/test_api_views.py
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from ..exceptions import AuditLogException

User = get_user_model()


class TestAuditLogSerializer(TestCase):
    """Test cases for AuditLogSerializer and ChangeMessageField."""

    def test_change_message_field_with_string(self):
        """Test serialization of change_message with string value."""
        from apps.audit_logging.api.serializers import AuditLogSerializer

        data = {
            "log_id": "test-123",
            "timestamp": "2023-12-15T10:30:00Z",
            "change_message": "Created new object",
        }
        serializer = AuditLogSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["change_message"], "Created new object")

    def test_change_message_field_with_object(self):
        """Test serialization of change_message with object value."""
        from apps.audit_logging.api.serializers import AuditLogSerializer

        change_message_obj = {
            "headers": ["field", "old_value", "new_value"],
            "rows": [
                {"field": "Phone number", "old_value": "0987654321", "new_value": "1234567890"},
                {"field": "Note", "old_value": "string", "new_value": "new new"},
            ],
        }
        data = {
            "log_id": "test-456",
            "timestamp": "2023-12-15T10:30:00Z",
            "change_message": change_message_obj,
        }
        serializer = AuditLogSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["change_message"], change_message_obj)

    def test_change_message_field_with_null(self):
        """Test serialization of change_message with null value."""
        from apps.audit_logging.api.serializers import AuditLogSerializer

        data = {
            "log_id": "test-789",
            "timestamp": "2023-12-15T10:30:00Z",
            "change_message": None,
        }
        serializer = AuditLogSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertIsNone(serializer.validated_data["change_message"])

    def test_change_message_field_with_array_values(self):
        """Test serialization of change_message with array values in rows."""
        from apps.audit_logging.api.serializers import AuditLogSerializer

        change_message_obj = {
            "headers": ["field", "old_value", "new_value"],
            "rows": [
                {
                    "field": "Certificates",
                    "old_value": ["old_cert.jpg"],
                    "new_value": ["cert1.jpg", "cert2.jpg"],
                }
            ],
        }
        data = {
            "log_id": "test-999",
            "timestamp": "2023-12-15T10:30:00Z",
            "change_message": change_message_obj,
        }
        serializer = AuditLogSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["change_message"], change_message_obj)


class TestAuditLogViewSet(TestCase):
    """Test cases for audit log ViewSet."""

    def setUp(self):
        # Changed to superuser to bypass RoleBasedPermission for API tests
        self.user = User.objects.create_superuser(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @patch("apps.audit_logging.api.serializers.get_opensearch_client")
    def test_search_audit_logs_success(self, mock_get_client):
        """Test successful audit log search."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.search_logs.return_value = {
            "results": [
                {
                    "log_id": "test-123",
                    "timestamp": "2023-12-15T10:30:00Z",
                    "action": "test_action",
                    "user_id": "1",
                    "employee_code": "EMP001",
                    "object_type": "test_object",
                }
            ],
            "count": 1,
            "next": None,
            "previous": None,
        }

        url = "/api/audit-logs/search/"
        response = self.client.get(url, {"actions": "test_action", "page_size": "10", "page": "1"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        data = response_data["data"]
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["count"], 1)
        # Verify employee_code is in the response
        self.assertEqual(data["results"][0]["employee_code"], "EMP001")

        # Verify OpenSearch client was called with correct parameters including summary_fields_only
        mock_client.search_logs.assert_called_once_with(
            filters={"action": ["test_action"]},
            page_size=10,
            page=1,
            sort_order="desc",
            summary_fields_only=True,
        )

    @patch("apps.audit_logging.api.serializers.get_opensearch_client")
    def test_search_audit_logs_with_filters(self, mock_get_client):
        """Test audit log search with multiple filters."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.search_logs.return_value = {
            "results": [
                {
                    "log_id": "test-filter-123",
                    "timestamp": "2023-12-15T10:30:00Z",
                    "user_id": "123",
                    "employee_code": "EMP001",
                    "action": "test_action",
                    "object_type": "test_object",
                }
            ],
            "count": 1,
            "next": None,
            "previous": None,
        }

        url = "/api/audit-logs/search/"
        response = self.client.get(
            url,
            {
                "from_date": "2023-12-01",
                "to_date": "2023-12-31",
                "user_id": "123",
                "employee_code": "EMP001",
                "search_term": "test query",
                "page_size": "25",
                "sort_order": "asc",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify employee_code is in the response
        response_data = response.json()
        data = response_data["data"]
        if data["results"]:
            self.assertEqual(data["results"][0]["employee_code"], "EMP001")

        # Verify filters were passed correctly
        mock_client.search_logs.assert_called_once()
        call_kwargs = mock_client.search_logs.call_args.kwargs
        self.assertEqual(call_kwargs["page_size"], 25)
        self.assertEqual(call_kwargs["sort_order"], "asc")
        self.assertTrue(call_kwargs["summary_fields_only"])
        self.assertIn("user_id", call_kwargs["filters"])
        self.assertIn("employee_code", call_kwargs["filters"])
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
            "employee_code": "EMP001",
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
        self.assertEqual(data["employee_code"], "EMP001")
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

    @patch("apps.audit_logging.api.views.get_opensearch_client")
    def test_detail_audit_log_with_dict_change_message(self, mock_get_client):
        """Test retrieval of audit log with dict change_message (structured format)."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.get_log_by_id.return_value = {
            "log_id": "test-456",
            "timestamp": "2023-12-15T10:30:00Z",
            "user_id": "1",
            "username": "testuser",
            "employee_code": "EMP001",
            "action": "CHANGE",
            "object_type": "Employee",
            "object_id": "789",
            "object_repr": "Jane Doe",
            "change_message": {
                "headers": ["field", "old_value", "new_value"],
                "rows": [
                    {"field": "Phone number", "old_value": "0987654321", "new_value": "1234567890"},
                    {"field": "Note", "old_value": "string", "new_value": "new new"},
                ],
            },
            "ip_address": "192.168.1.1",
        }

        url = "/api/audit-logs/detail/test-456/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        data = response_data["data"]
        self.assertEqual(data["log_id"], "test-456")
        self.assertEqual(data["action"], "CHANGE")
        # Verify change_message is a dict
        self.assertIsInstance(data["change_message"], dict)
        self.assertIn("headers", data["change_message"])
        self.assertIn("rows", data["change_message"])
        self.assertEqual(len(data["change_message"]["rows"]), 2)
        self.assertEqual(data["change_message"]["headers"], ["field", "old_value", "new_value"])

    @patch("apps.audit_logging.api.views.get_opensearch_client")
    def test_detail_audit_log_with_string_change_message(self, mock_get_client):
        """Test retrieval of audit log with string change_message (legacy format)."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.get_log_by_id.return_value = {
            "log_id": "test-789",
            "timestamp": "2023-12-15T10:30:00Z",
            "user_id": "1",
            "username": "testuser",
            "action": "DELETE",
            "object_type": "Customer",
            "object_id": "123",
            "object_repr": "Test Customer",
            "change_message": "Deleted object",
        }

        url = "/api/audit-logs/detail/test-789/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        data = response_data["data"]
        self.assertEqual(data["log_id"], "test-789")
        # Verify change_message is a string
        self.assertIsInstance(data["change_message"], str)
        self.assertEqual(data["change_message"], "Deleted object")

    @patch("apps.audit_logging.api.serializers.get_opensearch_client")
    def test_search_with_from_date_to_date(self, mock_get_client):
        """Test search with from_date and to_date parameters."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.search_logs.return_value = {
            "results": [],
            "count": 0,
            "next": None,
            "previous": None,
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
        """Test that detail endpoint includes full_name, employee_code and HR fields."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.get_log_by_id.return_value = {
            "log_id": "test-123",
            "timestamp": "2023-12-15T10:30:00Z",
            "user_id": "1",
            "username": "testuser",
            "employee_code": "EMP002",
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
        self.assertEqual(data["employee_code"], "EMP002")

    @patch("apps.audit_logging.api.serializers.get_opensearch_client")
    def test_search_default_sort_order_desc(self, mock_get_client):
        """Test that default sort order is descending (newest first)."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.search_logs.return_value = {
            "results": [],
            "count": 0,
            "next": None,
            "previous": None,
        }

        url = "/api/audit-logs/search/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify default sort order is desc
        call_kwargs = mock_client.search_logs.call_args.kwargs
        self.assertEqual(call_kwargs["sort_order"], "desc")

    @patch("apps.audit_logging.api.serializers.get_opensearch_client")
    def test_search_audit_logs_with_employee_code(self, mock_get_client):
        """Test audit log search filtered by employee code."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.search_logs.return_value = {
            "results": [
                {
                    "log_id": "test-456",
                    "timestamp": "2023-12-15T10:30:00Z",
                    "user_id": "1",
                    "username": "testuser",
                    "employee_code": "EMP001",
                    "action": "CREATE",
                    "object_type": "test_object",
                }
            ],
            "count": 1,
            "next": None,
            "previous": False,
        }

        url = "/api/audit-logs/search/"
        response = self.client.get(url, {"employee_code": "EMP001"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify employee_code filter was passed correctly
        mock_client.search_logs.assert_called_once()
        call_kwargs = mock_client.search_logs.call_args.kwargs
        self.assertIn("employee_code", call_kwargs["filters"])
        self.assertEqual(call_kwargs["filters"]["employee_code"], "EMP001")

    @patch("apps.audit_logging.api.serializers.get_opensearch_client")
    def test_search_audit_logs_with_multiple_actions(self, mock_get_client):
        """Test audit log search with multiple actions (?actions=CREATE&actions=UPDATE)."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.search_logs.return_value = {
            "results": [
                {
                    "log_id": "test-123",
                    "timestamp": "2023-12-15T10:30:00Z",
                    "user_id": "1",
                    "username": "testuser",
                    "action": "CREATE",
                    "object_type": "User",
                },
                {
                    "log_id": "test-456",
                    "timestamp": "2023-12-15T10:35:00Z",
                    "user_id": "1",
                    "username": "testuser",
                    "action": "UPDATE",
                    "object_type": "User",
                },
            ],
            "count": 2,
            "next": None,
            "previous": None,
        }

        url = "/api/audit-logs/search/"
        # Pass list to send multiple values: ?actions=CREATE&actions=UPDATE
        response = self.client.get(url, {"actions": ["CREATE", "UPDATE"]})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["data"]["count"], 2)

        # Verify action filter was passed as a list
        mock_client.search_logs.assert_called_once()
        call_kwargs = mock_client.search_logs.call_args.kwargs
        self.assertIn("action", call_kwargs["filters"])
        self.assertEqual(call_kwargs["filters"]["action"], ["CREATE", "UPDATE"])

    @patch("apps.audit_logging.api.serializers.get_opensearch_client")
    def test_search_audit_logs_with_multiple_object_types(self, mock_get_client):
        """Test audit log search with multiple object_types (?object_types=User&object_types=Role)."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.search_logs.return_value = {
            "results": [
                {
                    "log_id": "test-123",
                    "timestamp": "2023-12-15T10:30:00Z",
                    "user_id": "1",
                    "username": "testuser",
                    "action": "CREATE",
                    "object_type": "User",
                },
                {
                    "log_id": "test-456",
                    "timestamp": "2023-12-15T10:35:00Z",
                    "user_id": "1",
                    "username": "testuser",
                    "action": "CREATE",
                    "object_type": "Role",
                },
            ],
            "count": 2,
            "next": None,
            "previous": None,
        }

        url = "/api/audit-logs/search/"
        # Pass list to send multiple values: ?object_types=User&object_types=Role
        response = self.client.get(url, {"object_types": ["User", "Role"]})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["data"]["count"], 2)

        # Verify object_type filter was passed as a list
        mock_client.search_logs.assert_called_once()
        call_kwargs = mock_client.search_logs.call_args.kwargs
        self.assertIn("object_type", call_kwargs["filters"])
        self.assertEqual(call_kwargs["filters"]["object_type"], ["User", "Role"])

    @patch("apps.audit_logging.api.serializers.get_opensearch_client")
    def test_search_audit_logs_with_single_action(self, mock_get_client):
        """Test that single action is passed as list."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.search_logs.return_value = {
            "results": [],
            "count": 0,
            "next": None,
            "previous": None,
        }

        url = "/api/audit-logs/search/"
        response = self.client.get(url, {"actions": "CREATE"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify action filter is a list even when single value
        mock_client.search_logs.assert_called_once()
        call_kwargs = mock_client.search_logs.call_args.kwargs
        self.assertIn("action", call_kwargs["filters"])
        self.assertEqual(call_kwargs["filters"]["action"], ["CREATE"])

    @patch("apps.audit_logging.api.serializers.get_opensearch_client")
    def test_search_audit_logs_with_single_object_type(self, mock_get_client):
        """Test that single object_type is passed as list."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.search_logs.return_value = {
            "results": [],
            "count": 0,
            "next": None,
            "previous": None,
        }

        url = "/api/audit-logs/search/"
        response = self.client.get(url, {"object_types": "User"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify object_type filter is a list even when single value
        mock_client.search_logs.assert_called_once()
        call_kwargs = mock_client.search_logs.call_args.kwargs
        self.assertIn("object_type", call_kwargs["filters"])
        self.assertEqual(call_kwargs["filters"]["object_type"], ["User"])
