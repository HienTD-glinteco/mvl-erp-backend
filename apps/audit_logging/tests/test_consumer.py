# audit_logging/tests/test_consumer.py
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from django.test import TestCase, override_settings

from ..consumer import AuditLogConsumer


@override_settings(
    RABBITMQ_STREAM_HOST="localhost",
    RABBITMQ_STREAM_PORT=5552,
    RABBITMQ_STREAM_USER="guest",
    RABBITMQ_STREAM_PASSWORD="guest",
    RABBITMQ_STREAM_VHOST="/",
    RABBITMQ_STREAM_NAME="audit_logs",
    AUDIT_LOG_BATCH_SIZE=1000,
    AUDIT_LOG_FLUSH_INTERVAL=60,
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
        self.batch_size = 1000
        self.consumer_name = "test_consumer"

    def test_consumer_initialization(self):
        """Test that consumer initializes correctly."""
        consumer = AuditLogConsumer(
            batch_size=self.batch_size,
            consumer_name=self.consumer_name,
        )

        self.assertEqual(consumer.batch_size, self.batch_size)
        self.assertEqual(consumer.consumer_name, self.consumer_name)
        self.assertEqual(consumer.log_batch, [])
        self.assertIsNotNone(consumer.opensearch_client)
        self.assertIsNone(consumer.rabbitmq_consumer)
        self.assertIsNone(consumer.flush_task)

    @patch("apps.audit_logging.consumer.get_opensearch_client")
    def test_consumer_initialization_with_mocked_opensearch(self, mock_get_client):
        """Test consumer initialization with mocked OpenSearch client."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        consumer = AuditLogConsumer(
            batch_size=self.batch_size,
            consumer_name=self.consumer_name,
        )

        self.assertEqual(consumer.opensearch_client, mock_client)

    @patch("apps.audit_logging.consumer.process_and_upload_batch")
    async def test_flush_batch_if_needed_force(self, mock_upload):
        """Test forced batch flushing."""
        consumer = AuditLogConsumer(
            batch_size=self.batch_size,
            consumer_name=self.consumer_name,
        )

        # Add some logs to the batch
        consumer.log_batch = [
            {"log_id": "test-1", "timestamp": "2023-12-15T10:30:00Z"},
            {"log_id": "test-2", "timestamp": "2023-12-15T10:31:00Z"},
        ]

        # Force flush
        await consumer.flush_batch_if_needed(force=True)

        # Verify upload was called and batch was cleared
        mock_upload.assert_called_once()
        self.assertEqual(len(consumer.log_batch), 0)

    @patch("apps.audit_logging.consumer.process_and_upload_batch")
    async def test_flush_batch_if_needed_size_threshold(self, mock_upload):
        """Test batch flushing when size threshold is reached."""
        consumer = AuditLogConsumer(
            batch_size=2,  # Small batch size for testing
            consumer_name=self.consumer_name,
        )

        # Add logs to exceed batch size
        consumer.log_batch = [
            {"log_id": "test-1", "timestamp": "2023-12-15T10:30:00Z"},
            {"log_id": "test-2", "timestamp": "2023-12-15T10:31:00Z"},
            {"log_id": "test-3", "timestamp": "2023-12-15T10:32:00Z"},
        ]

        await consumer.flush_batch_if_needed()

        # Verify upload was called and batch was cleared
        mock_upload.assert_called_once()
        self.assertEqual(len(consumer.log_batch), 0)

    @patch("apps.audit_logging.consumer.process_and_upload_batch")
    async def test_flush_batch_if_needed_no_flush_needed(self, mock_upload):
        """Test that batch is not flushed when conditions aren't met."""
        consumer = AuditLogConsumer(
            batch_size=1000,
            consumer_name=self.consumer_name,
        )

        # Add only a few logs (below threshold)
        consumer.log_batch = [
            {"log_id": "test-1", "timestamp": "2023-12-15T10:30:00Z"},
        ]

        await consumer.flush_batch_if_needed()

        # Verify upload was NOT called
        mock_upload.assert_not_called()
        self.assertEqual(len(consumer.log_batch), 1)

    async def test_index_to_opensearch_success(self):
        """Test successful OpenSearch indexing."""
        consumer = AuditLogConsumer(
            batch_size=self.batch_size,
            consumer_name=self.consumer_name,
        )

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

        consumer = AuditLogConsumer(
            batch_size=self.batch_size,
            consumer_name=self.consumer_name,
        )

        # Mock the opensearch client to fail twice then succeed
        consumer.opensearch_client = MagicMock()
        consumer.opensearch_client.index_log = MagicMock(
            side_effect=[
                ConnectionError("Connection failed"),
                ConnectionError("Connection failed"),
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
        consumer = AuditLogConsumer(
            batch_size=self.batch_size,
            consumer_name=self.consumer_name,
        )

        # Mock opensearch client
        consumer.opensearch_client = MagicMock()
        consumer.opensearch_client.index_log = MagicMock()

        message = '{"log_id": "test-123", "timestamp": "2023-12-15T10:30:00Z", "action": "test_action"}'
        context = MagicMock()
        context.offset = 0

        await consumer._message_handler(message, context)

        # Verify log was added to batch
        self.assertEqual(len(consumer.log_batch), 1)
        self.assertEqual(consumer.log_batch[0]["log_id"], "test-123")

        # Verify OpenSearch indexing was attempted
        consumer.opensearch_client.index_log.assert_called_once()

    async def test_message_handler_invalid_json(self):
        """Test message handler with invalid JSON."""
        consumer = AuditLogConsumer(
            batch_size=self.batch_size,
            consumer_name=self.consumer_name,
        )

        message = "invalid json {{"
        context = MagicMock()
        context.offset = 0

        # Should not raise an exception
        await consumer._message_handler(message, context)

        # Verify log was NOT added to batch
        self.assertEqual(len(consumer.log_batch), 0)
