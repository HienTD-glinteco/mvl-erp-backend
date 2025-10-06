# audit_logging/tests/test_opensearch_client.py
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from ..opensearch_client import OpenSearchClient


@override_settings(
    OPENSEARCH_HOST="localhost",
    OPENSEARCH_PORT=9200,
    OPENSEARCH_USERNAME="",
    OPENSEARCH_PASSWORD="",
    OPENSEARCH_USE_SSL=False,
    OPENSEARCH_VERIFY_CERTS=False,
    OPENSEARCH_INDEX_PREFIX="test-audit-logs",
)
class TestOpenSearchClient(TestCase):
    """Test cases for OpenSearchClient."""

    def setUp(self):
        self.mock_opensearch = MagicMock()
        with patch("apps.audit_logging.opensearch_client.OpenSearch") as mock_os_class:
            mock_os_class.return_value = self.mock_opensearch
            self.client = OpenSearchClient()

    def test_get_index_name(self):
        """Test index name generation from timestamp."""
        timestamp = "2023-12-15T10:30:00Z"
        index_name = self.client._get_index_name(timestamp)
        self.assertEqual(index_name, "test-audit-logs-2023-12")

    def test_index_log_success(self):
        """Test successful log indexing."""
        self.mock_opensearch.indices.exists.return_value = True
        self.mock_opensearch.index.return_value = {"result": "created"}

        log_data = {
            "log_id": "test-123",
            "timestamp": "2023-12-15T10:30:00Z",
            "action": "test_action",
            "object_type": "test_object",
        }

        result = self.client.index_log(log_data)

        self.mock_opensearch.index.assert_called_once()
        self.assertEqual(result["result"], "created")

    def test_bulk_index_logs_success(self):
        """Test successful bulk indexing."""
        self.mock_opensearch.indices.exists.return_value = True
        self.mock_opensearch.bulk.return_value = {"errors": False, "items": []}

        logs = [
            {
                "log_id": "test-1",
                "timestamp": "2023-12-15T10:30:00Z",
                "action": "test_action_1",
            },
            {
                "log_id": "test-2",
                "timestamp": "2023-12-15T10:30:00Z",
                "action": "test_action_2",
            },
        ]

        result = self.client.bulk_index_logs(logs)

        self.mock_opensearch.bulk.assert_called_once()
        self.assertFalse(result["errors"])

    def test_search_logs_success(self):
        """Test successful log searching."""
        self.mock_opensearch.search.return_value = {
            "hits": {
                "total": {"value": 1},
                "hits": [
                    {
                        "_source": {
                            "log_id": "test-123",
                            "timestamp": "2023-12-15T10:30:00Z",
                            "action": "test_action",
                        }
                    }
                ],
            }
        }

        filters = {"action": "test_action"}
        result = self.client.search_logs(filters=filters)

        self.mock_opensearch.search.assert_called_once()
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["total"], 1)

    def test_build_search_query_with_filters(self):
        """Test search query building with various filters."""
        filters = {
            "from_date": "2023-12-01",
            "to_date": "2023-12-31",
            "action": "test_action",
            "search_term": "test query",
        }

        query = self.client._build_search_query(filters)

        self.assertIn("bool", query)
        self.assertIn("must", query["bool"])
        must_clauses = query["bool"]["must"]

        # Check for range queries
        range_clauses = [c for c in must_clauses if "range" in c]
        self.assertEqual(len(range_clauses), 2)  # from_date and to_date

        # Check for term query
        term_clauses = [c for c in must_clauses if "term" in c]
        self.assertEqual(len(term_clauses), 1)  # action

        # Check for multi_match query
        multi_match_clauses = [c for c in must_clauses if "multi_match" in c]
        self.assertEqual(len(multi_match_clauses), 1)  # search_term

    def test_get_log_by_id_success(self):
        """Test successful retrieval of a single log by ID."""
        self.mock_opensearch.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "log_id": "test-123",
                            "timestamp": "2023-12-15T10:30:00Z",
                            "action": "test_action",
                            "user_id": "1",
                            "object_type": "test_object",
                            "change_message": "Test change",
                            "ip_address": "192.168.1.1",
                        }
                    }
                ]
            }
        }

        result = self.client.get_log_by_id("test-123")

        self.mock_opensearch.search.assert_called_once()
        self.assertEqual(result["log_id"], "test-123")
        self.assertIn("change_message", result)
        self.assertIn("ip_address", result)

    def test_get_log_by_id_not_found(self):
        """Test retrieval of non-existent log."""
        from ..exceptions import AuditLogException

        self.mock_opensearch.search.return_value = {"hits": {"hits": []}}

        with self.assertRaises(AuditLogException) as context:
            self.client.get_log_by_id("nonexistent-id")

        self.assertIn("not found", str(context.exception))

    def test_search_logs_with_summary_fields(self):
        """Test search with summary fields only."""
        self.mock_opensearch.search.return_value = {
            "hits": {
                "total": {"value": 1},
                "hits": [
                    {
                        "_source": {
                            "log_id": "test-123",
                            "timestamp": "2023-12-15T10:30:00Z",
                            "action": "test_action",
                        }
                    }
                ],
            }
        }

        filters = {"action": "test_action"}
        result = self.client.search_logs(filters=filters, summary_fields_only=True)

        self.mock_opensearch.search.assert_called_once()
        # Verify that _source was included in the search body
        call_args = self.mock_opensearch.search.call_args
        search_body = call_args.kwargs["body"]
        self.assertIn("_source", search_body)
        self.assertEqual(len(search_body["_source"]), 9)  # 9 summary fields
        self.assertIn("log_id", search_body["_source"])
        self.assertIn("timestamp", search_body["_source"])
        self.assertIn("object_repr", search_body["_source"])


@override_settings(
    OPENSEARCH_HOST="localhost",
    OPENSEARCH_PORT=9200,
    OPENSEARCH_USERNAME="testuser",
    OPENSEARCH_PASSWORD="testpass",
    OPENSEARCH_USE_SSL=True,
    OPENSEARCH_VERIFY_CERTS=True,
    OPENSEARCH_INDEX_PREFIX="secure-audit-logs",
)
class TestOpenSearchClientWithAuth(TestCase):
    """Test OpenSearchClient with authentication."""

    @patch("apps.audit_logging.opensearch_client.OpenSearch")
    def test_client_creation_with_auth(self, mock_os_class):
        """Test that client is created with authentication when configured."""
        mock_opensearch = MagicMock()
        mock_os_class.return_value = mock_opensearch

        OpenSearchClient()

        # Verify OpenSearch was called with correct auth parameters
        mock_os_class.assert_called_once()
        call_args = mock_os_class.call_args

        self.assertIn("http_auth", call_args.kwargs)
        self.assertEqual(call_args.kwargs["http_auth"], ("testuser", "testpass"))
        self.assertTrue(call_args.kwargs["use_ssl"])
        self.assertTrue(call_args.kwargs["verify_certs"])
