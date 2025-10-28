"""Management command to run the realtime attendance listener.

This command starts the realtime attendance listener that maintains persistent
connections to all enabled attendance devices and captures events in realtime.
"""

import asyncio
import logging
import signal

from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _

from apps.hrm.realtime_listener import RealtimeAttendanceListener

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Django management command to run the realtime attendance listener."""

    help = _("Run realtime attendance listener for all enabled devices")

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--log-level",
            type=str,
            default="INFO",
            choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            help=_("Set logging level (default: INFO)"),
        )

    def handle(self, *args, **options):
        """Execute the command."""
        # Set logging level
        log_level = options["log_level"]
        logging.getLogger("apps.hrm.realtime_listener").setLevel(getattr(logging, log_level))

        self.stdout.write(self.style.SUCCESS(_("Starting realtime attendance listener...")))

        # Create listener instance
        listener = RealtimeAttendanceListener()

        # Set up signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            self.stdout.write(self.style.WARNING(_("\nShutdown signal received, stopping listener...")))
            asyncio.create_task(listener.stop())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Run the listener
        try:
            asyncio.run(listener.start())
            self.stdout.write(self.style.SUCCESS(_("Realtime attendance listener stopped")))
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING(_("\nListener interrupted by user")))
        except Exception as e:
            self.stdout.write(self.style.ERROR(_("Error running listener: %(error)s") % {"error": str(e)}))
            logger.exception("Fatal error in realtime attendance listener")
            raise
