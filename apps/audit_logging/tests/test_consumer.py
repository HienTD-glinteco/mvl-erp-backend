# audit_logging/tests/test_consumer.py
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from ..consumer import AuditLogConsumer


@override_settings(
    RABBITMQ_STREAM_HOST="localhost",
    RABBITMQ_STREAM_PORT=5552,
    RABBITMQ_STREAM_USER="guest",
    RABBITMQ_STREAM_PASSWORD="guest",
    RABBITMQ_STREAM_VHOST="/",
    RABBITMQ_STREAM_NAME="audit_logs",
    OPENSEARCH_HOST="localhost",
    OPENSEARCH_PORT=9200,
    OPENSEARCH_USERNAME="",
    OPENSEARCH_PASSWORD="",
    OPENSEARCH_USE_SSL=False,
    OPENSEARCH_VERIFY_CERTS=False,
    OPENSEARCH_INDEX_PREFIX="test-audit-logs",
)
class TestAuditLogConsumer(TestCase):
    """Test cases for AuditLogConsumer."""

    def setUp(self):
        self.consumer_name = "test_consumer"

    def test_consumer_initialization(self):
        """Test that consumer initializes correctly."""
        consumer = AuditLogConsumer(consumer_name=self.consumer_name)

        self.assertEqual(consumer.consumer_name, self.consumer_name)
        self.assertIsNotNone(consumer.opensearch_client)
        self.assertIsNone(consumer.rabbitmq_consumer)

    @patch("apps.audit_logging.consumer.get_opensearch_client")
    def test_consumer_initialization_with_mocked_opensearch(self, mock_get_client):
        """Test consumer initialization with mocked OpenSearch client."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        consumer = AuditLogConsumer(consumer_name=self.consumer_name)

        self.assertEqual(consumer.opensearch_client, mock_client)

    async def test_index_to_opensearch_success(self):
        """Test successful OpenSearch indexing."""
        consumer = AuditLogConsumer(consumer_name=self.consumer_name)

        # Mock the opensearch client
        consumer.opensearch_client = MagicMock()
        consumer.opensearch_client.index_log = MagicMock()

        log_data = {
            "log_id": "test-123",
            "timestamp": "2023-12-15T10:30:00Z",
            "action": "test_action",
        }

        await consumer._index_to_opensearch(log_data)

        # Verify index_log was called
        consumer.opensearch_client.index_log.assert_called_once_with(log_data)

    async def test_index_to_opensearch_with_retry(self):
        """Test OpenSearch indexing with retry logic."""
        from opensearchpy.exceptions import ConnectionError

        consumer = AuditLogConsumer(consumer_name=self.consumer_name)

        # Mock the opensearch client to fail twice then succeed
        consumer.opensearch_client = MagicMock()
        # Construct ConnectionError with (status_code, error, info) to match opensearch TransportError args
        consumer.opensearch_client.index_log = MagicMock(
            side_effect=[
                ConnectionError("N/A", "Connection failed", Exception("underlying")),
                ConnectionError("N/A", "Connection failed", Exception("underlying")),
                None,  # Success on third attempt
            ]
        )

        log_data = {
            "log_id": "test-123",
            "timestamp": "2023-12-15T10:30:00Z",
            "action": "test_action",
        }

        await consumer._index_to_opensearch(log_data)

        # Verify index_log was called 3 times (2 failures + 1 success)
        self.assertEqual(consumer.opensearch_client.index_log.call_count, 3)

    async def test_message_handler_success(self):
        """Test successful message handling."""
        consumer = AuditLogConsumer(consumer_name=self.consumer_name)

        # Mock opensearch client
        consumer.opensearch_client = MagicMock()
        consumer.opensearch_client.index_log = MagicMock()

        message = '{"log_id": "test-123", "timestamp": "2023-12-15T10:30:00Z", "action": "test_action"}'
        context = MagicMock()
        context.offset = 0

        await consumer._message_handler(message, context)

        # Verify OpenSearch indexing was attempted
        consumer.opensearch_client.index_log.assert_called_once()

    async def test_message_handler_invalid_json(self):
        """Test message handler with invalid JSON."""
        consumer = AuditLogConsumer(consumer_name=self.consumer_name)

        # Mock opensearch client
        consumer.opensearch_client = MagicMock()
        consumer.opensearch_client.index_log = MagicMock()

        message = "invalid json {{"
        context = MagicMock()
        context.offset = 0

        # Should not raise an exception
        await consumer._message_handler(message, context)

        # Verify OpenSearch indexing was NOT attempted
        consumer.opensearch_client.index_log.assert_not_called()
