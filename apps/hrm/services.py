"""Service layer for HRM app business logic."""

import logging
from datetime import datetime
from typing import Any

from django.utils.translation import gettext as _

from apps.devices import DeviceConnectionError, ZKDeviceService
from apps.hrm.models import AttendanceDevice

logger = logging.getLogger(__name__)


# Alias for backwards compatibility
AttendanceDeviceConnectionError = DeviceConnectionError


class AttendanceDeviceService:
    """Service class for managing attendance device operations.

    This is a wrapper around ZKDeviceService from the devices app that works with
    AttendanceDevice model instances and handles business logic.

    Attributes:
        device: AttendanceDevice model instance
        timeout: Connection timeout in seconds (default: 60)
    """

    def __init__(self, device: AttendanceDevice, timeout: int = 60):
        """Initialize service with device instance.

        Args:
            device: AttendanceDevice model instance
            timeout: Connection timeout in seconds
        """
        self.device = device
        self.timeout = timeout
        self._zk_service = ZKDeviceService(
            ip_address=device.ip_address,
            port=device.port,
            password=device.password,
            timeout=timeout,
        )
        # Keep reference for compatibility
        self._zk_connection = None

    def __enter__(self):
        """Context manager entry - establish connection."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close connection."""
        self.disconnect()
        return False

    def connect(self):
        """Establish connection to the attendance device.

        Returns:
            ZK: Connected PyZK instance

        Raises:
            AttendanceDeviceConnectionError: If connection fails
        """
        logger.info(
            f"Attempting to connect to device {self.device.name} at {self.device.ip_address}:{self.device.port}"
        )

        try:
            conn = self._zk_service.connect()
            self._zk_connection = conn
            logger.info(f"Successfully connected to device {self.device.name}")
            return conn

        except DeviceConnectionError as e:
            logger.error(f"Connection error for device {self.device.name}: {str(e)}")
            raise AttendanceDeviceConnectionError(str(e)) from e

    def disconnect(self) -> None:
        """Disconnect from the attendance device."""
        try:
            self._zk_service.disconnect()
            logger.info(f"Disconnected from device {self.device.name}")
        except Exception as e:
            logger.warning(f"Error disconnecting from device {self.device.name}: {str(e)}")
        finally:
            self._zk_connection = None

    def test_connection(self) -> tuple[bool, str]:
        """Test connection to the device.

        Returns:
            tuple[bool, str]: (success, message) tuple indicating connection status
        """
        logger.info(f"Testing connection to device {self.device.name}")
        try:
            return self._zk_service.test_connection()
        except Exception as e:
            logger.error(f"Error during connection test for device {self.device.name}: {str(e)}")
            return False, _("Unexpected error: %(error)s") % {"error": str(e)}

    def get_attendance_logs(self, start_datetime: datetime | None = None) -> list[dict[str, Any]]:
        """Fetch attendance logs from the device.

        Args:
            start_datetime: Optional filter to get logs after this datetime (timezone-aware)

        Returns:
            list[dict]: List of attendance log dictionaries with keys:
                - uid: User ID on device (int)
                - user_id: Attendance code (str)
                - timestamp: Datetime of attendance (datetime)
                - status: Authentication status (int)
                - punch: Punch type (int)

        Raises:
            AttendanceDeviceConnectionError: If connection fails or fetching fails
        """
        logger.info(f"Fetching attendance logs from device {self.device.name}")

        try:
            logs = self._zk_service.get_attendance_logs(start_datetime=start_datetime)
            logger.info(f"Retrieved {len(logs)} attendance logs from device {self.device.name}")
            return logs

        except DeviceConnectionError as e:
            logger.error(f"Error fetching attendance logs from device {self.device.name}: {str(e)}")
            raise AttendanceDeviceConnectionError(str(e)) from e
