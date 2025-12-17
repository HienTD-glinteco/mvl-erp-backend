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
    AttendanceRecord,
    Employee,
)
from apps.hrm.services.timesheets import trigger_timesheet_updates_from_records

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Django management command to run the realtime attendance listener."""

    help = "Run realtime attendance listener for all enabled devices"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue: asyncio.Queue = None
        self.loop = None
        self.running = False

        # Caches to reduce DB hits
        self.device_cache: Dict[int, AttendanceDevice] = {}
        self.employee_cache: Dict[str, int] = {}  # attendance_code -> employee_id

        # Stats
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
            self.queue = asyncio.Queue()

            # Create listener instance
            listener = ZKRealtimeDeviceListener(
                get_devices_callback=self.get_enabled_devices,
                on_attendance_event=self.on_attendance_event,
                on_device_connected=self.on_device_connected,
                on_device_disconnected=self.on_device_disconnected,
                on_device_error=self.on_device_error,
                on_device_disabled=self.on_device_disabled,
            )

            # Start background event processor
            processor_task = loop.create_task(self.process_events())

            # Start listener
            try:
                loop.run_until_complete(listener.start())
            except asyncio.CancelledError:
                pass
            finally:
                # When listener stops, ensure we drain the queue
                logger.info("Listener stopped, draining event queue...")
                # Wait a bit for processor to clear queue
                loop.run_until_complete(self.drain_queue())
                processor_task.cancel()
                try:
                    loop.run_until_complete(processor_task)
                except asyncio.CancelledError:
                    pass

            logger.info(f"Realtime attendance listener stopped. Total processed: {self.processed_count}")

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
            # Pre-populate cache
            self.device_cache[device.id] = device

        logger.info(f"Found {len(device_infos)} enabled devices for realtime monitoring")
        return device_infos

    async def on_attendance_event(self, event: ZKAttendanceEvent) -> None:
        """Handle attendance event captured from device."""
        if self.running:
            self.queue.put_nowait(event)

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
            # Only query if we really need name, otherwise just log ID
            device_name = f"ID: {device_id}"
            if device_id in self.device_cache:
                device_name = self.device_cache[device_id].name

            logger.warning(
                f"Device {device_name} error: {error_message} (consecutive failures: {consecutive_failures})"
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

    async def process_events(self):
        """Background task to process events from the queue in batches."""
        batch: List[ZKAttendanceEvent] = []
        last_save_time = time.time()
        BATCH_SIZE = 100
        BATCH_TIMEOUT = 1.0  # seconds

        logger.info("Event processor started")

        while self.running:
            try:
                # Calculate timeout
                now = time.time()
                time_since_last_save = now - last_save_time
                timeout = max(0.1, BATCH_TIMEOUT - time_since_last_save)

                try:
                    # Wait for event
                    event = await asyncio.wait_for(self.queue.get(), timeout=timeout)
                    batch.append(event)
                    self.queue.task_done()
                except asyncio.TimeoutError:
                    # Timeout reached, check if we need to flush
                    pass

                # Check if we should flush
                now = time.time()
                should_flush = len(batch) >= BATCH_SIZE or (batch and (now - last_save_time) >= BATCH_TIMEOUT)

                if should_flush:
                    await self.save_batch(batch)
                    batch = []
                    last_save_time = time.time()

            except asyncio.CancelledError:
                # Save remaining items on cancel
                if batch:
                    await self.save_batch(batch)
                break
            except Exception as e:
                logger.error(f"Error in event processor: {e}")
                # Don't lose the batch? or maybe we skip it to avoid loop?
                # For now, clear batch to avoid infinite error loop if data is bad
                batch = []

    async def drain_queue(self):
        """Drain any remaining events in the queue."""
        batch = []
        while not self.queue.empty():
            try:
                event = self.queue.get_nowait()
                batch.append(event)
                self.queue.task_done()
            except asyncio.QueueEmpty:
                break

        if batch:
            await self.save_batch(batch)

    @sync_to_async
    def save_batch(self, batch: List[ZKAttendanceEvent]):
        """Save a batch of events to the database."""
        if not batch:
            return

        records_to_create = []

        # Pre-fetch employees if needed
        attendance_codes = {e.user_id for e in batch if e.user_id not in self.employee_cache}
        if attendance_codes:
            employees = Employee.objects.filter(attendance_code__in=attendance_codes)
            for emp in employees:
                self.employee_cache[emp.attendance_code] = emp.id

        for event in batch:
            # Get device
            device = self.device_cache.get(event.device_id)
            if not device:
                # Try to fetch
                try:
                    device = AttendanceDevice.objects.get(id=event.device_id)
                    self.device_cache[event.device_id] = device
                except AttendanceDevice.DoesNotExist:
                    logger.error(f"Device ID {event.device_id} not found for event")
                    continue

            # Get employee
            employee_id = self.employee_cache.get(event.user_id)

            # Ensure timestamp is timezone-aware
            timestamp = event.timestamp
            if timestamp.tzinfo is None:
                timestamp = timezone.make_aware(timestamp)
            else:
                timestamp = timestamp.replace(tzinfo=timezone.get_current_timezone())

            record = AttendanceRecord(
                biometric_device=device,
                employee_id=employee_id,
                attendance_code=event.user_id,
                timestamp=timestamp,
                raw_data={
                    "uid": event.uid,
                    "user_id": event.user_id,
                    "timestamp": timestamp.isoformat(),
                    "status": event.status,
                    "punch": event.punch,
                },
                is_valid=True,
            )
            # Ensure `code` is set before bulk_create. AutoCodeMixin sets a temp code on save(),
            # but bulk_create bypasses save(); create a temporary unique code here.
            if not getattr(record, "code", None):
                temp_prefix = getattr(AttendanceRecord, "TEMP_CODE_PREFIX", "TEMP_")
                record.code = f"{temp_prefix}{get_random_string(16)}"
            records_to_create.append(record)

        if records_to_create:
            created_records = AttendanceRecord.objects.bulk_create(records_to_create)
            self.processed_count += len(created_records)
            logger.info(f"Saved batch of {len(created_records)} attendance records")

            # Post-processing: Trigger timesheet updates
            trigger_timesheet_updates_from_records(created_records)
