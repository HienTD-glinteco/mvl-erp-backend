"""Management command to run the realtime attendance listener.

This command starts the realtime attendance listener that maintains persistent
connections to all enabled attendance devices and captures events in realtime.
"""

import asyncio
import logging
import signal

from django.core.management.base import BaseCommand

from apps.devices.zk import ZKRealtimeDeviceListener

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Django management command to run the realtime attendance listener."""

    help = "Run realtime attendance listener for all enabled devices"

    def handle(self, *args, **options):
        """Execute the command."""
        logger.info("Starting realtime attendance listener...")

        # Create listener instance
        listener = ZKRealtimeDeviceListener()

        # Set up signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            logger.warning("\nShutdown signal received, stopping listener...")
            asyncio.create_task(listener.stop())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Run the listener
        try:
            asyncio.run(listener.start())
            logger.info("Realtime attendance listener stopped")
        except KeyboardInterrupt:
            logger.warning("\nListener interrupted by user")
        except Exception as e:
            logger.error(f"Error running listener: {str(e)}")
            logger.exception("Fatal error in realtime attendance listener")
            raise
