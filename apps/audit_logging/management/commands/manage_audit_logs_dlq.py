import asyncio
import logging

from django.core.management.base import BaseCommand

from apps.audit_logging.dlq_consumer import DLQConsumer

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Manage audit log Dead Letter Queue (DLQ)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--action",
            type=str,
            default="list",
            choices=["list", "reprocess_all", "purge"],
            help="Action to perform: list (show messages), reprocess_all (attempt to re-index all messages), or purge (delete all messages)",
        )
        parser.add_argument(
            "--count",
            type=int,
            default=10,
            help="Number of messages to list",
        )
        parser.add_argument(
            "--no-input",
            action="store_true",
            help="Do not prompt for confirmation before purging",
        )

    def handle(self, *args, **options):
        action = options["action"]
        count = options["count"]
        no_input = options["no_input"]

        dlq_consumer = DLQConsumer()

        if action == "list":
            self._list_messages(dlq_consumer, count)
        elif action == "reprocess_all":
            self._reprocess_all(dlq_consumer)
        elif action == "purge":
            self._purge_dlq(dlq_consumer, no_input)

    def _list_messages(self, dlq_consumer: DLQConsumer, count: int):
        self.stdout.write(f"Fetching up to {count} messages from DLQ...")
        messages = asyncio.run(dlq_consumer.list_messages(count))

        if not messages:
            self.stdout.write(self.style.WARNING("No messages found in DLQ."))
            return

        for msg in messages:
            self.stdout.write("-" * 40)
            self.stdout.write(f"DLQ Offset: {msg.get('dlq_offset')}")
            self.stdout.write(f"Failed at: {msg.get('failed_at')}")
            self.stdout.write(f"Error Type: {msg.get('error_type')}")
            self.stdout.write(f"Error: {msg.get('error')}")

            original = msg.get("original_message", {})
            log_id = original.get("log_id") if isinstance(original, dict) else "unknown"
            self.stdout.write(f"Log ID: {log_id}")

    def _reprocess_all(self, dlq_consumer: DLQConsumer):
        self.stdout.write("Reprocessing messages from DLQ...")
        messages = asyncio.run(dlq_consumer.list_messages(100))  # Process up to 100 at a time

        if not messages:
            self.stdout.write(self.style.WARNING("No messages found in DLQ to reprocess."))
            return

        success_count = 0
        for msg in messages:
            success = asyncio.run(dlq_consumer.reprocess_message(msg))
            if success:
                success_count += 1

        self.stdout.write(self.style.SUCCESS(f"Successfully reprocessed {success_count}/{len(messages)} messages."))
        self.stdout.write(
            self.style.WARNING("Note: Messages remain in the DLQ stream but are now indexed in OpenSearch.")
        )

    def _purge_dlq(self, dlq_consumer: DLQConsumer, no_input: bool):
        if not no_input:
            confirm = input("Are you sure you want to purge all messages in the DLQ? [y/N]: ")
            if confirm.lower() != "y":
                self.stdout.write("Aborted.")
                return

        self.stdout.write("Purging DLQ stream...")
        success = asyncio.run(dlq_consumer.purge_dlq())
        if success:
            self.stdout.write(self.style.SUCCESS("Successfully purged DLQ."))
        else:
            self.stdout.write(self.style.ERROR("Failed to purge DLQ."))
