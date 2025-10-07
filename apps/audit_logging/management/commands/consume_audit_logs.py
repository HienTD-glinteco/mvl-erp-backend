# audit_logging/management/commands/consume_audit_logs.py
import asyncio

from django.core.management.base import BaseCommand

from apps.audit_logging.consumer import AuditLogConsumer


class Command(BaseCommand):
    help = "Consume audit logs from RabbitMQ Stream and index to OpenSearch"

    def add_arguments(self, parser):
        parser.add_argument(
            "--consumer-name",
            type=str,
            default="audit_log_consumer",
            help="Consumer name for offset tracking (uses RabbitMQ's server-side tracking)",
        )

    def handle(self, *args, **options):
        consumer_name = options["consumer_name"]

        self.stdout.write(self.style.SUCCESS(f"Starting audit log consumer: {consumer_name}"))

        # Initialize and run the consumer
        consumer = AuditLogConsumer(consumer_name=consumer_name)

        try:
            asyncio.run(consumer.start())
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Interrupted. Shutting down..."))
        finally:
            self.stdout.write(self.style.SUCCESS("Consumer stopped."))
