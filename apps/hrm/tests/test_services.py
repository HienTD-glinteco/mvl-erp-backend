"""Tests for HRM attendance device service."""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest
from django.test import TestCase

from apps.hrm.models import AttendanceDevice
from apps.hrm.services import AttendanceDeviceConnectionError, AttendanceDeviceService


class MockAttendance:
    """Mock attendance object from PyZK."""

    def __init__(self, uid, user_id, timestamp, status, punch):
        """Initialize mock attendance."""
        self.uid = uid
        self.user_id = user_id
        self.timestamp = timestamp
        self.status = status
        self.punch = punch


@pytest.mark.django_db
class TestAttendanceDeviceService(TestCase):
    """Test cases for AttendanceDeviceService."""

    def setUp(self):
        """Set up test data."""
        self.device = AttendanceDevice.objects.create(
            name="Test Device",
            location="Main Office",
            ip_address="192.168.1.100",
            port=4370,
            password="admin123",
        )

    @patch("apps.hrm.services.ZK")
    def test_connect_success(self, mock_zk_class):
        """Test successful connection to device."""
        # Arrange
        mock_zk_instance = Mock()
        mock_conn = Mock()
        mock_zk_instance.connect.return_value = mock_conn
        mock_zk_class.return_value = mock_zk_instance

        service = AttendanceDeviceService(self.device)

        # Act
        conn = service.connect()

        # Assert
        self.assertIsNotNone(conn)
        self.assertEqual(conn, mock_conn)
        mock_zk_class.assert_called_once_with(
            "192.168.1.100",
            port=4370,
            timeout=5,
            password="admin123",
            ommit_ping=False,
        )
        mock_zk_instance.connect.assert_called_once()

    @patch("apps.hrm.services.ZK")
    def test_connect_network_error(self, mock_zk_class):
        """Test connection failure due to network error."""
        # Arrange
        from zk.exception import ZKErrorConnection

        mock_zk_instance = Mock()
        mock_zk_instance.connect.side_effect = ZKErrorConnection("Network unreachable")
        mock_zk_class.return_value = mock_zk_instance

        service = AttendanceDeviceService(self.device)

        # Act & Assert
        with self.assertRaises(AttendanceDeviceConnectionError) as context:
            service.connect()

        self.assertIn("Network connection error", str(context.exception))

    @patch("apps.hrm.services.ZK")
    def test_connect_response_error(self, mock_zk_class):
        """Test connection failure due to device response error."""
        # Arrange
        from zk.exception import ZKErrorResponse

        mock_zk_instance = Mock()
        mock_zk_instance.connect.side_effect = ZKErrorResponse("Invalid response")
        mock_zk_class.return_value = mock_zk_instance

        service = AttendanceDeviceService(self.device)

        # Act & Assert
        with self.assertRaises(AttendanceDeviceConnectionError) as context:
            service.connect()

        self.assertIn("Device response error", str(context.exception))

    @patch("apps.hrm.services.ZK")
    def test_connect_returns_none(self, mock_zk_class):
        """Test connection failure when connect returns None."""
        # Arrange
        mock_zk_instance = Mock()
        mock_zk_instance.connect.return_value = None
        mock_zk_class.return_value = mock_zk_instance

        service = AttendanceDeviceService(self.device)

        # Act & Assert
        with self.assertRaises(AttendanceDeviceConnectionError) as context:
            service.connect()

        self.assertIn("Failed to establish connection", str(context.exception))

    @patch("apps.hrm.services.ZK")
    def test_disconnect_success(self, mock_zk_class):
        """Test successful disconnection."""
        # Arrange
        mock_zk_instance = Mock()
        mock_conn = Mock()
        mock_zk_instance.connect.return_value = mock_conn
        mock_zk_class.return_value = mock_zk_instance

        service = AttendanceDeviceService(self.device)
        service.connect()

        # Act
        service.disconnect()

        # Assert
        mock_conn.disconnect.assert_called_once()
        self.assertIsNone(service._zk_connection)

    @patch("apps.hrm.services.ZK")
    def test_disconnect_with_error(self, mock_zk_class):
        """Test disconnection handles errors gracefully."""
        # Arrange
        mock_zk_instance = Mock()
        mock_conn = Mock()
        mock_conn.disconnect.side_effect = Exception("Disconnect error")
        mock_zk_instance.connect.return_value = mock_conn
        mock_zk_class.return_value = mock_zk_instance

        service = AttendanceDeviceService(self.device)
        service.connect()

        # Act - should not raise exception
        service.disconnect()

        # Assert
        self.assertIsNone(service._zk_connection)

    @patch("apps.hrm.services.ZK")
    def test_context_manager(self, mock_zk_class):
        """Test using service as context manager."""
        # Arrange
        mock_zk_instance = Mock()
        mock_conn = Mock()
        mock_zk_instance.connect.return_value = mock_conn
        mock_zk_class.return_value = mock_zk_instance

        # Act
        with AttendanceDeviceService(self.device) as service:
            # Assert - connection is established
            self.assertIsNotNone(service._zk_connection)

        # Assert - connection is closed after exiting context
        mock_conn.disconnect.assert_called_once()

    @patch("apps.hrm.services.ZK")
    def test_test_connection_success(self, mock_zk_class):
        """Test connection test with successful result."""
        # Arrange
        mock_zk_instance = Mock()
        mock_conn = Mock()
        mock_conn.get_firmware_version.return_value = "6.60"
        mock_zk_instance.connect.return_value = mock_conn
        mock_zk_class.return_value = mock_zk_instance

        service = AttendanceDeviceService(self.device)

        # Act
        success, message = service.test_connection()

        # Assert
        self.assertTrue(success)
        self.assertIn("6.60", message)
        self.assertIn("successful", message.lower())

    @patch("apps.hrm.services.ZK")
    def test_test_connection_failure(self, mock_zk_class):
        """Test connection test with failed result."""
        # Arrange
        from zk.exception import ZKErrorConnection

        mock_zk_instance = Mock()
        mock_zk_instance.connect.side_effect = ZKErrorConnection("Connection failed")
        mock_zk_class.return_value = mock_zk_instance

        service = AttendanceDeviceService(self.device)

        # Act
        success, message = service.test_connection()

        # Assert
        self.assertFalse(success)
        self.assertIn("Connection failed", message)

    @patch("apps.hrm.services.ZK")
    def test_get_attendance_logs_success(self, mock_zk_class):
        """Test fetching attendance logs successfully."""
        # Arrange
        mock_zk_instance = Mock()
        mock_conn = Mock()
        mock_zk_instance.connect.return_value = mock_conn

        # Create mock attendance records
        now = datetime.now(timezone.utc)
        mock_attendances = [
            MockAttendance(1, "100", now, 1, 0),
            MockAttendance(2, "200", now - timedelta(hours=1), 1, 0),
            MockAttendance(3, "300", now - timedelta(hours=2), 1, 0),
        ]
        mock_conn.get_attendance.return_value = mock_attendances
        mock_zk_class.return_value = mock_zk_instance

        service = AttendanceDeviceService(self.device)
        service.connect()

        # Act
        logs = service.get_attendance_logs()

        # Assert
        self.assertEqual(len(logs), 3)
        self.assertEqual(logs[0]["user_id"], "100")
        self.assertEqual(logs[0]["uid"], 1)
        self.assertEqual(logs[1]["user_id"], "200")
        self.assertEqual(logs[2]["user_id"], "300")

    @patch("apps.hrm.services.ZK")
    def test_get_attendance_logs_with_filter(self, mock_zk_class):
        """Test fetching attendance logs with datetime filter."""
        # Arrange
        mock_zk_instance = Mock()
        mock_conn = Mock()
        mock_zk_instance.connect.return_value = mock_conn

        now = datetime.now(timezone.utc)
        filter_time = now - timedelta(hours=1, minutes=30)

        mock_attendances = [
            MockAttendance(1, "100", now, 1, 0),  # Should be included
            MockAttendance(2, "200", now - timedelta(hours=1), 1, 0),  # Should be included
            MockAttendance(3, "300", now - timedelta(hours=3), 1, 0),  # Should be excluded
        ]
        mock_conn.get_attendance.return_value = mock_attendances
        mock_zk_class.return_value = mock_zk_instance

        service = AttendanceDeviceService(self.device)
        service.connect()

        # Act
        logs = service.get_attendance_logs(start_datetime=filter_time)

        # Assert
        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[0]["user_id"], "100")
        self.assertEqual(logs[1]["user_id"], "200")

    @patch("apps.hrm.services.ZK")
    def test_get_attendance_logs_empty(self, mock_zk_class):
        """Test fetching attendance logs when device has no logs."""
        # Arrange
        mock_zk_instance = Mock()
        mock_conn = Mock()
        mock_conn.get_attendance.return_value = []
        mock_zk_instance.connect.return_value = mock_conn
        mock_zk_class.return_value = mock_zk_instance

        service = AttendanceDeviceService(self.device)
        service.connect()

        # Act
        logs = service.get_attendance_logs()

        # Assert
        self.assertEqual(len(logs), 0)

    @patch("apps.hrm.services.ZK")
    def test_get_attendance_logs_not_connected(self, mock_zk_class):
        """Test fetching attendance logs without connection."""
        # Arrange
        service = AttendanceDeviceService(self.device)

        # Act & Assert
        with self.assertRaises(AttendanceDeviceConnectionError) as context:
            service.get_attendance_logs()

        self.assertIn("not connected", str(context.exception).lower())

    @patch("apps.hrm.services.ZK")
    def test_get_attendance_logs_handles_naive_timestamps(self, mock_zk_class):
        """Test that naive timestamps are converted to timezone-aware."""
        # Arrange
        mock_zk_instance = Mock()
        mock_conn = Mock()
        mock_zk_instance.connect.return_value = mock_conn

        # Create attendance with naive datetime
        naive_dt = datetime(2025, 10, 28, 12, 0, 0)
        mock_attendances = [MockAttendance(1, "100", naive_dt, 1, 0)]
        mock_conn.get_attendance.return_value = mock_attendances
        mock_zk_class.return_value = mock_zk_instance

        service = AttendanceDeviceService(self.device)
        service.connect()

        # Act
        logs = service.get_attendance_logs()

        # Assert
        self.assertEqual(len(logs), 1)
        self.assertIsNotNone(logs[0]["timestamp"].tzinfo)
        self.assertEqual(logs[0]["timestamp"].tzinfo, timezone.utc)

    @patch("apps.hrm.services.ZK")
    def test_custom_timeout(self, mock_zk_class):
        """Test service with custom timeout."""
        # Arrange
        mock_zk_instance = Mock()
        mock_conn = Mock()
        mock_zk_instance.connect.return_value = mock_conn
        mock_zk_class.return_value = mock_zk_instance

        # Act
        service = AttendanceDeviceService(self.device, timeout=10)
        service.connect()

        # Assert
        mock_zk_class.assert_called_once_with(
            "192.168.1.100",
            port=4370,
            timeout=10,
            password="admin123",
            ommit_ping=False,
        )

    @patch("apps.hrm.services.ZK")
    def test_device_without_password(self, mock_zk_class):
        """Test connection to device without password."""
        # Arrange
        device_no_pass = AttendanceDevice.objects.create(
            name="No Password Device",
            ip_address="192.168.1.101",
            password="",
        )

        mock_zk_instance = Mock()
        mock_conn = Mock()
        mock_zk_instance.connect.return_value = mock_conn
        mock_zk_class.return_value = mock_zk_instance

        service = AttendanceDeviceService(device_no_pass)

        # Act
        service.connect()

        # Assert - password should be 0 when empty string
        mock_zk_class.assert_called_once_with(
            "192.168.1.101",
            port=4370,
            timeout=5,
            password=0,
            ommit_ping=False,
        )
