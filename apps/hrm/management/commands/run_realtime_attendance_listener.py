"""Management command to run the realtime attendance listener.

This command starts the realtime attendance listener that maintains persistent
connections to all enabled attendance devices and captures events in realtime.

The listener uses callbacks to handle business logic and database operations,
keeping device communication logic separate from business logic.
"""

import asyncio
import logging
import signal
from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.devices.zk import ZKAttendanceEvent, ZKDeviceInfo, ZKRealtimeDeviceListener
from apps.hrm.models import AttendanceDevice, AttendanceRecord

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


def get_enabled_devices() -> list[ZKDeviceInfo]:
    """Get list of enabled attendance devices for realtime monitoring.

    Returns:
        List of ZKDeviceInfo objects for devices that have realtime enabled
    """
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


def handle_attendance_event(event: ZKAttendanceEvent) -> None:
    """Handle attendance event captured from device.

    This creates an AttendanceRecord in the database for the event.
    Applies delta time correction to ensure accurate timestamps.

    Args:
        event: ZKAttendanceEvent object from the device
    """
    from datetime import timedelta

    from apps.devices.zk import ZKDeviceService

    try:
        # Get the device
        try:
            device = AttendanceDevice.objects.get(id=event.device_id)
        except AttendanceDevice.DoesNotExist:
            logger.error(f"Device ID {event.device_id} not found in database")
            return

        # Check if time sync is needed (more than 1 hour since last sync)
        if device.should_resync_time(max_hours=1):
            logger.info(f"Re-syncing time for device {device.name} (last sync > 1 hour ago)")
            try:
                service = ZKDeviceService(
                    ip_address=device.ip_address,
                    port=device.port,
                    password=device.password,
                )
                with service:
                    device_time = service.get_device_time()
                    system_time = timezone.now()
                    device.update_time_sync(device_time, system_time)
                    device.save(update_fields=["delta_time_seconds", "time_last_synced_at", "updated_at"])
                    logger.info(
                        f"Re-synced time for device {device.name}: delta={device.delta_time_seconds}s"
                    )
            except Exception as e:
                logger.warning(f"Failed to re-sync time for device {device.name}: {str(e)}")

        # Ensure timestamp is timezone-aware
        device_timestamp = event.timestamp
        if device_timestamp.tzinfo is None:
            device_timestamp = timezone.make_aware(device_timestamp)

        # Apply delta time correction
        corrected_timestamp = device_timestamp + timedelta(seconds=device.delta_time_seconds)

        # Create attendance record
        record = AttendanceRecord.objects.create(
            device=device,
            attendance_code=event.user_id,
            timestamp=corrected_timestamp,
            raw_data={
                "uid": event.uid,
                "user_id": event.user_id,
                "timestamp": device_timestamp.isoformat(),
                "timestamp_corrected": corrected_timestamp.isoformat(),
                "delta_time_seconds": device.delta_time_seconds,
                "status": event.status,
                "punch": event.punch,
            },
            is_valid=True,  # Realtime events are considered valid by default
        )

        logger.info(
            f"Created attendance record {record.id} for user {event.user_id} "
            f"from device {event.device_name} at {corrected_timestamp} (device: {device_timestamp}, delta: {device.delta_time_seconds}s)"
        )

    except Exception as e:
        logger.exception(f"Error handling attendance event from device {event.device_name}: {str(e)}")


def handle_device_connected(device_id: int, device_info: dict[str, Any]) -> None:
    """Handle device connection event.

    Updates device information in the database when a device successfully connects.
    Also syncs device time on connection.

    Args:
        device_id: ID of the device that connected
        device_info: Dictionary with device information (serial_number, registration_number, etc.)
    """
    from datetime import timedelta

    from apps.devices.zk import ZKDeviceService

    try:
        device = AttendanceDevice.objects.get(id=device_id)

        # Update device info if provided
        updated_fields = []
        if device_info.get("serial_number") and device.serial_number != device_info["serial_number"]:
            device.serial_number = device_info["serial_number"]
            updated_fields.append("serial_number")

        if device_info.get("registration_number") and device.registration_number != device_info["registration_number"]:
            device.registration_number = device_info["registration_number"]
            updated_fields.append("registration_number")

        # Mark device as connected
        if not device.is_connected:
            device.is_connected = True
            updated_fields.append("is_connected")

        # Sync device time on connection
        try:
            service = ZKDeviceService(
                ip_address=device.ip_address,
                port=device.port,
                password=device.password,
            )
            with service:
                device_time = service.get_device_time()
                system_time = timezone.now()
                device.update_time_sync(device_time, system_time)
                updated_fields.extend(["delta_time_seconds", "time_last_synced_at"])
                logger.info(
                    f"Synced time for device {device.name} on connection: delta={device.delta_time_seconds}s"
                )
        except Exception as e:
            logger.warning(f"Failed to sync time for device {device.name} on connection: {str(e)}")

        if updated_fields:
            updated_fields.append("updated_at")
            device.save(update_fields=updated_fields)

        logger.info(f"Device {device.name} (ID: {device_id}) connected successfully")

    except AttendanceDevice.DoesNotExist:
        logger.error(f"Device ID {device_id} not found in database")
    except Exception as e:
        logger.exception(f"Error handling device connected event for device ID {device_id}: {str(e)}")


def handle_device_disconnected(device_id: int) -> None:
    """Handle device disconnection event.

    Updates device connection status in the database.

    Args:
        device_id: ID of the device that disconnected
    """
    try:
        device = AttendanceDevice.objects.get(id=device_id)

        if device.is_connected:
            device.is_connected = False
            device.save(update_fields=["is_connected", "updated_at"])

        logger.info(f"Device {device.name} (ID: {device_id}) disconnected")

    except AttendanceDevice.DoesNotExist:
        logger.error(f"Device ID {device_id} not found in database")
    except Exception as e:
        logger.exception(f"Error handling device disconnected event for device ID {device_id}: {str(e)}")


def handle_device_error(device_id: int, error_message: str, consecutive_failures: int) -> None:
    """Handle device error event.

    Logs device errors for monitoring and debugging.

    Args:
        device_id: ID of the device that encountered an error
        error_message: Error message describing the issue
        consecutive_failures: Number of consecutive failures
    """
    try:
        device = AttendanceDevice.objects.get(id=device_id)
        logger.warning(
            f"Device {device.name} (ID: {device_id}) error: {error_message} "
            f"(consecutive failures: {consecutive_failures})"
        )
    except AttendanceDevice.DoesNotExist:
        logger.error(f"Device ID {device_id} not found in database")
    except Exception as e:
        logger.exception(f"Error handling device error event for device ID {device_id}: {str(e)}")


def handle_device_disabled(device_id: int) -> None:
    """Handle device disabled event.

    Disables realtime monitoring for a device that has been offline for too long.

    Args:
        device_id: ID of the device to disable
    """
    try:
        device = AttendanceDevice.objects.get(id=device_id)

        # Disable realtime monitoring
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
