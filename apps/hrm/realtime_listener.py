"""Realtime attendance listener for capturing live events from attendance devices.

This module provides functionality to maintain persistent connections to attendance
devices and capture attendance events in realtime using PyZK's live_capture feature.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone as dt_timezone

from django.db import transaction
from zk import ZK
from zk.attendance import Attendance
from zk.exception import ZKErrorConnection, ZKErrorResponse

from apps.hrm.models import AttendanceDevice, AttendanceRecord

logger = logging.getLogger(__name__)

# Configuration constants
DEFAULT_LIVE_CAPTURE_TIMEOUT = 60
RECONNECT_BASE_DELAY = 5
RECONNECT_MAX_DELAY = 300
RECONNECT_BACKOFF_MULTIPLIER = 2
MAX_CONSECUTIVE_FAILURES = 5
MAX_RETRY_DURATION = 86400  # 1 day in seconds (stop retrying after this)
DEVICE_INFO_UPDATE_INTERVAL = 300  # Update device info every 5 minutes


class RealtimeAttendanceListener:
    """Manages realtime attendance event capture from multiple devices concurrently.

    This class handles:
    - Concurrent connections to multiple attendance devices
    - Live event capture and storage
    - Automatic reconnection with exponential backoff
    - Device status tracking and updates
    - Error handling and admin notifications
    """

    def __init__(self):
        """Initialize the realtime listener."""
        self._device_tasks: dict[int, asyncio.Task] = {}
        self._running = False
        self._shutdown_event = asyncio.Event()

    async def start(self):
        """Start the realtime listener for all enabled devices."""
        logger.info("Starting realtime attendance listener")
        self._running = True
        self._shutdown_event.clear()

        # Get all enabled devices
        devices = await self._get_enabled_devices()
        logger.info(f"Found {len(devices)} enabled device(s) for realtime monitoring")

        # Start listener task for each device
        for device in devices:
            task = asyncio.create_task(self._device_listener_loop(device))
            self._device_tasks[device.id] = task
            logger.info(f"Started listener task for device: {device.name} (ID: {device.id})")

        # Wait for shutdown signal
        await self._shutdown_event.wait()

    async def stop(self):
        """Stop all device listeners and clean up."""
        logger.info("Stopping realtime attendance listener")
        self._running = False
        self._shutdown_event.set()

        # Cancel all device tasks
        for device_id, task in self._device_tasks.items():
            if not task.done():
                task.cancel()
                logger.debug(f"Cancelled listener task for device ID: {device_id}")

        # Wait for all tasks to complete
        if self._device_tasks:
            await asyncio.gather(*self._device_tasks.values(), return_exceptions=True)

        self._device_tasks.clear()
        logger.info("Realtime attendance listener stopped")

    async def _get_enabled_devices(self) -> list[AttendanceDevice]:
        """Get all enabled attendance devices with realtime enabled from database."""
        return await asyncio.to_thread(
            lambda: list(AttendanceDevice.objects.filter(is_enabled=True, realtime_enabled=True))
        )

    async def _device_listener_loop(self, device: AttendanceDevice):
        """Main loop for a single device listener with retry logic.

        Args:
            device: AttendanceDevice instance to monitor
        """
        consecutive_failures = 0
        reconnect_delay = RECONNECT_BASE_DELAY
        last_device_info_update = 0
        first_failure_time = None  # Track when failures started

        while self._running:
            try:
                logger.info(f"Connecting to device: {device.name} at {device.ip_address}:{device.port}")

                # Connect to device
                zk_conn = await self._connect_device(device)

                # Update device info and status on successful connection
                current_time = time.time()
                await self._update_device_info(device, zk_conn)
                await self._mark_device_connected(device)
                last_device_info_update = current_time

                # Reset failure counter and timer on successful connection
                consecutive_failures = 0
                first_failure_time = None
                reconnect_delay = RECONNECT_BASE_DELAY

                logger.info(f"Successfully connected to device: {device.name}, starting live capture")

                # Start live capture loop
                await self._live_capture_loop(device, zk_conn, last_device_info_update)

            except (ZKErrorConnection, ZKErrorResponse, ConnectionError) as e:
                consecutive_failures += 1
                error_msg = f"Connection error for device {device.name}: {str(e)}"

                # Track first failure time
                if first_failure_time is None:
                    first_failure_time = time.time()

                # Check if we've been retrying for more than MAX_RETRY_DURATION (1 day)
                time_since_first_failure = time.time() - first_failure_time
                if time_since_first_failure >= MAX_RETRY_DURATION:
                    logger.critical(
                        f"Device {device.name} has been offline for {time_since_first_failure / 3600:.1f} hours. "
                        f"Disabling realtime listener for this device."
                    )
                    await self._disable_realtime_for_device(device)
                    # Exit the loop for this device
                    break

                logger.warning(
                    f"{error_msg} (failure {consecutive_failures}/{MAX_CONSECUTIVE_FAILURES}, "
                    f"retrying for {time_since_first_failure / 3600:.1f} hours)"
                )

                # Mark device as disconnected
                await self._mark_device_disconnected(device)

                # Check if we should notify admin
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    await self._notify_admin_device_offline(device, error_msg)
                    # Reset counter to avoid spamming notifications
                    consecutive_failures = 0

            except Exception as e:
                logger.exception(f"Unexpected error in listener loop for device {device.name}: {str(e)}")
                await self._mark_device_disconnected(device)

            finally:
                # Clean up connection if it exists
                if "zk_conn" in locals() and zk_conn:
                    await self._disconnect_device(device, zk_conn)

            # Wait before reconnecting (exponential backoff)
            if self._running:
                logger.info(f"Reconnecting to device {device.name} in {reconnect_delay} seconds")
                await asyncio.sleep(reconnect_delay)

                # Increase delay for next retry (exponential backoff)
                reconnect_delay = min(reconnect_delay * RECONNECT_BACKOFF_MULTIPLIER, RECONNECT_MAX_DELAY)

    async def _connect_device(self, device: AttendanceDevice) -> ZK:
        """Connect to an attendance device.

        Args:
            device: AttendanceDevice instance

        Returns:
            Connected ZK instance

        Raises:
            ZKErrorConnection: If connection fails
            ZKErrorResponse: If device response is invalid
        """

        def _do_connect():
            zk = ZK(
                device.ip_address,
                port=device.port,
                timeout=DEFAULT_LIVE_CAPTURE_TIMEOUT,
                password=device.password or 0,
                ommit_ping=False,
            )
            conn = zk.connect()
            if not conn:
                raise ConnectionError("Failed to establish connection")
            return conn

        return await asyncio.to_thread(_do_connect)

    async def _disconnect_device(self, device: AttendanceDevice, zk_conn: ZK):
        """Disconnect from an attendance device.

        Args:
            device: AttendanceDevice instance
            zk_conn: Connected ZK instance
        """

        def _do_disconnect():
            try:
                if hasattr(zk_conn, "end_live_capture"):
                    zk_conn.end_live_capture = True
                zk_conn.disconnect()
                logger.debug(f"Disconnected from device: {device.name}")
            except Exception as e:
                logger.warning(f"Error during disconnect from device {device.name}: {str(e)}")

        await asyncio.to_thread(_do_disconnect)

    async def _live_capture_loop(self, device: AttendanceDevice, zk_conn: ZK, last_info_update: float):
        """Run the live capture loop for a connected device.

        Args:
            device: AttendanceDevice instance
            zk_conn: Connected ZK instance
            last_info_update: Timestamp of last device info update
        """

        def _do_live_capture():
            """Run live capture in a separate thread."""
            for attendance in zk_conn.live_capture(new_timeout=DEFAULT_LIVE_CAPTURE_TIMEOUT):
                # Check if we should stop
                if not self._running or (hasattr(zk_conn, "end_live_capture") and zk_conn.end_live_capture):
                    break

                # None means timeout, continue waiting
                if attendance is None:
                    continue

                # Yield the attendance event
                yield attendance

        # Run live capture in executor
        loop = asyncio.get_event_loop()

        try:
            # We need to run the generator in a thread
            async for attendance in self._async_generator_from_sync(_do_live_capture, loop):
                if attendance is not None:
                    await self._process_attendance_event(device, attendance)

                # Periodically update device info
                current_time = time.time()
                if current_time - last_info_update >= DEVICE_INFO_UPDATE_INTERVAL:
                    await self._update_device_info(device, zk_conn)
                    last_info_update = current_time

        except Exception as e:
            logger.error(f"Error in live capture loop for device {device.name}: {str(e)}")
            raise

    async def _async_generator_from_sync(self, sync_gen_func, loop):
        """Convert a synchronous generator to an async generator.

        Args:
            sync_gen_func: Function that returns a synchronous generator
            loop: Event loop

        Yields:
            Items from the synchronous generator
        """

        def _get_next_item(gen):
            try:
                return next(gen), False
            except StopIteration:
                return None, True

        gen = sync_gen_func()

        while True:
            item, done = await loop.run_in_executor(None, _get_next_item, gen)
            if done:
                break
            yield item

    async def _process_attendance_event(self, device: AttendanceDevice, attendance: Attendance):
        """Process a single attendance event and store it in database.

        Args:
            device: AttendanceDevice that captured the event
            attendance: Attendance object from PyZK
        """
        try:
            # Ensure timestamp is timezone-aware
            timestamp = attendance.timestamp
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=dt_timezone.utc)

            # Log the event
            logger.info(
                f"Captured attendance event - Device: {device.name}, User: {attendance.user_id}, Time: {timestamp}"
            )

            # Store in database (avoid duplicates)
            await self._store_attendance_record(device, attendance, timestamp)

        except Exception as e:
            logger.error(
                f"Error processing attendance event from device {device.name}: {str(e)}, "
                f"Event: user_id={attendance.user_id}, timestamp={attendance.timestamp}"
            )

    async def _store_attendance_record(self, device: AttendanceDevice, attendance: Attendance, timestamp: datetime):
        """Store attendance record in database, avoiding duplicates.

        Args:
            device: AttendanceDevice that captured the event
            attendance: Attendance object from PyZK
            timestamp: Timezone-aware timestamp
        """

        def _do_store():
            # Check if record already exists
            existing = AttendanceRecord.objects.filter(
                device=device, attendance_code=attendance.user_id, timestamp=timestamp
            ).exists()

            if existing:
                logger.debug(
                    f"Attendance record already exists - Device: {device.name}, "
                    f"User: {attendance.user_id}, Time: {timestamp}"
                )
                return False

            # Create raw data
            raw_data = {
                "uid": attendance.uid,
                "user_id": attendance.user_id,
                "timestamp": timestamp.isoformat(),
                "status": attendance.status,
                "punch": attendance.punch,
            }

            # Create new record
            with transaction.atomic():
                AttendanceRecord.objects.create(
                    device=device, attendance_code=attendance.user_id, timestamp=timestamp, raw_data=raw_data
                )

            logger.info(
                f"Stored attendance record - Device: {device.name}, User: {attendance.user_id}, Time: {timestamp}"
            )
            return True

        await asyncio.to_thread(_do_store)

    async def _update_device_info(self, device: AttendanceDevice, zk_conn: ZK):
        """Update device information fields from connected device.

        Args:
            device: AttendanceDevice instance
            zk_conn: Connected ZK instance
        """

        def _do_update():
            try:
                # Get device serial number
                serial = zk_conn.get_serialnumber()
                if serial:
                    device.serial_number = serial

                # Get device platform (can be used as registration number)
                platform = zk_conn.get_platform()
                if platform:
                    device.registration_number = platform

                # Save updates
                device.save(update_fields=["serial_number", "registration_number", "updated_at"])

                logger.debug(
                    f"Updated device info - Device: {device.name}, "
                    f"Serial: {device.serial_number}, Platform: {device.registration_number}"
                )
            except Exception as e:
                logger.warning(f"Failed to update device info for {device.name}: {str(e)}")

        await asyncio.to_thread(_do_update)

    async def _mark_device_connected(self, device: AttendanceDevice):
        """Mark device as connected in database and re-enable realtime if disabled.

        Args:
            device: AttendanceDevice instance
        """

        def _do_mark():
            device.is_connected = True
            # Re-enable realtime if it was disabled
            if not device.realtime_enabled:
                device.realtime_enabled = True
                device.realtime_disabled_at = None
                logger.info(f"Re-enabled realtime for device {device.name} after successful connection")
            device.save(update_fields=["is_connected", "realtime_enabled", "realtime_disabled_at", "updated_at"])
            logger.info(f"Device {device.name} marked as connected")

        await asyncio.to_thread(_do_mark)

    async def _mark_device_disconnected(self, device: AttendanceDevice):
        """Mark device as disconnected in database.

        Args:
            device: AttendanceDevice instance
        """

        def _do_mark():
            device.is_connected = False
            device.save(update_fields=["is_connected", "updated_at"])
            logger.info(f"Device {device.name} marked as disconnected")

        await asyncio.to_thread(_do_mark)

    async def _disable_realtime_for_device(self, device: AttendanceDevice):
        """Disable realtime listener for device after extended failures.

        Args:
            device: AttendanceDevice instance
        """

        def _do_disable():
            from django.utils import timezone

            device.realtime_enabled = False
            device.realtime_disabled_at = timezone.now()
            device.is_connected = False
            device.save(update_fields=["realtime_enabled", "realtime_disabled_at", "is_connected", "updated_at"])
            logger.critical(
                f"DISABLED realtime listener for device {device.name} (ID: {device.id}) "
                f"after 24 hours of connection failures. Use reconnect action to re-enable."
            )

        await asyncio.to_thread(_do_disable)

    async def _notify_admin_device_offline(self, device: AttendanceDevice, error_msg: str):
        """Notify admin about device being offline after repeated failures.

        Args:
            device: AttendanceDevice instance
            error_msg: Error message to include in notification
        """
        # TODO: Implement admin notification system
        # This could use Django's email system, push notifications, or logging to a monitoring system
        logger.critical(
            f"ADMIN ALERT: Device {device.name} (ID: {device.id}) is offline after "
            f"{MAX_CONSECUTIVE_FAILURES} consecutive failures. Error: {error_msg}"
        )

        # For now, just log the critical error
        # In production, this should:
        # 1. Send email to admins
        # 2. Create a system notification
        # 3. Trigger an alert in monitoring system (e.g., Sentry)
