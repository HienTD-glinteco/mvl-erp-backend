# audit_logging/management/commands/consume_audit_logs.py
import asyncio
import json
import logging
import time

from django.conf import settings
from django.core.management.base import BaseCommand
from opensearchpy.exceptions import ConnectionError, TransportError
from rstream import Consumer
from rstream.constants import ConsumerOffsetSpecification, OffsetType

from apps.audit_logging.opensearch_client import get_opensearch_client
from apps.audit_logging.s3_uploader import process_and_upload_batch

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Consume audit logs from RabbitMQ Stream and index to OpenSearch + upload to S3"

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=None,
            help="Override default batch size for S3 uploads",
        )
        parser.add_argument(
            "--consumer-name",
            type=str,
            default="audit_log_consumer",
            help="Consumer name for offset tracking (uses RabbitMQ's server-side tracking)",
        )

    def handle(self, *args, **options):
        batch_size = options.get("batch_size") or settings.AUDIT_LOG_BATCH_SIZE
        consumer_name = options["consumer_name"]

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting audit log consumer: {consumer_name} (batch_size={batch_size})"
            )
        )

        # Run the async consumer
        asyncio.run(self._run_consumer(batch_size, consumer_name))

    async def _run_consumer(self, batch_size: int, consumer_name: str):
        """Runs the RabbitMQ stream consumer continuously."""
        log_batch = []
        opensearch_client = get_opensearch_client()

        consumer = Consumer(
            host=settings.RABBITMQ_STREAM_HOST,
            port=settings.RABBITMQ_STREAM_PORT,
            username=settings.RABBITMQ_STREAM_USER,
            password=settings.RABBITMQ_STREAM_PASSWORD,
            vhost=settings.RABBITMQ_STREAM_VHOST,
        )

        async def message_handler(message, context):
            nonlocal log_batch
            try:
                log_data = json.loads(message)

                # Add to batch for S3 upload first (before OpenSearch indexing)
                log_batch.append(log_data)

                # Index to OpenSearch for real-time search with retry logic
                # This happens after adding to batch so S3 archival continues even if indexing fails
                max_retries = 3
                retry_delay = 1  # Start with 1 second delay
                
                for attempt in range(max_retries):
                    try:
                        opensearch_client.index_log(log_data)
                        logger.debug(f"Indexed log {log_data['log_id']} to OpenSearch")
                        break  # Success, exit retry loop
                    except (ConnectionError, TransportError) as e:
                        # Network/connection issues - retry
                        if attempt < max_retries - 1:
                            logger.warning(
                                f"Failed to index log to OpenSearch (attempt {attempt + 1}/{max_retries}): {e}. "
                                f"Retrying in {retry_delay} seconds..."
                            )
                            time.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                        else:
                            logger.error(
                                f"Failed to index log to OpenSearch after {max_retries} attempts: {e}",
                                exc_info=True
                            )
                    except Exception as e:
                        # Other errors - log and continue without retry
                        logger.error(
                            f"Failed to index log to OpenSearch: {e}", exc_info=True
                        )
                        break

            except json.JSONDecodeError:
                logger.warning(
                    f"Skipping message with offset {context.offset} due to JSON decode error."
                )
                return

            # Upload to S3 when batch is full
            if len(log_batch) >= batch_size:
                logger.info(f"Uploading batch of {len(log_batch)} logs to S3.")
                try:
                    process_and_upload_batch(list(log_batch))
                    log_batch.clear()
                except Exception as e:
                    logger.error(f"Failed to upload batch to S3: {e}", exc_info=True)
                    # Keep logs in batch for retry on next batch
                    # In production, you might want more sophisticated retry logic

        try:
            await consumer.start()
            # Use RabbitMQ's server-side offset tracking
            # The consumer name is used for tracking position in the stream
            await consumer.subscribe(
                stream=settings.RABBITMQ_STREAM_NAME,
                callback=message_handler,
                offset_specification=ConsumerOffsetSpecification(OffsetType.FIRST, None),
                consumer_name=consumer_name,
            )

            logger.info(f"Consumer {consumer_name} started successfully")
            self.stdout.write(
                self.style.SUCCESS(
                    f"Consumer running. Press Ctrl+C to stop gracefully."
                )
            )

            # Run indefinitely
            await consumer.run()

        except KeyboardInterrupt:
            logger.info("Shutting down consumer gracefully...")
            self.stdout.write(self.style.WARNING("Interrupted. Shutting down..."))

            # Upload any remaining logs in the batch before shutting down
            if log_batch:
                logger.info(f"Uploading final batch of {len(log_batch)} logs to S3.")
                try:
                    process_and_upload_batch(list(log_batch))
                except Exception as e:
                    logger.error(
                        f"Failed to upload final batch to S3: {e}", exc_info=True
                    )

        finally:
            await consumer.close()
            self.stdout.write(self.style.SUCCESS("Consumer stopped."))
