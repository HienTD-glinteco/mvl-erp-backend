import asyncio
import json
import logging
import signal
import time
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.utils import timezone
from opensearchpy.exceptions import ConnectionError, OpenSearchException, RequestError, TransportError
from rstream import Consumer as RStreamConsumer, Producer as RStreamProducer
from rstream.constants import ConsumerOffsetSpecification, OffsetType

from .opensearch_client import get_opensearch_client

logger = logging.getLogger(__name__)


class ConsumerMetrics:
    """Track performance and error metrics for the audit log consumer."""

    def __init__(self):
        self.start_time = time.time()
        self.processed_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.dlq_count = 0
        self.offset_commits = 0
        self.error_types: Dict[str, int] = {}
        self.latencies: List[float] = []
        self.MAX_LATENCY_HISTORY = 1000

    def record_success(self, latency: float):
        self.processed_count += 1
        self.success_count += 1
        self.latencies.append(latency)
        if len(self.latencies) > self.MAX_LATENCY_HISTORY:
            self.latencies.pop(0)

    def record_failure(self, error_type: str):
        self.processed_count += 1
        self.failure_count += 1
        self.error_types[error_type] = self.error_types.get(error_type, 0) + 1

    def record_transient_error(self, error_type: str):
        self.error_types[error_type] = self.error_types.get(error_type, 0) + 1

    def record_dlq(self):
        self.dlq_count += 1

    def record_commit(self):
        self.offset_commits += 1

    def get_stats(self) -> Dict[str, Any]:
        uptime = time.time() - self.start_time
        avg_latency = sum(self.latencies) / len(self.latencies) if self.latencies else 0

        return {
            "uptime_seconds": int(uptime),
            "processed": self.processed_count,
            "success": self.success_count,
            "failed": self.failure_count,
            "sent_to_dlq": self.dlq_count,
            "offset_commits": self.offset_commits,
            "error_distribution": self.error_types,
            "avg_latency_ms": round(avg_latency * 1000, 2),
            "throughput_msg_per_sec": round(self.processed_count / uptime, 2) if uptime > 0 else 0,
        }

    def log_summary(self):
        stats = self.get_stats()
        logger.info(f"Consumer Stats Summary: {json.dumps(stats, indent=2)}")


class AuditLogConsumer:
    """
    Consumer for audit logs from RabbitMQ Stream.

    Handles:
    - Reading messages from RabbitMQ Stream
    - Indexing logs to OpenSearch for real-time search
    """

    rabbitmq_consumer: Optional[RStreamConsumer]
    dlq_producer: Optional[RStreamProducer]

    def __init__(self, consumer_name: str):
        """
        Initialize the audit log consumer.

        Args:
            consumer_name: Name for RabbitMQ consumer (used for offset tracking)
        """
        self.consumer_name = consumer_name
        self.opensearch_client = get_opensearch_client()
        self.rabbitmq_consumer = None
        self.dlq_producer = None
        self.is_running = False

        # Metrics and tracking
        self.metrics = ConsumerMetrics()
        self.last_committed_offset = -1
        self.current_offset = -1

        # Configuration
        self.BATCH_SIZE = getattr(settings, "AUDIT_LOG_CONSUMER_BATCH_SIZE", 100)
        self.STATS_INTERVAL = getattr(settings, "AUDIT_LOG_CONSUMER_STATS_INTERVAL", 1000)
        self.DLQ_STREAM_NAME = getattr(settings, "AUDIT_LOG_DLQ_NAME", f"{settings.RABBITMQ_STREAM_NAME}_dlq")

    def _categorize_error(self, e: Exception) -> str:
        """Categorize OpenSearch and other errors."""
        if isinstance(e, RequestError):
            # Check for mapping conflicts or validation errors
            error_reason = str(e)
            if "mapper_parsing_exception" in error_reason or "illegal_argument_exception" in error_reason:
                return "validation"
            return "request_error"

        if isinstance(e, (ConnectionError, TransportError)):
            return "network"

        if isinstance(e, OpenSearchException):
            return "opensearch_internal"

        if isinstance(e, json.JSONDecodeError):
            return "serialization"

        return "unknown"

    async def _send_to_dlq(self, message: str, error: Exception, offset: int):
        """Send failed message to Dead Letter Queue stream."""
        self.metrics.record_dlq()
        try:
            error_type = self._categorize_error(error)
            dlq_message = {
                "original_message": json.loads(message) if error_type != "serialization" else message,
                "error": str(error),
                "error_type": error_type,
                "offset": offset,
                "failed_at": timezone.now().isoformat(),
                "consumer_name": self.consumer_name,
            }

            # Lazily initialize DLQ producer
            if not self.dlq_producer:
                dlq_producer = RStreamProducer(
                    host=settings.RABBITMQ_STREAM_HOST,
                    port=settings.RABBITMQ_STREAM_PORT,
                    username=settings.RABBITMQ_STREAM_USER,
                    password=settings.RABBITMQ_STREAM_PASSWORD,
                    vhost=settings.RABBITMQ_STREAM_VHOST,
                )
                self.dlq_producer = dlq_producer
                await dlq_producer.start()
                await dlq_producer.create_stream(self.DLQ_STREAM_NAME, exists_ok=True)

            if self.dlq_producer:
                await self.dlq_producer.send(self.DLQ_STREAM_NAME, json.dumps(dlq_message).encode("utf-8"))

            logger.warning(f"Message with offset {offset} moved to DLQ: {self.DLQ_STREAM_NAME}")
        except Exception as dlq_err:
            logger.critical(
                f"FAILED TO SEND TO DLQ: {dlq_err}. Message may be lost. Original error: {error}", exc_info=True
            )

    def get_health_status(self) -> Dict[str, Any]:
        """Return the current health status and metrics of the consumer."""
        return {
            "is_running": self.is_running,
            "consumer_name": self.consumer_name,
            "current_offset": self.current_offset,
            "last_committed_offset": self.last_committed_offset,
            "metrics": self.metrics.get_stats(),
        }

    async def _index_to_opensearch(self, log_data: dict, original_message: str, offset: int):
        """
        Index log data to OpenSearch with retry logic and error categorization.
        """
        max_retries = 3
        retry_delay = 1
        start_time = time.time()

        for attempt in range(max_retries):
            try:
                self.opensearch_client.index_log(log_data)
                self.metrics.record_success(time.time() - start_time)
                logger.debug(f"Indexed log {log_data.get('log_id')} to OpenSearch")
                return True

            except (ConnectionError, TransportError) as e:
                # Network/transient issues - retry
                self.metrics.record_transient_error("network")
                if attempt < max_retries - 1:
                    logger.warning(f"Network error (attempt {attempt + 1}/{max_retries}): {e}. Retrying...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    self.metrics.record_failure("network_final_failure")
                    await self._send_to_dlq(original_message, e, offset)

            except RequestError as e:
                # Validation/mapping errors - don't retry, move to DLQ if mapping issue
                error_type = self._categorize_error(e)
                self.metrics.record_failure(error_type)

                if error_type == "validation":
                    logger.error(f"Validation error in OpenSearch mapping: {e}. Skipping log {log_data.get('log_id')}")
                    # We don't necessarily want to DLQ every validation error if it's junk data
                    # but for audit logs, it's safer to DLQ so we can fix the mapping if needed
                    await self._send_to_dlq(original_message, e, offset)
                else:
                    await self._send_to_dlq(original_message, e, offset)
                break

            except Exception as e:
                # Other unexpected errors
                self.metrics.record_transient_error("unknown")
                if attempt < max_retries - 1:
                    logger.warning(f"Unexpected error (attempt {attempt + 1}/{max_retries}): {e}. Retrying...")
                    await asyncio.sleep(retry_delay)
                else:
                    self.metrics.record_failure("unknown_final_failure")
                    await self._send_to_dlq(original_message, e, offset)

        return False

    async def _message_handler(self, message, context):
        """
        Handle incoming messages from RabbitMQ Stream.
        """
        self.current_offset = context.offset

        try:
            log_data = json.loads(message)

            # Index to OpenSearch with categorized error handling
            await self._index_to_opensearch(log_data, message, context.offset)

        except json.JSONDecodeError as e:
            logger.warning(f"Skipping message with offset {context.offset} due to JSON decode error.")
            self.metrics.record_failure("serialization")
            await self._send_to_dlq(message, e, context.offset)

        # Periodic offset storage
        if self.metrics.processed_count > 0 and self.metrics.processed_count % self.BATCH_SIZE == 0:
            await self._commit_offset(context.offset)

        # Periodic stats logging
        if self.metrics.processed_count > 0 and self.metrics.processed_count % self.STATS_INTERVAL == 0:
            self.metrics.log_summary()

    async def _commit_offset(self, offset: int):
        """Commit offset to RabbitMQ Stream."""
        if self.rabbitmq_consumer and offset > self.last_committed_offset:
            try:
                await self.rabbitmq_consumer.store_offset(
                    subscriber_name=self.consumer_name, stream=settings.RABBITMQ_STREAM_NAME, offset=offset
                )
                self.last_committed_offset = offset
                self.metrics.record_commit()
                logger.info(f"Committed offset at {offset} after processing {self.metrics.processed_count} messages.")
            except Exception as e:
                logger.error(f"Failed to commit offset at {offset}: {e}")

    def _handle_signal(self, sig, frame):
        """Handle termination signals for graceful shutdown."""
        logger.info(f"Received signal {sig}. Requesting shutdown...")
        self.is_running = False

    async def start(self):
        """Start the consumer and begin processing messages."""
        self.is_running = True

        # Register signal handlers for graceful shutdown
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, self._handle_signal)

        # Initialize RabbitMQ consumer
        self.rabbitmq_consumer = RStreamConsumer(
            host=settings.RABBITMQ_STREAM_HOST,
            port=settings.RABBITMQ_STREAM_PORT,
            username=settings.RABBITMQ_STREAM_USER,
            password=settings.RABBITMQ_STREAM_PASSWORD,
            vhost=settings.RABBITMQ_STREAM_VHOST,
        )

        try:
            await self.rabbitmq_consumer.create_stream(settings.RABBITMQ_STREAM_NAME, exists_ok=True)
            await self.rabbitmq_consumer.start()

            # Subscribe to the stream
            await self.rabbitmq_consumer.subscribe(
                stream=settings.RABBITMQ_STREAM_NAME,
                callback=self._message_handler,
                offset_specification=ConsumerOffsetSpecification(OffsetType.FIRST, None),
                subscriber_name=self.consumer_name,
            )

            logger.info(f"Consumer {self.consumer_name} started successfully")

            # Monitoring loop while running
            while self.is_running:
                await asyncio.sleep(1)
                # We use a loop here so we can respond to self.is_running becoming False
                # The actual message processing happens in the background via the subscribe callback

            logger.info("Shutdown initiated...")
            await self.stop()

        except Exception as e:
            logger.error(f"Consumer error: {e}", exc_info=True)
            await self.stop()

    async def stop(self):
        """Stop the consumer and perform cleanup."""
        self.is_running = False

        # Final offset commit if needed
        if self.current_offset > self.last_committed_offset:
            logger.info(f"Performing final offset commit at {self.current_offset}")
            await self._commit_offset(self.current_offset)

        # Log final stats
        self.metrics.log_summary()

        # Close RabbitMQ consumer
        if self.rabbitmq_consumer:
            await self.rabbitmq_consumer.close()
            self.rabbitmq_consumer = None

        # Close DLQ producer
        if self.dlq_producer:
            await self.dlq_producer.close()
            self.dlq_producer = None

        logger.info("Consumer stopped successfully")
