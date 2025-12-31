import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from django.conf import settings
from rstream import Consumer as RStreamConsumer
from rstream.constants import ConsumerOffsetSpecification, OffsetType

from .opensearch_client import get_opensearch_client

logger = logging.getLogger(__name__)


class DLQConsumer:
    """
    Utility for consuming and reprocessing messages from the Audit Log Dead Letter Queue.
    """

    rabbitmq_consumer: Optional[RStreamConsumer]
    is_running: bool

    def __init__(self, consumer_name: str = "audit_log_dlq_consumer"):
        self.consumer_name = consumer_name
        self.opensearch_client = get_opensearch_client()
        self.DLQ_STREAM_NAME = getattr(settings, "AUDIT_LOG_DLQ_NAME", f"{settings.RABBITMQ_STREAM_NAME}_dlq")
        self.rabbitmq_consumer = None
        self.messages: List[Dict[str, Any]] = []
        self.is_running = False

    async def _message_handler(self, message, context):
        """Handle incoming messages from the DLQ stream."""
        try:
            dlq_data = json.loads(message)
            dlq_data["dlq_offset"] = context.offset
            self.messages.append(dlq_data)
            logger.info(f"Received DLQ message with offset {context.offset}")
        except json.JSONDecodeError:
            logger.error(f"Failed to decode DLQ message at offset {context.offset}")

    async def list_messages(self, count: int = 10) -> List[Dict[str, Any]]:
        """
        Fetch a number of messages from the DLQ without reprocessing.
        """
        self.messages = []
        rabbitmq_consumer = RStreamConsumer(
            host=settings.RABBITMQ_STREAM_HOST,
            port=settings.RABBITMQ_STREAM_PORT,
            username=settings.RABBITMQ_STREAM_USER,
            password=settings.RABBITMQ_STREAM_PASSWORD,
            vhost=settings.RABBITMQ_STREAM_VHOST,
        )
        self.rabbitmq_consumer = rabbitmq_consumer

        try:
            await rabbitmq_consumer.start()
            # Subscribe from the beginning to peek at messages
            await rabbitmq_consumer.subscribe(
                stream=self.DLQ_STREAM_NAME,
                callback=self._message_handler,
                offset_specification=ConsumerOffsetSpecification(OffsetType.FIRST, None),
                subscriber_name=f"{self.consumer_name}_peek",
            )

            # Wait a bit to collect messages
            wait_time = 0.0
            while len(self.messages) < count and wait_time < 5:
                await asyncio.sleep(0.5)
                wait_time += 0.5

            return self.messages[:count]

        finally:
            if self.rabbitmq_consumer:
                await self.rabbitmq_consumer.close()

    async def reprocess_message(self, dlq_data: Dict[str, Any]) -> bool:
        """
        Attempt to re-index a message from the DLQ to OpenSearch.
        """
        original_message = dlq_data.get("original_message")
        if not original_message:
            logger.error("DLQ entry missing original_message")
            return False

        try:
            # Handle if original_message is string or dict
            log_data = original_message if isinstance(original_message, dict) else json.loads(original_message)

            self.opensearch_client.index_log(log_data)
            logger.info(f"Successfully reprocessed log {log_data.get('log_id')} from DLQ")
            return True
        except Exception as e:
            logger.error(f"Failed to reprocess message from DLQ: {e}")
            return False

    async def purge_dlq(self) -> bool:
        """
        Delete and recreate the DLQ stream to clear all messages.
        """
        # We need a consumer or producer to use the connection methods
        # RStreamConsumer allows stream deletion/creation
        temp_consumer = RStreamConsumer(
            host=settings.RABBITMQ_STREAM_HOST,
            port=settings.RABBITMQ_STREAM_PORT,
            username=settings.RABBITMQ_STREAM_USER,
            password=settings.RABBITMQ_STREAM_PASSWORD,
            vhost=settings.RABBITMQ_STREAM_VHOST,
        )
        try:
            await temp_consumer.start()
            await temp_consumer.delete_stream(self.DLQ_STREAM_NAME)
            await temp_consumer.create_stream(self.DLQ_STREAM_NAME, exists_ok=True)
            logger.info(f"Successfully purged DLQ stream: {self.DLQ_STREAM_NAME}")
            return True
        except Exception as e:
            logger.error(f"Failed to purge DLQ stream: {e}")
            return False
        finally:
            await temp_consumer.close()
