"""Service layer for HRM app business logic."""

import logging
from datetime import datetime, timezone
from typing import Any

from django.utils.translation import gettext as _
from zk import ZK
from zk.exception import ZKErrorConnection, ZKErrorResponse

from apps.hrm.models import AttendanceDevice

logger = logging.getLogger(__name__)


class AttendanceDeviceConnectionError(Exception):
    """Exception raised when connection to attendance device fails."""

    pass


class AttendanceDeviceService:
    """Service class for managing attendance device operations using PyZK.

    This service provides methods to:
    - Connect to attendance devices
    - Test device connectivity
    - Fetch attendance logs from devices
    - Handle connection errors and retries

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
        self._zk_connection: ZK | None = None

    def __enter__(self):
        """Context manager entry - establish connection."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close connection."""
        self.disconnect()
        return False

    def connect(self) -> ZK:
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
            # Create ZK instance
            zk = ZK(
                self.device.ip_address,
                port=self.device.port,
                timeout=self.timeout,
                password=self.device.password or 0,
                ommit_ping=False,
            )

            # Attempt connection
            conn = zk.connect()
            if not conn:
                raise AttendanceDeviceConnectionError(_("Failed to establish connection to device"))

            self._zk_connection = conn
            logger.info(f"Successfully connected to device {self.device.name}")

            return conn

        except ZKErrorConnection as e:
            error_msg = _("Network connection error: %(error)s") % {"error": str(e)}
            logger.error(f"Connection error for device {self.device.name}: {str(e)}")
            raise AttendanceDeviceConnectionError(error_msg) from e

        except ZKErrorResponse as e:
            error_msg = _("Device response error: %(error)s") % {"error": str(e)}
            logger.error(f"Response error from device {self.device.name}: {str(e)}")
            raise AttendanceDeviceConnectionError(error_msg) from e

        except Exception as e:
            error_msg = _("Unexpected error: %(error)s") % {"error": str(e)}
            logger.error(f"Unexpected error connecting to device {self.device.name}: {str(e)}")
            raise AttendanceDeviceConnectionError(error_msg) from e

    def disconnect(self) -> None:
        """Disconnect from the attendance device."""
        if self._zk_connection:
            try:
                self._zk_connection.disconnect()
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
        try:
            with self:
                # Try to get device info to verify connection works
                if self._zk_connection:
                    # Get basic device info
                    firmware = self._zk_connection.get_firmware_version()
                    success_msg = _("Connection successful. Firmware: %(firmware)s") % {"firmware": firmware}
                    logger.info(f"Connection test passed for device {self.device.name}")
                    return True, success_msg

                return False, _("Connection object is None")

        except AttendanceDeviceConnectionError as e:
            logger.error(f"Connection test failed for device {self.device.name}: {str(e)}")
            return False, str(e)

        except Exception as e:
            logger.error(f"Unexpected error during connection test for device {self.device.name}: {str(e)}")
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
                - punch: Punch type (int) - ignored in current implementation

        Raises:
            AttendanceDeviceConnectionError: If connection fails or fetching fails
        """
        if not self._zk_connection:
            raise AttendanceDeviceConnectionError(_("Device not connected. Call connect() first."))

        logger.info(f"Fetching attendance logs from device {self.device.name}")

        try:
            # Get all attendance records from device
            attendances = self._zk_connection.get_attendance()

            if not attendances:
                logger.info(f"No attendance logs found on device {self.device.name}")
                return []

            # Convert to list of dictionaries
            logs = []
            for att in attendances:
                # Ensure timestamp is timezone-aware
                att_timestamp = att.timestamp
                if att_timestamp.tzinfo is None:
                    # Assume device time is in UTC if no timezone info
                    att_timestamp = att_timestamp.replace(tzinfo=timezone.utc)

                # Filter by start_datetime if provided
                if start_datetime and att_timestamp < start_datetime:
                    continue

                log_entry = {
                    "uid": att.uid,
                    "user_id": att.user_id,
                    "timestamp": att_timestamp,
                    "status": att.status,
                    "punch": att.punch,
                }
                logs.append(log_entry)

            logger.info(f"Retrieved {len(logs)} attendance logs from device {self.device.name}")
            return logs

        except Exception as e:
            error_msg = _("Failed to fetch attendance logs: %(error)s") % {"error": str(e)}
            logger.error(f"Error fetching attendance logs from device {self.device.name}: {str(e)}")
            raise AttendanceDeviceConnectionError(error_msg) from e
