"""Tests for realtime attendance listener."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from zk.exception import ZKErrorConnection

from apps.hrm.models import AttendanceDevice, AttendanceRecord
from apps.hrm.realtime_listener import RealtimeAttendanceListener

# Mark all tests in this file as async
pytestmark = pytest.mark.asyncio


class MockAttendance:
    """Mock Attendance object from PyZK."""

    def __init__(self, user_id, timestamp, status, punch, uid):
        """Initialize mock attendance."""
        self.user_id = user_id
        self.timestamp = timestamp
        self.status = status
        self.punch = punch
        self.uid = uid


@pytest.mark.django_db(transaction=True)
class TestRealtimeAttendanceListener:
    """Test cases for RealtimeAttendanceListener."""

    @pytest.fixture(autouse=True)
    def setup_method(self, db):
        """Set up test data."""
        self.device = AttendanceDevice.objects.create(
            name="Test Device",
            location="Main Office",
            ip_address="192.168.1.100",
            port=4370,
            is_enabled=True,
        )

    async def test_listener_initialization(self):
        """Test listener can be initialized."""
        listener = RealtimeAttendanceListener()
        assert listener is not None
        assert not listener._running
        assert len(listener._device_tasks) == 0

    async def test_get_enabled_devices(self, db):
        """Test getting enabled devices from database."""
        # Create another device that is disabled
        await asyncio.to_thread(
            AttendanceDevice.objects.create,
            name="Disabled Device",
            ip_address="192.168.1.101",
            is_enabled=False,
        )

        listener = RealtimeAttendanceListener()
        devices = await listener._get_enabled_devices()

        assert len(devices) == 1
        assert devices[0].name == "Test Device"

    async def test_mark_device_connected(self, db):
        """Test marking device as connected."""
        listener = RealtimeAttendanceListener()

        # Initially not connected
        device = await asyncio.to_thread(AttendanceDevice.objects.get, id=self.device.id)
        assert not device.is_connected

        # Mark as connected
        await listener._mark_device_connected(self.device)

        # Refresh from database
        device = await asyncio.to_thread(AttendanceDevice.objects.get, id=self.device.id)
        assert device.is_connected

    async def test_mark_device_disconnected(self, db):
        """Test marking device as disconnected."""
        listener = RealtimeAttendanceListener()

        # Set initially connected
        def set_connected():
            device = AttendanceDevice.objects.get(id=self.device.id)
            device.is_connected = True
            device.save()

        await asyncio.to_thread(set_connected)

        # Mark as disconnected
        await listener._mark_device_disconnected(self.device)

        # Refresh from database
        device = await asyncio.to_thread(AttendanceDevice.objects.get, id=self.device.id)
        assert not device.is_connected

    async def test_store_attendance_record(self, db):
        """Test storing attendance record in database."""
        listener = RealtimeAttendanceListener()

        timestamp = datetime.now(timezone.utc)
        attendance = MockAttendance(user_id="100", timestamp=timestamp, status=1, punch=0, uid=1)

        # Store record
        await listener._store_attendance_record(self.device, attendance, timestamp)

        # Verify record was created
        def check_records():
            records = AttendanceRecord.objects.filter(device=self.device, attendance_code="100")
            assert records.count() == 1

            record = records.first()
            assert record.attendance_code == "100"
            assert record.timestamp == timestamp
            assert record.raw_data is not None
            assert record.raw_data["uid"] == 1

        await asyncio.to_thread(check_records)

    async def test_store_attendance_record_avoids_duplicates(self, db):
        """Test that duplicate records are not created."""
        listener = RealtimeAttendanceListener()

        timestamp = datetime.now(timezone.utc)
        attendance = MockAttendance(user_id="100", timestamp=timestamp, status=1, punch=0, uid=1)

        # Store record twice
        await listener._store_attendance_record(self.device, attendance, timestamp)
        await listener._store_attendance_record(self.device, attendance, timestamp)

        # Verify only one record was created
        def check_count():
            records = AttendanceRecord.objects.filter(device=self.device, attendance_code="100", timestamp=timestamp)
            assert records.count() == 1

        await asyncio.to_thread(check_count)

    async def test_process_attendance_event_with_naive_timestamp(self, db):
        """Test processing attendance event with naive timestamp."""
        listener = RealtimeAttendanceListener()

        # Create attendance with naive datetime
        naive_timestamp = datetime(2025, 10, 28, 12, 0, 0)
        attendance = MockAttendance(user_id="200", timestamp=naive_timestamp, status=1, punch=0, uid=2)

        # Process event
        await listener._process_attendance_event(self.device, attendance)

        # Verify record was created with timezone-aware timestamp
        def check_record():
            records = AttendanceRecord.objects.filter(device=self.device, attendance_code="200")
            assert records.count() == 1

            record = records.first()
            assert record.timestamp.tzinfo is not None

        await asyncio.to_thread(check_record)

    @patch("apps.hrm.realtime_listener.ZK")
    async def test_connect_device_success(self, mock_zk_class):
        """Test successful device connection."""
        # Mock ZK connection
        mock_zk_instance = Mock()
        mock_conn = Mock()
        mock_zk_instance.connect.return_value = mock_conn
        mock_zk_class.return_value = mock_zk_instance

        listener = RealtimeAttendanceListener()
        conn = await listener._connect_device(self.device)

        assert conn is not None
        mock_zk_class.assert_called_once_with(
            "192.168.1.100",
            port=4370,
            timeout=60,
            password=0,
            ommit_ping=False,
        )

    @patch("apps.hrm.realtime_listener.ZK")
    async def test_connect_device_failure(self, mock_zk_class):
        """Test device connection failure."""
        # Mock ZK connection to raise error
        mock_zk_instance = Mock()
        mock_zk_instance.connect.side_effect = ZKErrorConnection("Connection failed")
        mock_zk_class.return_value = mock_zk_instance

        listener = RealtimeAttendanceListener()

        with pytest.raises(ZKErrorConnection):
            await listener._connect_device(self.device)

    @patch("apps.hrm.realtime_listener.ZK")
    async def test_disconnect_device(self, mock_zk_class):
        """Test device disconnection."""
        # Mock ZK connection
        mock_conn = Mock()
        mock_conn.disconnect = Mock()

        listener = RealtimeAttendanceListener()
        await listener._disconnect_device(self.device, mock_conn)

        mock_conn.disconnect.assert_called_once()

    @patch("apps.hrm.realtime_listener.ZK")
    async def test_update_device_info(self, mock_zk_class, db):
        """Test updating device information."""
        # Mock ZK connection with device info
        mock_conn = Mock()
        mock_conn.get_serialnumber.return_value = "ABC123456"
        mock_conn.get_platform.return_value = "ZK-Platform-V1"

        listener = RealtimeAttendanceListener()
        await listener._update_device_info(self.device, mock_conn)

        # Refresh from database
        device = await asyncio.to_thread(AttendanceDevice.objects.get, id=self.device.id)
        assert device.serial_number == "ABC123456"
        assert device.registration_number == "ZK-Platform-V1"

    async def test_notify_admin_device_offline(self):
        """Test admin notification for offline device."""
        listener = RealtimeAttendanceListener()

        # This should log a critical error but not raise exception
        # Just verify it doesn't crash
        await listener._notify_admin_device_offline(self.device, "Connection timeout")

    async def test_async_generator_from_sync(self):
        """Test converting sync generator to async generator."""

        def sync_gen():
            for i in range(3):
                yield i

        listener = RealtimeAttendanceListener()
        loop = asyncio.get_event_loop()

        results = []
        async for item in listener._async_generator_from_sync(sync_gen, loop):
            results.append(item)

        assert results == [0, 1, 2]

    @patch("apps.hrm.realtime_listener.ZK")
    async def test_start_and_stop(self, mock_zk_class, db):
        """Test starting and stopping the listener."""
        # Mock ZK to avoid actual connections
        mock_zk_instance = Mock()
        mock_conn = Mock()
        mock_conn.live_capture = Mock(return_value=iter([]))  # Empty generator
        mock_conn.get_serialnumber = Mock(return_value="TEST123")
        mock_conn.get_platform = Mock(return_value="TEST")
        mock_zk_instance.connect.return_value = mock_conn
        mock_zk_class.return_value = mock_zk_instance

        listener = RealtimeAttendanceListener()

        # Start listener in background
        start_task = asyncio.create_task(listener.start())

        # Wait a bit for it to initialize
        await asyncio.sleep(1.0)

        # Verify it's running
        assert listener._running

        # Stop listener
        await listener.stop()

        # Verify it stopped
        assert not listener._running

        # Wait for start task to complete
        try:
            await asyncio.wait_for(start_task, timeout=2.0)
        except asyncio.TimeoutError:
            start_task.cancel()
            try:
                await start_task
            except asyncio.CancelledError:
                pass
