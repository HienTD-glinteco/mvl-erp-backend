# audit_logging/consumer.py
import asyncio
import json
import logging

from django.conf import settings
from opensearchpy.exceptions import ConnectionError, TransportError
from rstream import Consumer as RStreamConsumer
from rstream.constants import ConsumerOffsetSpecification, OffsetType

from .opensearch_client import get_opensearch_client

logger = logging.getLogger(__name__)


class AuditLogConsumer:
    """
    Consumer for audit logs from RabbitMQ Stream.
    
    Handles:
    - Reading messages from RabbitMQ Stream
    - Indexing logs to OpenSearch for real-time search
    """

    def __init__(self, consumer_name: str):
        """
        Initialize the audit log consumer.

        Args:
            consumer_name: Name for RabbitMQ consumer (used for offset tracking)
        """
        self.consumer_name = consumer_name
        self.opensearch_client = get_opensearch_client()
        self.rabbitmq_consumer = None

    async def _index_to_opensearch(self, log_data: dict):
        """
        Index log data to OpenSearch with retry logic.

        Args:
            log_data: The log data to index
        """
        max_retries = 3
        retry_delay = 1  # Start with 1 second delay

        for attempt in range(max_retries):
            try:
                self.opensearch_client.index_log(log_data)
                logger.debug(f"Indexed log {log_data['log_id']} to OpenSearch")
                break  # Success, exit retry loop
            except (ConnectionError, TransportError) as e:
                # Network/connection issues - retry
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Failed to index log to OpenSearch (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {retry_delay} seconds..."
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error(
                        f"Failed to index log to OpenSearch after {max_retries} attempts: {e}",
                        exc_info=True,
                    )
            except Exception as e:
                # Other errors - log and continue without retry
                logger.error(
                    f"Failed to index log to OpenSearch: {e}", exc_info=True
                )
                break

    async def _message_handler(self, message, context):
        """
        Handle incoming messages from RabbitMQ Stream.

        Args:
            message: The message content
            context: Message context including offset
        """
        try:
            log_data = json.loads(message)

            # Index to OpenSearch for real-time search with retry logic
            await self._index_to_opensearch(log_data)

        except json.JSONDecodeError:
            logger.warning(
                f"Skipping message with offset {context.offset} due to JSON decode error."
            )
            return

    async def start(self):
        """Start the consumer and begin processing messages."""
        # Initialize RabbitMQ consumer
        self.rabbitmq_consumer = RStreamConsumer(
            host=settings.RABBITMQ_STREAM_HOST,
            port=settings.RABBITMQ_STREAM_PORT,
            username=settings.RABBITMQ_STREAM_USER,
            password=settings.RABBITMQ_STREAM_PASSWORD,
            vhost=settings.RABBITMQ_STREAM_VHOST,
        )

        try:
            await self.rabbitmq_consumer.start()
            # Use RabbitMQ's server-side offset tracking
            # The consumer name is used for tracking position in the stream
            await self.rabbitmq_consumer.subscribe(
                stream=settings.RABBITMQ_STREAM_NAME,
                callback=self._message_handler,
                offset_specification=ConsumerOffsetSpecification(
                    OffsetType.FIRST, None
                ),
                consumer_name=self.consumer_name,
            )

            logger.info(f"Consumer {self.consumer_name} started successfully")

            # Run indefinitely
            await self.rabbitmq_consumer.run()

        except KeyboardInterrupt:
            logger.info("Shutting down consumer gracefully...")
            await self.stop()

    async def stop(self):
        """Stop the consumer and perform cleanup."""
        # Close RabbitMQ consumer
        if self.rabbitmq_consumer:
            await self.rabbitmq_consumer.close()

        logger.info("Consumer stopped successfully")
