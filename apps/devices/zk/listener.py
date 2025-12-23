"""Realtime attendance listener for capturing live events from attendance devices.

This module provides functionality to maintain persistent connections to attendance
devices and capture attendance events in realtime using PyZK's live_capture feature.

This is a pure event capture system - it does NOT handle business logic or database operations.
Event handlers are provided via callbacks.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

from django.utils import timezone
from zk import ZK
from zk.attendance import Attendance
from zk.exception import ZKErrorConnection, ZKErrorResponse, ZKNetworkError

logger = logging.getLogger(__name__)

# Configuration constants
DEFAULT_LIVE_CAPTURE_TIMEOUT = 60
RECONNECT_BASE_DELAY = 5
RECONNECT_MAX_DELAY = 300
RECONNECT_BACKOFF_MULTIPLIER = 2
MAX_CONSECUTIVE_FAILURES = 5
MAX_RETRY_DURATION = 86400  # 1 day in seconds (stop retrying after this)
DEVICE_INFO_UPDATE_INTERVAL = 300  # Update device info every 5 minutes
DEVICE_CHECK_INTERVAL = 60  # Check for new/enabled devices every 60 seconds


class ZKDeviceInfo:
    """Simple data class for ZK device information."""

    def __init__(
        self,
        device_id: int,
        name: str,
        ip_address: str,
        port: int,
        password: str | int | None = None,
    ):
        self.device_id = device_id
        self.name = name
        self.ip_address = ip_address
        self.port = port
        self.password = password or 0


class ZKAttendanceEvent:
    """Data class for ZK attendance events."""

    def __init__(
        self,
        device_id: int,
        device_name: str,
        user_id: str,
        uid: int,
        timestamp: datetime,
        status: int,
        punch: int,
    ):
        self.device_id = device_id
        self.device_name = device_name
        self.user_id = user_id
        self.uid = uid
        self.timestamp = timestamp
        self.status = status
        self.punch = punch

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "device_id": self.device_id,
            "device_name": self.device_name,
            "user_id": self.user_id,
            "uid": self.uid,
            "timestamp": self.timestamp,
            "status": self.status,
            "punch": self.punch,
        }


class ZKRealtimeDeviceListener:
    """Manages realtime attendance event capture from multiple ZK devices concurrently.

    This class handles:
    - Concurrent connections to multiple ZK attendance devices
    - Live event capture via callbacks
    - Automatic reconnection with exponential backoff
    - Error handling and device status tracking

    Business logic (DB operations, notifications, etc.) is handled via callbacks.
    """

    def __init__(
        self,
        get_devices_callback: Callable[[], list[ZKDeviceInfo]],
        on_attendance_event: Callable[[ZKAttendanceEvent], Any],
        on_device_connected: Callable[[int, dict[str, Any]], Any] | None = None,
        on_device_disconnected: Callable[[int], Any] | None = None,
        on_device_error: Callable[[int, str, int], Any] | None = None,
        on_device_disabled: Callable[[int], Any] | None = None,
        max_workers: int = 50,
    ):
        """Initialize the realtime listener.

        Args:
            get_devices_callback: Function to get list of enabled devices
            on_attendance_event: Callback for attendance events (required)
            on_device_connected: Callback when device connects successfully
            on_device_disconnected: Callback when device disconnects
            on_device_error: Callback for device errors (device_id, error_msg, consecutive_failures)
            on_device_disabled: Callback when device is disabled due to prolonged failures
            max_workers: Maximum number of worker threads for device connections (default: 50)
        """
        self._get_devices = get_devices_callback
        self._on_attendance_event = on_attendance_event
        self._on_device_connected = on_device_connected
        self._on_device_disconnected = on_device_disconnected
        self._on_device_error = on_device_error
        self._on_device_disabled = on_device_disabled
        self.max_workers = max_workers

        self._device_tasks: dict[int, asyncio.Task] = {}
        self._registered_device_ids: set[int] = set()  # Track currently registered devices
        self._running = False
        self._shutdown_event = asyncio.Event()

        # Dual executors
        self._listener_executor: ThreadPoolExecutor | None = None
        self._general_executor: ThreadPoolExecutor | None = None

    async def start(self):
        """Start the realtime listener for all enabled devices."""
        logger.info("Starting realtime attendance listener")
        self._running = True
        self._shutdown_event.clear()

        # Initialize thread pool executors
        # Listener executor needs one thread per device + buffer
        self._listener_executor = ThreadPoolExecutor(max_workers=self.max_workers + 10, thread_name_prefix="zk_listen")
        # General executor for connection/disconnection/info tasks
        self._general_executor = ThreadPoolExecutor(max_workers=20, thread_name_prefix="zk_gen")

        # Start initial devices
        await self._check_and_start_devices()

        # Create a background task to periodically check for new devices
        device_checker_task = asyncio.create_task(self._periodic_device_checker())

        # Wait for shutdown signal
        await self._shutdown_event.wait()

        # Cancel the device checker task
        device_checker_task.cancel()
        try:
            await device_checker_task
        except asyncio.CancelledError:
            pass

    async def _run_blocking(self, func: Callable, *args):
        """Run a blocking function in the general thread pool executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._general_executor, func, *args)

    async def _periodic_device_checker(self):
        """Periodically check for new or re-enabled devices and start listeners for them."""
        while self._running:
            try:
                await asyncio.sleep(DEVICE_CHECK_INTERVAL)
                if self._running:
                    await self._check_and_start_devices()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic device checker: {str(e)}")

    async def _check_and_start_devices(self):
        """Check for enabled devices and start listeners for any that aren't already running.

        Also removes devices that were previously registered but are no longer enabled.
        """
        # Get all enabled devices via callback
        devices = await self._run_blocking(self._get_devices)

        # Build set of currently enabled device IDs
        enabled_device_ids = {device.device_id for device in devices}

        # Remove devices that are no longer enabled
        devices_to_remove = self._registered_device_ids - enabled_device_ids
        for device_id in devices_to_remove:
            if device_id in self._device_tasks:
                task = self._device_tasks[device_id]
                if not task.done():
                    task.cancel()
                    logger.info(f"Cancelled listener task for disabled device ID: {device_id}")
                del self._device_tasks[device_id]
            logger.info(f"Removed disabled device ID {device_id} from registered devices")

        # Update the registered device IDs
        self._registered_device_ids = enabled_device_ids.copy()

        # Find devices that need listeners started
        for device in devices:
            # Skip if already has a running task
            if device.device_id in self._device_tasks:
                task = self._device_tasks[device.device_id]
                # Check if task is still running
                if not task.done():
                    continue
                # Task finished (likely disabled), remove it
                del self._device_tasks[device.device_id]

            # Start new listener task for this device
            task = asyncio.create_task(self._device_listener_loop(device))
            self._device_tasks[device.device_id] = task
            logger.info(f"Started listener task for device: {device.name} (ID: {device.device_id})")

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

        # Shutdown executors
        if self._listener_executor:
            self._listener_executor.shutdown(wait=False)
            self._listener_executor = None

        if self._general_executor:
            self._general_executor.shutdown(wait=False)
            self._general_executor = None

        logger.info("Realtime attendance listener stopped")

    async def _device_listener_loop(self, device: ZKDeviceInfo):
        """Main loop for a single device listener with retry logic.

        Args:
            device: DeviceInfo instance to monitor
        """
        consecutive_failures = 0
        reconnect_delay = RECONNECT_BASE_DELAY
        last_device_info_update: float = 0
        first_failure_time = None  # Track when failures started

        zk_conn = None

        # Create a function to run the blocking live capture loop
        # We capture the main loop here to pass it to the blocking function
        main_loop = asyncio.get_running_loop()

        def _run_blocking_capture(connection, last_update):
            return self._live_capture_loop_blocking(device, connection, last_update, main_loop)

        while self._running:
            try:
                logger.info(f"Connecting to device: {device.name} at {device.ip_address}:{device.port}")

                # Connect to device (uses general executor)
                zk_conn = await self._connect_device(device)

                # Get device info and notify via callback (uses general executor)
                device_info = await self._get_device_info(zk_conn)
                await self._safe_call(self._on_device_connected, device.device_id, device_info)

                last_device_info_update = time.time()

                # Reset failure counter and timer on successful connection
                consecutive_failures = 0
                first_failure_time = None
                reconnect_delay = RECONNECT_BASE_DELAY

                logger.info(f"Successfully connected to device: {device.name}, starting live capture")

                # Run the live capture loop in the dedicated listener executor
                # This blocks one thread in the listener pool for the duration of the connection
                await main_loop.run_in_executor(
                    self._listener_executor, _run_blocking_capture, zk_conn, last_device_info_update
                )

            except (ZKErrorConnection, ZKErrorResponse, ConnectionError, ZKNetworkError) as e:
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
                        f"Requesting disable of realtime listener for this device."
                    )
                    await self._safe_call(self._on_device_disabled, device.device_id)
                    # Exit the loop for this device
                    break

                logger.warning(
                    f"{error_msg} (failure {consecutive_failures}/{MAX_CONSECUTIVE_FAILURES}, "
                    f"retrying for {time_since_first_failure / 3600:.1f} hours)"
                )

                # If consecutive failures exceed limit, disable device
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    logger.critical(
                        f"Device {device.name} has exceeded {MAX_CONSECUTIVE_FAILURES} consecutive failures. "
                        f"Requesting disable of realtime listener for this device."
                    )
                    await self._safe_call(self._on_device_disabled, device.device_id)
                    # Exit the loop for this device
                    break

                # Notify disconnection and error via callbacks (safe)
                await self._safe_call(self._on_device_disconnected, device.device_id)
                await self._safe_call(self._on_device_error, device.device_id, error_msg, consecutive_failures)

            except Exception as e:
                logger.exception(f"Unexpected error in listener loop for device {device.name}: {str(e)}")
                await self._safe_call(self._on_device_disconnected, device.device_id)

            finally:
                # Clean up connection if it exists
                if zk_conn:
                    await self._disconnect_device(device, zk_conn)

            # Check if device is still registered before retrying
            if device.device_id not in self._registered_device_ids:
                logger.info(
                    f"Device {device.name} (ID: {device.device_id}) is no longer registered. Stopping retry attempts."
                )
                break

            # Wait before reconnecting (exponential backoff)
            if self._running:
                logger.info(f"Reconnecting to device {device.name} in {reconnect_delay} seconds")
                await asyncio.sleep(reconnect_delay)

                # Increase delay for next retry (exponential backoff)
                reconnect_delay = min(reconnect_delay * RECONNECT_BACKOFF_MULTIPLIER, RECONNECT_MAX_DELAY)

    async def _connect_device(self, device: ZKDeviceInfo) -> ZK:
        """Connect to an attendance device.

        Args:
            device: DeviceInfo instance

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
                password=device.password,
                ommit_ping=False,
            )
            conn = zk.connect()
            if not conn:
                raise ConnectionError("Failed to establish connection")
            return conn

        return await self._run_blocking(_do_connect)

    async def _disconnect_device(self, device: ZKDeviceInfo, zk_conn: ZK):
        """Disconnect from an attendance device.

        Args:
            device: DeviceInfo instance
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

        await self._run_blocking(_do_disconnect)

    async def _get_device_info(self, zk_conn: ZK) -> dict[str, Any]:
        """Get device information from connected device.

        Args:
            zk_conn: Connected ZK instance

        Returns:
            Dictionary with device info
        """

        def _do_get_info():
            try:
                return {
                    "serial_number": zk_conn.get_serialnumber() or "",
                    "registration_number": zk_conn.get_device_name() or "",
                    "firmware_version": zk_conn.get_firmware_version() or "",
                }
            except Exception as e:
                logger.warning(f"Error getting device info: {str(e)}")
                return {}

        return await self._run_blocking(_do_get_info)

    async def _safe_call(self, callback, *args, **kwargs):
        """Safely call a callback (sync or async).

        Swallows exceptions from the callback and logs them.
        """
        if not callback:
            return
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args, **kwargs)
            else:
                await self._run_blocking(callback, *args, **kwargs)
        except Exception as e:
            try:
                name = getattr(callback, "__name__", str(callback))
            except Exception:
                name = str(callback)
            logger.exception(f"Callback {name} raised an exception: {e}")

    def _live_capture_loop_blocking(
        self, device: ZKDeviceInfo, zk_conn: ZK, last_info_update: float, main_loop: asyncio.AbstractEventLoop
    ):
        """Run the live capture loop in a blocking way (to be run in a thread).

        This replaces the async generator approach to avoid context switching overhead
        and thread starvation.

        Args:
            device: DeviceInfo instance
            zk_conn: Connected ZK instance
            last_info_update: Timestamp of last device info update
            main_loop: Reference to the main asyncio loop for dispatching events
        """
        logger.debug(f"Starting blocking capture loop for device {device.name}")

        try:
            for attendance in zk_conn.live_capture(new_timeout=DEFAULT_LIVE_CAPTURE_TIMEOUT):
                # Check if we should stop (thread-safe boolean check)
                if not self._running:
                    break

                if hasattr(zk_conn, "end_live_capture") and zk_conn.end_live_capture:
                    break

                # Update device info periodically (also dispatch to main loop)
                current_time = time.time()
                if current_time - last_info_update >= DEVICE_INFO_UPDATE_INTERVAL:
                    try:
                        info = {
                            "serial_number": zk_conn.get_serialnumber() or "",
                            "registration_number": zk_conn.get_device_name() or "",
                            "firmware_version": zk_conn.get_firmware_version() or "",
                        }
                        if self._on_device_connected:
                            # Schedule callback on main loop
                            asyncio.run_coroutine_threadsafe(
                                self._safe_call(self._on_device_connected, device.device_id, info), main_loop
                            )
                        last_info_update = current_time
                    except Exception as e:
                        logger.warning(f"Error updating device info in loop: {e}")

                # None means timeout, continue waiting
                if attendance is None:
                    continue

                # Process the event
                # We need to dispatch this to the main loop to be processed asynchronously
                # Create a coroutine object
                coro = self._process_attendance_event(device, attendance)
                # Schedule it
                asyncio.run_coroutine_threadsafe(coro, main_loop)

        except Exception as e:
            logger.error(f"Error in live capture loop for device {device.name}: {str(e)}")
            # We raise so the outer loop handles the error (retry logic)
            raise

    async def _process_attendance_event(self, device: ZKDeviceInfo, attendance: Attendance):
        """Process a single attendance event by calling the event handler.

        Args:
            device: DeviceInfo that captured the event
            attendance: Attendance object from PyZK
        """
        try:
            # Ensure timestamp is timezone-aware
            timestamp = attendance.timestamp
            if timezone.is_naive(timestamp):
                timestamp = timezone.make_aware(timestamp)

            # Create event object
            event = ZKAttendanceEvent(
                device_id=device.device_id,
                device_name=device.name,
                user_id=attendance.user_id,
                uid=attendance.uid,
                timestamp=timestamp,
                status=attendance.status,
                punch=attendance.punch,
            )

            # Call the event handler callback
            if asyncio.iscoroutinefunction(self._on_attendance_event):
                await self._on_attendance_event(event)
            else:
                await self._run_blocking(self._on_attendance_event, event)

            logger.info(
                f"Processed attendance event - Device: {device.name}, User: {attendance.user_id}, Time: {timestamp}"
            )

        except Exception as e:
            logger.error(
                f"Error processing attendance event from device {device.name}: {str(e)}, "
                f"Event: user_id={attendance.user_id}, timestamp={attendance.timestamp}"
            )
