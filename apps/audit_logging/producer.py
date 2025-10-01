# audit_logging/producer.py
import asyncio
import datetime
import json
import logging
import uuid

from django.conf import settings
from rstream import Producer, exceptions

file_audit_logger = logging.getLogger("audit_log_producer")


class AuditStreamProducer:
    """
    Manages sending messages to a RabbitMQ Stream.
    """

    async def _send_message_async(self, message_body: str):
        """
        Connects to RabbitMQ, sends a single message, and disconnects.
        """
        try:
            async with Producer(
                host=settings.RABBITMQ_STREAM_HOST,
                port=settings.RABBITMQ_STREAM_PORT,
                username=settings.RABBITMQ_STREAM_USER,
                password=settings.RABBITMQ_STREAM_PASSWORD,
                vhost=settings.RABBITMQ_STREAM_VHOST,
            ) as producer:
                try:
                    await producer.create_stream(settings.RABBITMQ_STREAM_NAME, exists_ok=True)
                except exceptions.PreconditionFailed:
                    # Stream already exists, which is fine
                    logging.debug("Stream already exists, proceeding.")

                await producer.send(settings.RABBITMQ_STREAM_NAME, message_body.encode("utf-8"))
        except Exception:
            logging.error("Failed to send audit log to RabbitMQ Stream:", exc_info=True)
            raise

    def log_event(self, **kwargs):
        """
        Formats a log event, writes it to a local file, and sends it to
        the RabbitMQ Stream.
        """
        kwargs["log_id"] = str(uuid.uuid4())
        kwargs["timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        log_json_string = json.dumps(kwargs)

        # Step 1: Write to local file for backup/local auditing.
        file_audit_logger.info(log_json_string)

        # Step 2: Push to RabbitMQ Stream.
        asyncio.run(self._send_message_async(log_json_string))


# Singleton instance of the producer
_audit_producer = AuditStreamProducer()


def log_audit_event(**kwargs):
    """
    Logs an audit event.

    This is the public interface for logging. It formats the event, writes it
    to a local log file, and pushes it to a RabbitMQ Stream.
    """
    _audit_producer.log_event(**kwargs)
