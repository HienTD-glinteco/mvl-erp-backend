"""ZK Device Service for managing attendance device operations using PyZK.

This module provides low-level device communication functionality without
any business logic or database operations.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from django.utils.translation import gettext as _
from django.utils.timezone import get_current_timezone
from zk import ZK
from zk.exception import ZKErrorConnection, ZKErrorResponse

from apps.devices.exceptions import DeviceConnectionError

logger = logging.getLogger(__name__)


class ZKDeviceService:
    """Service class for managing ZK attendance device operations.

    This service provides methods to:
    - Connect to attendance devices
    - Test device connectivity
    - Fetch attendance logs from devices
    - Handle connection errors and retries

    This class is pure device communication - no business logic or DB operations.

    Attributes:
        ip_address: Device IP address
        port: Device port number
        password: Device password (optional)
        timeout: Connection timeout in seconds
    """

    def __init__(
        self,
        ip_address: str,
        port: int = 4370,
        password: str | int | None = None,
        timeout: int = 60,
    ):
        """Initialize service with device connection parameters.

        Args:
            ip_address: Device IP address
            port: Device port number (default: 4370)
            password: Device password (optional)
            timeout: Connection timeout in seconds (default: 60)
        """
        self.ip_address = ip_address
        self.port = port
        self.password = password or 0
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
            DeviceConnectionError: If connection fails
        """
        logger.info(f"Attempting to connect to device at {self.ip_address}:{self.port}")

        try:
            # Create ZK instance
            zk = ZK(
                self.ip_address,
                port=self.port,
                timeout=self.timeout,
                password=self.password,
                ommit_ping=False,
            )

            # Attempt connection
            conn = zk.connect()
            if not conn:
                raise DeviceConnectionError(_("Failed to establish connection to device"))

            self._zk_connection = conn
            logger.info(f"Successfully connected to device at {self.ip_address}")

            return conn

        except ZKErrorConnection as e:
            error_msg = _("Network connection error: %(error)s") % {"error": str(e)}
            logger.error(f"Connection error for device at {self.ip_address}: {str(e)}")
            raise DeviceConnectionError(error_msg) from e

        except ZKErrorResponse as e:
            error_msg = _("Device response error: %(error)s") % {"error": str(e)}
            logger.error(f"Response error from device at {self.ip_address}: {str(e)}")
            raise DeviceConnectionError(error_msg) from e

        except Exception as e:
            error_msg = _("Unexpected error: %(error)s") % {"error": str(e)}
            logger.error(f"Unexpected error connecting to device at {self.ip_address}: {str(e)}")
            raise DeviceConnectionError(error_msg) from e

    def disconnect(self) -> None:
        """Disconnect from the attendance device."""
        if self._zk_connection:
            try:
                self._zk_connection.disconnect()
                logger.info(f"Disconnected from device at {self.ip_address}")
            except Exception as e:
                logger.warning(f"Error disconnecting from device at {self.ip_address}: {str(e)}")
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
                    logger.info(f"Connection test passed for device at {self.ip_address}")
                    return True, success_msg

                return False, _("Connection object is None")

        except DeviceConnectionError as e:
            logger.error(f"Connection test failed for device at {self.ip_address}: {str(e)}")
            return False, str(e)

        except Exception as e:
            logger.error(f"Unexpected error during connection test for device at {self.ip_address}: {str(e)}")
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
            DeviceConnectionError: If connection fails or fetching fails
        """
        if not self._zk_connection:
            raise DeviceConnectionError(_("Device not connected. Call connect() first."))

        logger.info(f"Fetching attendance logs from device at {self.ip_address}")

        try:
            # Get all attendance records from device
            attendances = self._zk_connection.get_attendance()

            if not attendances:
                logger.info(f"No attendance logs found on device at {self.ip_address}")
                return []

            # Convert to list of dictionaries
            logs = []
            for att in attendances:
                # Ensure timestamp is timezone-aware
                att_timestamp = att.timestamp
                if att_timestamp.tzinfo is None:
                    # Assume device time is in UTC if no timezone info
                    att_timestamp = att_timestamp.replace(tzinfo=timezone.utc)
                else:
                    # Force replace tzinfo with current timezone without converting the instant
                    att_timestamp = att_timestamp.replace(tzinfo=get_current_timezone())

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

            logger.info(f"Retrieved {len(logs)} attendance logs from device at {self.ip_address}")
            return logs

        except Exception as e:
            error_msg = _("Failed to fetch attendance logs: %(error)s") % {"error": str(e)}
            logger.error(f"Error fetching attendance logs from device at {self.ip_address}: {str(e)}")
            raise DeviceConnectionError(error_msg) from e

    def get_device_info(self) -> dict[str, Any]:
        """Get device information.

        Returns:
            dict: Device information including serial number, firmware, etc.

        Raises:
            DeviceConnectionError: If connection fails or operation fails
        """
        if not self._zk_connection:
            raise DeviceConnectionError(_("Device not connected. Call connect() first."))

        try:
            info = {
                "serial_number": self._zk_connection.get_serialnumber() or "",
                "registration_number": self._zk_connection.get_device_name() or "",
                "firmware_version": self._zk_connection.get_firmware_version() or "",
            }
            return info

        except Exception as e:
            error_msg = _("Failed to get device info: %(error)s") % {"error": str(e)}
            logger.error(f"Error getting device info from {self.ip_address}: {str(e)}")
            raise DeviceConnectionError(error_msg) from e
