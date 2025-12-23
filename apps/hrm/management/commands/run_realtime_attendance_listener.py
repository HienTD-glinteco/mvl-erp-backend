"""Management command to run the realtime attendance listener.

This command starts the realtime attendance listener that maintains persistent
connections to all enabled attendance devices and captures events in realtime.

The listener uses callbacks to handle business logic and database operations,
keeping device communication logic separate from business logic.
"""

import asyncio
import logging
import signal
import time
from typing import Any, Dict, List

from asgiref.sync import sync_to_async
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.crypto import get_random_string

from apps.devices.zk import ZKAttendanceEvent, ZKDeviceInfo, ZKRealtimeDeviceListener
from apps.hrm.models import (
    AttendanceDevice,
)
from apps.hrm.tasks.attendances import process_realtime_attendance_event

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Django management command to run the realtime attendance listener."""

    help = "Run realtime attendance listener for all enabled devices"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.loop = None
        self.running = False
        self.processed_count = 0

    def handle(self, *args, **options):
        """Execute the command."""
        logger.info("Starting realtime attendance listener...")

        # Initialize
        self.running = True

        # Set up signal handlers for graceful shutdown
        loop = None

        def signal_handler(signum, frame):
            logger.warning("\nShutdown signal received, stopping listener...")
            self.running = False
            if loop and loop.is_running():
                # We'll let the listener stop method handle the task cancellation
                pass

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.loop = loop

            # Create listener instance
            listener = ZKRealtimeDeviceListener(
                get_devices_callback=self.get_enabled_devices,
                on_attendance_event=self.on_attendance_event,
                on_device_connected=self.on_device_connected,
                on_device_disconnected=self.on_device_disconnected,
                on_device_error=self.on_device_error,
                on_device_disabled=self.on_device_disabled,
            )

            # Start listener
            try:
                loop.run_until_complete(listener.start())
            except asyncio.CancelledError:
                pass

            logger.info(f"Realtime attendance listener stopped. Events dispatched: {self.processed_count}")

        except KeyboardInterrupt:
            logger.warning("\nListener interrupted by user")
        except Exception as e:
            logger.error(f"Error running listener: {str(e)}")
            logger.exception("Fatal error in realtime attendance listener")
            raise
        finally:
            if loop:
                loop.close()

    def get_enabled_devices(self) -> list[ZKDeviceInfo]:
        """Get list of enabled attendance devices for realtime monitoring."""
        devices = AttendanceDevice.objects.filter(
            is_enabled=True,
            realtime_enabled=True,
        ).select_related("block")

        device_infos = []
        for device in devices:
            device_infos.append(
                ZKDeviceInfo(
                    device_id=device.id,
                    name=device.name,
                    ip_address=device.ip_address,
                    port=device.port,
                    password=device.password or 0,
                )
            )

        logger.info(f"Found {len(device_infos)} enabled devices for realtime monitoring")
        return device_infos

    async def on_attendance_event(self, event: ZKAttendanceEvent) -> None:
        """Handle attendance event captured from device."""
        if self.running:
            # Dispatch to Celery for async processing
            # We convert the event to a dict first
            event_data = event.to_dict()
            # Ensure timestamp is ISO string for serialization
            if hasattr(event_data["timestamp"], "isoformat"):
                event_data["timestamp"] = event_data["timestamp"].isoformat()

            # Use delay() to dispatch task asynchronously
            # We wrap this in sync_to_async or just call it directly since .delay() is non-blocking (usually)
            # But we are in an async function.
            try:
                await sync_to_async(process_realtime_attendance_event.delay)(event_data)
                self.processed_count += 1
            except Exception as e:
                logger.error(f"Failed to dispatch event to Celery: {e}")

    def on_device_connected(self, device_id: int, device_info: dict[str, Any]) -> None:
        """Handle device connection event (runs in thread)."""
        try:
            device = AttendanceDevice.objects.get(id=device_id)

            updated_fields = []
            if device_info.get("serial_number") and device.serial_number != device_info["serial_number"]:
                device.serial_number = device_info["serial_number"]
                updated_fields.append("serial_number")

            if (
                device_info.get("registration_number")
                and device.registration_number != device_info["registration_number"]
            ):
                device.registration_number = device_info["registration_number"]
                updated_fields.append("registration_number")

            if not device.is_connected:
                device.is_connected = True
                updated_fields.append("is_connected")

            if updated_fields:
                updated_fields.append("updated_at")
                device.save(update_fields=updated_fields)

            # Update cache
            self.device_cache[device_id] = device

            logger.info(f"Device {device.name} (ID: {device_id}) connected successfully")

        except AttendanceDevice.DoesNotExist:
            logger.error(f"Device ID {device_id} not found in database")
        except Exception as e:
            logger.exception(f"Error handling device connected event for device ID {device_id}: {str(e)}")

    def on_device_disconnected(self, device_id: int) -> None:
        """Handle device disconnection event (runs in thread)."""
        try:
            device = AttendanceDevice.objects.get(id=device_id)

            if device.is_connected:
                device.is_connected = False
                device.save(update_fields=["is_connected", "updated_at"])

            # Update cache
            self.device_cache[device_id] = device

            logger.info(f"Device {device.name} (ID: {device_id}) disconnected")

        except AttendanceDevice.DoesNotExist:
            logger.error(f"Device ID {device_id} not found in database")
        except Exception as e:
            logger.exception(f"Error handling device disconnected event for device ID {device_id}: {str(e)}")

    def on_device_error(self, device_id: int, error_message: str, consecutive_failures: int) -> None:
        """Handle device error event (runs in thread)."""
        try:
            logger.warning(
                f"Device ID {device_id} error: {error_message} (consecutive failures: {consecutive_failures})"
            )
        except Exception as e:
            logger.exception(f"Error handling device error event for device ID {device_id}: {str(e)}")

    def on_device_disabled(self, device_id: int) -> None:
        """Handle device disabled event (runs in thread)."""
        try:
            device = AttendanceDevice.objects.get(id=device_id)

            device.realtime_enabled = False
            device.realtime_disabled_at = timezone.now()
            device.is_connected = False
            device.save(update_fields=["realtime_enabled", "realtime_disabled_at", "is_connected", "updated_at"])

            logger.critical(
                f"Device {device.name} (ID: {device_id}) has been offline for extended period. "
                f"Realtime monitoring disabled. Manual intervention required."
            )

        except AttendanceDevice.DoesNotExist:
            logger.error(f"Device ID {device_id} not found in database")
        except Exception as e:
            logger.exception(f"Error handling device disabled event for device ID {device_id}: {str(e)}")

