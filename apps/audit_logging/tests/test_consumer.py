import json
from unittest.mock import AsyncMock, MagicMock, patch

from django.conf import settings
from django.test import TestCase, override_settings
from opensearchpy.exceptions import ConnectionError, OpenSearchException, RequestError, TransportError

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

        await consumer._index_to_opensearch(log_data, json.dumps(log_data), 100)

        # Verify index_log was called
        consumer.opensearch_client.index_log.assert_called_once_with(log_data)
        self.assertEqual(consumer.metrics.success_count, 1)

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

        await consumer._index_to_opensearch(log_data, json.dumps(log_data), 100)

        # Verify index_log was called 3 times (2 failures + 1 success)
        self.assertEqual(consumer.opensearch_client.index_log.call_count, 3)
        self.assertEqual(consumer.metrics.success_count, 1)
        self.assertEqual(consumer.metrics.error_types.get("network"), 2)

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

    def test_categorize_error(self):
        """Test error categorization logic."""
        consumer = AuditLogConsumer(consumer_name=self.consumer_name)

        # Validation error
        self.assertEqual(consumer._categorize_error(RequestError(400, "mapper_parsing_exception", {})), "validation")
        self.assertEqual(consumer._categorize_error(RequestError(400, "illegal_argument_exception", {})), "validation")

        # Generic request error
        self.assertEqual(consumer._categorize_error(RequestError(400, "some other error", {})), "request_error")

        # Network errors
        self.assertEqual(consumer._categorize_error(ConnectionError("N/A", "timeout", None)), "network")
        self.assertEqual(consumer._categorize_error(TransportError(500, "transport error", None)), "network")

        # Internal error
        self.assertEqual(consumer._categorize_error(OpenSearchException("internal")), "opensearch_internal")

        # Serialization
        self.assertEqual(consumer._categorize_error(json.JSONDecodeError("msg", "doc", 0)), "serialization")

        # Unknown
        self.assertEqual(consumer._categorize_error(ValueError("oops")), "unknown")

    @patch("asyncio.sleep", return_value=None)
    async def test_dlq_production(self, mock_sleep):
        """Test that failed messages are sent to DLQ."""
        consumer = AuditLogConsumer(consumer_name=self.consumer_name)
        consumer.opensearch_client = MagicMock()
        consumer.opensearch_client.index_log.side_effect = Exception("Final failure")

        # Mock DLQ producer
        mock_producer = AsyncMock()
        consumer.dlq_producer = mock_producer

        log_data = {"log_id": "dlq-test"}
        await consumer._index_to_opensearch(log_data, json.dumps(log_data), 100)

        # Verify metrics recorded final failure
        self.assertEqual(consumer.metrics.failure_count, 1)
        self.assertEqual(consumer.metrics.error_types.get("unknown"), 3)
        self.assertEqual(consumer.metrics.error_types.get("unknown_final_failure"), 1)

        # Verify DLQ send was called
        mock_producer.send.assert_called_once()
        sent_args = mock_producer.send.call_args[0]
        self.assertEqual(sent_args[0], consumer.DLQ_STREAM_NAME)
        dlq_msg = json.loads(sent_args[1].decode("utf-8"))
        self.assertEqual(dlq_msg["error_type"], "unknown")
        self.assertEqual(dlq_msg["offset"], 100)

    async def test_get_health_status(self):
        """Test health status reporting."""
        consumer = AuditLogConsumer(consumer_name=self.consumer_name)
        consumer.is_running = True
        consumer.current_offset = 500
        consumer.last_committed_offset = 400
        consumer.metrics.record_success(0.1)

        status = consumer.get_health_status()
        self.assertTrue(status["is_running"])
        self.assertEqual(status["current_offset"], 500)
        self.assertEqual(status["last_committed_offset"], 400)
        self.assertEqual(status["metrics"]["success"], 1)

    async def test_graceful_shutdown(self):
        """Test final offset commit during stop()."""
        consumer = AuditLogConsumer(consumer_name=self.consumer_name)
        mock_rabbitmq = AsyncMock()
        consumer.rabbitmq_consumer = mock_rabbitmq

        consumer.current_offset = 123
        consumer.last_committed_offset = 100

        await consumer.stop()

        # Verify final commit happened
        mock_rabbitmq.store_offset.assert_called_once_with(
            subscriber_name=self.consumer_name, stream=settings.RABBITMQ_STREAM_NAME, offset=123
        )
