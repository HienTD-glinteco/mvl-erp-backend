# audit_logging/management/commands/consume_audit_logs.py
import asyncio

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.audit_logging.consumer import AuditLogConsumer


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

        # Initialize and run the consumer
        consumer = AuditLogConsumer(
            batch_size=batch_size,
            consumer_name=consumer_name,
        )

        try:
            asyncio.run(consumer.start())
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Interrupted. Shutting down..."))
        finally:
            self.stdout.write(self.style.SUCCESS("Consumer stopped."))

