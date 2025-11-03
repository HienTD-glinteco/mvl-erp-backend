"""Management command to run the realtime attendance listener.

This command starts the realtime attendance listener that maintains persistent
connections to all enabled attendance devices and captures events in realtime.

The listener uses callbacks to handle business logic and database operations,
keeping device communication logic separate from business logic.
"""

import asyncio
import logging
import signal

from django.core.management.base import BaseCommand

from apps.devices.zk import ZKRealtimeDeviceListener
from apps.hrm.realtime_callbacks import (
    get_enabled_devices,
    handle_attendance_event,
    handle_device_connected,
    handle_device_disconnected,
    handle_device_error,
    handle_device_disabled,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Django management command to run the realtime attendance listener."""

    help = "Run realtime attendance listener for all enabled devices"

    def handle(self, *args, **options):
        """Execute the command."""
        logger.info("Starting realtime attendance listener...")

        # Create listener instance with HRM business logic callbacks
        listener = ZKRealtimeDeviceListener(
            get_devices_callback=get_enabled_devices,
            on_attendance_event=handle_attendance_event,
            on_device_connected=handle_device_connected,
            on_device_disconnected=handle_device_disconnected,
            on_device_error=handle_device_error,
            on_device_disabled=handle_device_disabled,
        )

        # Set up signal handlers for graceful shutdown
        loop = None

        def signal_handler(signum, frame):
            logger.warning("\nShutdown signal received, stopping listener...")
            if loop and loop.is_running():
                loop.create_task(listener.stop())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Run the listener
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(listener.start())
            logger.info("Realtime attendance listener stopped")
        except KeyboardInterrupt:
            logger.warning("\nListener interrupted by user")
        except Exception as e:
            logger.error(f"Error running listener: {str(e)}")
            logger.exception("Fatal error in realtime attendance listener")
            raise
        finally:
            if loop:
                loop.close()
