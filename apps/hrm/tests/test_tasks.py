"""Tests for HRM attendance synchronization tasks."""

from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
from celery.exceptions import Retry
from django.test import TestCase
from django.utils import timezone as django_timezone

from apps.hrm.models import AttendanceDevice, AttendanceRecord
from apps.hrm.services import AttendanceDeviceConnectionError
from apps.hrm.tasks import sync_all_attendance_devices, sync_attendance_logs_for_device


@pytest.mark.django_db
class TestSyncAttendanceLogsForDevice(TestCase):
    """Test cases for sync_attendance_logs_for_device task."""

    def setUp(self):
        """Set up test data."""
        self.device = AttendanceDevice.objects.create(
            name="Test Device",
            location="Main Office",
            ip_address="192.168.1.100",
            port=4370,
        )

    @patch("apps.hrm.tasks.AttendanceDeviceService")
    def test_sync_success_with_new_logs(self, mock_service_class):
        """Test successful sync with new logs."""
        # Arrange
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        today = django_timezone.now()
        mock_logs = [
            {
                "uid": 1,
                "user_id": "100",
                "timestamp": today,
                "status": 1,
                "punch": 0,
            },
            {
                "uid": 2,
                "user_id": "200",
                "timestamp": today - timedelta(hours=1),
                "status": 1,
                "punch": 0,
            },
        ]
        mock_service.get_attendance_logs.return_value = mock_logs
        mock_service.__enter__ = Mock(return_value=mock_service)
        mock_service.__exit__ = Mock(return_value=False)

        # Act
        result = sync_attendance_logs_for_device(self.device.id)

        # Assert
        self.assertTrue(result["success"])
        self.assertEqual(result["device_id"], self.device.id)
        self.assertEqual(result["device_name"], "Test Device")
        self.assertEqual(result["logs_synced"], 2)
        self.assertEqual(result["total_today_logs"], 2)

        # Verify records were created
        self.assertEqual(AttendanceRecord.objects.count(), 2)
        self.assertEqual(AttendanceRecord.objects.filter(attendance_code="100").count(), 1)
        self.assertEqual(AttendanceRecord.objects.filter(attendance_code="200").count(), 1)

        # Verify device status updated
        self.device.refresh_from_db()
        self.assertTrue(self.device.is_connected)
        self.assertIsNotNone(self.device.polling_synced_at)

    @patch("apps.hrm.tasks.AttendanceDeviceService")
    def test_sync_skips_duplicates(self, mock_service_class):
        """Test that duplicate records are not created."""
        # Arrange
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        today = django_timezone.now()
        timestamp = today.replace(hour=10, minute=0, second=0, microsecond=0)

        # Create existing record
        AttendanceRecord.objects.create(
            device=self.device,
            attendance_code="100",
            timestamp=timestamp,
        )

        # Mock service returns same record
        mock_logs = [
            {
                "uid": 1,
                "user_id": "100",
                "timestamp": timestamp,
                "status": 1,
                "punch": 0,
            },
        ]
        mock_service.get_attendance_logs.return_value = mock_logs
        mock_service.__enter__ = Mock(return_value=mock_service)
        mock_service.__exit__ = Mock(return_value=False)

        # Act
        result = sync_attendance_logs_for_device(self.device.id)

        # Assert
        self.assertTrue(result["success"])
        self.assertEqual(result["logs_synced"], 0)  # No new logs synced
        self.assertEqual(AttendanceRecord.objects.count(), 1)  # Still only 1 record

    @patch("apps.hrm.tasks.AttendanceDeviceService")
    def test_sync_filters_current_day_only(self, mock_service_class):
        """Test that only current day logs are synced."""
        # Arrange
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        today = django_timezone.now()
        yesterday = today - timedelta(days=1)

        mock_logs = [
            {
                "uid": 1,
                "user_id": "100",
                "timestamp": today,
                "status": 1,
                "punch": 0,
            },
            {
                "uid": 2,
                "user_id": "200",
                "timestamp": yesterday,  # Should be filtered out
                "status": 1,
                "punch": 0,
            },
        ]
        mock_service.get_attendance_logs.return_value = mock_logs
        mock_service.__enter__ = Mock(return_value=mock_service)
        mock_service.__exit__ = Mock(return_value=False)

        # Act
        result = sync_attendance_logs_for_device(self.device.id)

        # Assert
        self.assertTrue(result["success"])
        self.assertEqual(result["logs_synced"], 1)  # Only today's log
        self.assertEqual(result["total_today_logs"], 1)
        self.assertEqual(AttendanceRecord.objects.count(), 1)
        self.assertEqual(AttendanceRecord.objects.first().attendance_code, "100")

    @patch("apps.hrm.tasks.AttendanceDeviceService")
    def test_sync_uses_last_sync_time(self, mock_service_class):
        """Test that sync uses last polling_synced_at time."""
        # Arrange
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.__enter__ = Mock(return_value=mock_service)
        mock_service.__exit__ = Mock(return_value=False)

        last_sync = django_timezone.now() - timedelta(hours=2)
        self.device.polling_synced_at = last_sync
        self.device.save()

        mock_service.get_attendance_logs.return_value = []

        # Act
        sync_attendance_logs_for_device(self.device.id)

        # Assert
        mock_service.get_attendance_logs.assert_called_once()
        call_args = mock_service.get_attendance_logs.call_args
        self.assertEqual(call_args[1]["start_datetime"], last_sync)

    @patch("apps.hrm.tasks.AttendanceDeviceService")
    def test_sync_uses_default_lookback_when_no_last_sync(self, mock_service_class):
        """Test that sync uses default lookback when no last sync time."""
        # Arrange
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.__enter__ = Mock(return_value=mock_service)
        mock_service.__exit__ = Mock(return_value=False)

        mock_service.get_attendance_logs.return_value = []

        # Ensure no last sync time
        self.device.polling_synced_at = None
        self.device.save()

        # Act
        sync_attendance_logs_for_device(self.device.id)

        # Assert
        mock_service.get_attendance_logs.assert_called_once()
        call_args = mock_service.get_attendance_logs.call_args
        start_dt = call_args[1]["start_datetime"]

        # Should be approximately 1 day ago
        expected = django_timezone.now() - timedelta(days=1)
        delta = abs((start_dt - expected).total_seconds())
        self.assertLess(delta, 5)  # Within 5 seconds

    @patch("apps.hrm.tasks.AttendanceDeviceService")
    def test_sync_connection_error_updates_status(self, mock_service_class):
        """Test that connection error updates device status to disconnected."""
        # Arrange
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        # Configure mock to raise error when used as context manager
        mock_service.__enter__ = Mock(side_effect=AttendanceDeviceConnectionError("Connection failed"))
        mock_service.__exit__ = Mock(return_value=False)

        # Set device as connected initially
        self.device.is_connected = True
        self.device.save()

        # Act - call the task, which will raise Retry but we'll catch it
        try:
            sync_attendance_logs_for_device(self.device.id)
        except Retry:
            pass  # Expected - task will retry on connection error

        # Assert device status updated
        self.device.refresh_from_db()
        self.assertFalse(self.device.is_connected)

    @patch("apps.hrm.tasks.AttendanceDeviceService")
    def test_sync_saves_raw_data(self, mock_service_class):
        """Test that raw_data is saved with attendance record."""
        # Arrange
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        today = django_timezone.now()
        mock_logs = [
            {
                "uid": 1,
                "user_id": "100",
                "timestamp": today,
                "status": 1,
                "punch": 0,
            },
        ]
        mock_service.get_attendance_logs.return_value = mock_logs
        mock_service.__enter__ = Mock(return_value=mock_service)
        mock_service.__exit__ = Mock(return_value=False)

        # Act
        sync_attendance_logs_for_device(self.device.id)

        # Assert
        record = AttendanceRecord.objects.first()
        self.assertIsNotNone(record.raw_data)
        self.assertEqual(record.raw_data["uid"], 1)
        self.assertEqual(record.raw_data["user_id"], "100")
        self.assertEqual(record.raw_data["status"], 1)

    def test_sync_device_not_found(self):
        """Test handling of non-existent device."""
        # Act
        result = sync_attendance_logs_for_device(99999)

        # Assert
        self.assertFalse(result["success"])
        self.assertEqual(result["device_id"], 99999)
        self.assertIn("does not exist", result["error"])

    @patch("apps.hrm.tasks.AttendanceDeviceService")
    def test_sync_empty_logs(self, mock_service_class):
        """Test sync with no logs from device."""
        # Arrange
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.get_attendance_logs.return_value = []
        mock_service.__enter__ = Mock(return_value=mock_service)
        mock_service.__exit__ = Mock(return_value=False)

        # Act
        result = sync_attendance_logs_for_device(self.device.id)

        # Assert
        self.assertTrue(result["success"])
        self.assertEqual(result["logs_synced"], 0)
        self.assertEqual(AttendanceRecord.objects.count(), 0)

        # Device status should still be updated
        self.device.refresh_from_db()
        self.assertTrue(self.device.is_connected)
        self.assertIsNotNone(self.device.polling_synced_at)


@pytest.mark.django_db
class TestSyncAllAttendanceDevices(TestCase):
    """Test cases for sync_all_attendance_devices task."""

    def setUp(self):
        """Set up test data."""
        self.device1 = AttendanceDevice.objects.create(
            name="Device 1",
            ip_address="192.168.1.100",
        )
        self.device2 = AttendanceDevice.objects.create(
            name="Device 2",
            ip_address="192.168.1.101",
        )

    @patch("apps.hrm.tasks.sync_attendance_logs_for_device")
    def test_sync_all_triggers_individual_tasks(self, mock_sync_task):
        """Test that sync_all triggers individual sync tasks."""
        # Arrange
        mock_sync_task.delay = Mock()

        # Act
        result = sync_all_attendance_devices()

        # Assert
        self.assertEqual(result["total_devices"], 2)
        self.assertEqual(result["tasks_triggered"], 2)
        self.assertIn(self.device1.id, result["device_ids"])
        self.assertIn(self.device2.id, result["device_ids"])

        # Verify delay was called for each device
        self.assertEqual(mock_sync_task.delay.call_count, 2)

    @patch("apps.hrm.tasks.sync_attendance_logs_for_device")
    def test_sync_all_with_no_devices(self, mock_sync_task):
        """Test sync_all when no devices exist."""
        # Arrange
        AttendanceDevice.objects.all().delete()

        # Act
        result = sync_all_attendance_devices()

        # Assert
        self.assertEqual(result["total_devices"], 0)
        self.assertEqual(result["tasks_triggered"], 0)
        self.assertEqual(result["device_ids"], [])
        mock_sync_task.delay.assert_not_called()

    @patch("apps.hrm.tasks.sync_attendance_logs_for_device")
    def test_sync_all_handles_task_trigger_error(self, mock_sync_task):
        """Test that sync_all handles errors when triggering individual tasks."""
        # Arrange
        mock_sync_task.delay.side_effect = [
            None,  # First device succeeds
            Exception("Task trigger error"),  # Second device fails
        ]

        # Act
        result = sync_all_attendance_devices()

        # Assert
        self.assertEqual(result["total_devices"], 2)
        self.assertEqual(result["tasks_triggered"], 1)  # Only one succeeded
        self.assertEqual(len(result["device_ids"]), 1)

    @patch("apps.hrm.tasks.sync_attendance_logs_for_device")
    def test_sync_all_with_single_device(self, mock_sync_task):
        """Test sync_all with single device."""
        # Arrange
        AttendanceDevice.objects.exclude(id=self.device1.id).delete()
        mock_sync_task.delay = Mock()

        # Act
        result = sync_all_attendance_devices()

        # Assert
        self.assertEqual(result["total_devices"], 1)
        self.assertEqual(result["tasks_triggered"], 1)
        mock_sync_task.delay.assert_called_once_with(self.device1.id)
