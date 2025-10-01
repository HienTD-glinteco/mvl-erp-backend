# audit_logging/consumer.py
import asyncio
import json
import logging
import time

from django.conf import settings
from opensearchpy.exceptions import ConnectionError, TransportError
from rstream import Consumer as RStreamConsumer
from rstream.constants import ConsumerOffsetSpecification, OffsetType

from .opensearch_client import get_opensearch_client
from .s3_uploader import process_and_upload_batch

logger = logging.getLogger(__name__)


class AuditLogConsumer:
    """
    Consumer for audit logs from RabbitMQ Stream.
    
    Handles:
    - Reading messages from RabbitMQ Stream
    - Indexing logs to OpenSearch for real-time search
    - Batching and uploading logs to S3 for archival
    - Periodic flushing based on time interval
    """

    def __init__(self, batch_size: int, consumer_name: str):
        """
        Initialize the audit log consumer.

        Args:
            batch_size: Maximum number of logs to batch before flushing to S3
            consumer_name: Name for RabbitMQ consumer (used for offset tracking)
        """
        self.batch_size = batch_size
        self.consumer_name = consumer_name
        self.log_batch = []
        self.last_flush_time = time.time()
        self.flush_lock = asyncio.Lock()
        self.opensearch_client = get_opensearch_client()
        self.rabbitmq_consumer = None
        self.flush_task = None

    async def flush_batch_if_needed(self, force: bool = False):
        """
        Flush the log batch to S3 if conditions are met.

        Args:
            force: If True, flush regardless of batch size or time
        """
        async with self.flush_lock:
            current_time = time.time()
            time_since_last_flush = current_time - self.last_flush_time

            should_flush = force or len(self.log_batch) >= self.batch_size or (
                self.log_batch
                and time_since_last_flush >= settings.AUDIT_LOG_FLUSH_INTERVAL
            )

            if should_flush and self.log_batch:
                logger.info(f"Uploading batch of {len(self.log_batch)} logs to S3.")
                try:
                    process_and_upload_batch(list(self.log_batch))
                    self.log_batch.clear()
                    self.last_flush_time = current_time
                except Exception as e:
                    logger.error(f"Failed to upload batch to S3: {e}", exc_info=True)
                    # Keep logs in batch for retry on next flush

    async def _periodic_flush(self):
        """Periodically flush logs to S3 based on time interval."""
        while True:
            try:
                await asyncio.sleep(settings.AUDIT_LOG_FLUSH_INTERVAL)
                await self.flush_batch_if_needed()
            except asyncio.CancelledError:
                logger.info("Periodic flush task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in periodic flush: {e}", exc_info=True)

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

            # Add to batch for S3 upload first (before OpenSearch indexing)
            async with self.flush_lock:
                self.log_batch.append(log_data)

            # Index to OpenSearch for real-time search with retry logic
            # This happens after adding to batch so S3 archival continues even if indexing fails
            await self._index_to_opensearch(log_data)

        except json.JSONDecodeError:
            logger.warning(
                f"Skipping message with offset {context.offset} due to JSON decode error."
            )
            return

        # Check if batch should be flushed (based on size)
        await self.flush_batch_if_needed()

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

        # Start periodic flush task
        self.flush_task = asyncio.create_task(self._periodic_flush())

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
        # Cancel periodic flush task
        if self.flush_task and not self.flush_task.done():
            self.flush_task.cancel()
            try:
                await self.flush_task
            except asyncio.CancelledError:
                pass

        # Upload any remaining logs in the batch before shutting down
        await self.flush_batch_if_needed(force=True)

        # Close RabbitMQ consumer
        if self.rabbitmq_consumer:
            await self.rabbitmq_consumer.close()

        logger.info("Consumer stopped successfully")
