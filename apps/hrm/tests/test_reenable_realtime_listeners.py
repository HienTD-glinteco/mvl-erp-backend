"""Tests for check_and_reenable_realtime_listeners Celery task."""

from unittest.mock import patch

import pytest

from apps.hrm.models import AttendanceDevice
from apps.hrm.tasks.attendances import check_and_reenable_realtime_listeners


@pytest.mark.django_db
class TestCheckAndReenableRealtimeListeners:
    """Test cases for check_and_reenable_realtime_listeners task."""

    def test_no_devices_to_reenable(self):
        """Test when there are no devices that need re-enabling."""
        # Arrange - Create a device that is enabled and has realtime enabled
        AttendanceDevice.objects.create(
            name="Enabled Device",
            ip_address="192.168.1.100",
            port=4370,
            is_enabled=True,
            realtime_enabled=True,
        )

        # Act
        result = check_and_reenable_realtime_listeners()

        # Assert
        assert result["total_devices_checked"] == 0
        assert result["reenabled_count"] == 0
        assert result["results"] == []

    def test_device_disabled_not_checked(self):
        """Test that disabled devices are not checked."""
        # Arrange - Create a disabled device with realtime disabled
        AttendanceDevice.objects.create(
            name="Disabled Device",
            ip_address="192.168.1.100",
            port=4370,
            is_enabled=False,
            realtime_enabled=False,
        )

        # Act
        result = check_and_reenable_realtime_listeners()

        # Assert - Should not check disabled devices
        assert result["total_devices_checked"] == 0
        assert result["reenabled_count"] == 0

    @patch("apps.hrm.models.attendance_device.ZKDeviceService")
    def test_reenable_device_success(self, mock_service):
        """Test successfully re-enabling a device."""
        # Arrange - Create enabled device with realtime disabled
        device = AttendanceDevice.objects.create(
            name="Test Device",
            ip_address="192.168.1.100",
            port=4370,
            is_enabled=True,
            realtime_enabled=False,
            is_connected=False,
        )

        # Mock successful connection
        mock_instance = mock_service.return_value
        mock_instance._zk_connection = True
        mock_instance.get_device_info.return_value = {
            "serial_number": "SN123",
            "firmware_version": "6.60",
        }
        mock_instance.__enter__ = lambda self: self
        mock_instance.__exit__ = lambda self, *args: None

        # Act
        result = check_and_reenable_realtime_listeners()

        # Assert
        assert result["total_devices_checked"] == 1
        assert result["reenabled_count"] == 1
        assert result["results"][0]["device_id"] == device.id
        assert result["results"][0]["success"] is True

        # Verify device was re-enabled
        device.refresh_from_db()
        assert device.realtime_enabled is True
        assert device.is_connected is True

    @patch("apps.hrm.models.attendance_device.ZKDeviceService")
    def test_reenable_device_connection_failure(self, mock_service):
        """Test device re-enable attempt when connection fails."""
        # Arrange - Create enabled device with realtime disabled
        device = AttendanceDevice.objects.create(
            name="Test Device",
            ip_address="192.168.1.100",
            port=4370,
            is_enabled=True,
            realtime_enabled=False,
            is_connected=False,
        )

        # Mock failed connection
        mock_instance = mock_service.return_value
        mock_instance.__enter__ = lambda self: (_ for _ in ()).throw(Exception("Connection timeout"))
        mock_instance.__exit__ = lambda self, *args: None

        # Act
        result = check_and_reenable_realtime_listeners()

        # Assert
        assert result["total_devices_checked"] == 1
        assert result["reenabled_count"] == 0
        assert result["results"][0]["device_id"] == device.id
        assert result["results"][0]["success"] is False
        assert "Connection timeout" in result["results"][0]["message"]

        # Verify device remains disabled
        device.refresh_from_db()
        assert device.realtime_enabled is False
        assert device.is_connected is False

    @patch("apps.hrm.models.attendance_device.ZKDeviceService")
    def test_reenable_multiple_devices(self, mock_service):
        """Test re-enabling multiple devices with mixed results."""
        # Arrange - Create two enabled devices with realtime disabled
        device1 = AttendanceDevice.objects.create(
            name="Device 1",
            ip_address="192.168.1.100",
            port=4370,
            is_enabled=True,
            realtime_enabled=False,
            is_connected=False,
        )
        device2 = AttendanceDevice.objects.create(
            name="Device 2",
            ip_address="192.168.1.101",
            port=4370,
            is_enabled=True,
            realtime_enabled=False,
            is_connected=False,
        )

        # Mock successful connection for first device
        call_count = [0]

        def mock_enter(self):
            call_count[0] += 1
            if call_count[0] == 1:
                return self
            raise Exception("Connection timeout")

        mock_instance = mock_service.return_value
        mock_instance._zk_connection = True
        mock_instance.get_device_info.return_value = {
            "serial_number": "SN123",
            "firmware_version": "6.60",
        }
        mock_instance.__enter__ = mock_enter
        mock_instance.__exit__ = lambda self, *args: None

        # Act
        result = check_and_reenable_realtime_listeners()

        # Assert
        assert result["total_devices_checked"] == 2
        assert result["reenabled_count"] == 1

        # Verify first device was re-enabled
        device1.refresh_from_db()
        assert device1.realtime_enabled is True

        # Verify second device remains disabled
        device2.refresh_from_db()
        assert device2.realtime_enabled is False
