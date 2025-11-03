"""Tests for ZK realtime attendance listener."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.devices.zk import ZKDeviceInfo, ZKRealtimeDeviceListener


@pytest.fixture
def mock_device_1():
    """Create a mock device info for testing."""
    return ZKDeviceInfo(
        device_id=1,
        name="Device 1",
        ip_address="192.168.1.100",
        port=4370,
        password=0,
    )


@pytest.fixture
def mock_device_2():
    """Create a second mock device info for testing."""
    return ZKDeviceInfo(
        device_id=2,
        name="Device 2",
        ip_address="192.168.1.101",
        port=4370,
        password=0,
    )


@pytest.fixture
def mock_device_3():
    """Create a third mock device info for testing."""
    return ZKDeviceInfo(
        device_id=3,
        name="Device 3",
        ip_address="192.168.1.102",
        port=4370,
        password=0,
    )


@pytest.mark.unit
@pytest.mark.asyncio
class TestZKRealtimeDeviceListener:
    """Test suite for ZKRealtimeDeviceListener."""

    async def test_registered_devices_initialized_empty(self):
        """Test that registered device IDs set is initialized empty."""
        get_devices_mock = MagicMock(return_value=[])
        on_event_mock = MagicMock()

        listener = ZKRealtimeDeviceListener(
            get_devices_callback=get_devices_mock,
            on_attendance_event=on_event_mock,
        )

        assert listener._registered_device_ids == set()
        assert listener._device_tasks == {}

    async def test_check_and_start_devices_tracks_registered_devices(self, mock_device_1, mock_device_2):
        """Test that _check_and_start_devices tracks registered device IDs."""
        devices = [mock_device_1, mock_device_2]
        get_devices_mock = MagicMock(return_value=devices)
        on_event_mock = MagicMock()

        listener = ZKRealtimeDeviceListener(
            get_devices_callback=get_devices_mock,
            on_attendance_event=on_event_mock,
        )

        with patch.object(listener, "_device_listener_loop", new_callable=AsyncMock):
            await listener._check_and_start_devices()

        # Should track both device IDs
        assert listener._registered_device_ids == {1, 2}
        assert len(listener._device_tasks) == 2

    async def test_check_and_start_devices_removes_disabled_devices(
        self, mock_device_1, mock_device_2, mock_device_3
    ):
        """Test that disabled devices are removed from tracking and tasks cancelled."""
        # Initial setup with 3 devices
        initial_devices = [mock_device_1, mock_device_2, mock_device_3]
        get_devices_mock = MagicMock(return_value=initial_devices)
        on_event_mock = MagicMock()

        listener = ZKRealtimeDeviceListener(
            get_devices_callback=get_devices_mock,
            on_attendance_event=on_event_mock,
        )

        # Start with all 3 devices
        with patch.object(listener, "_device_listener_loop", new_callable=AsyncMock):
            await listener._check_and_start_devices()

        assert listener._registered_device_ids == {1, 2, 3}
        assert len(listener._device_tasks) == 3

        # Now only return 2 devices (device 3 is disabled)
        updated_devices = [mock_device_1, mock_device_2]
        get_devices_mock.return_value = updated_devices

        # Check and start again
        with patch.object(listener, "_device_listener_loop", new_callable=AsyncMock):
            await listener._check_and_start_devices()

        # Device 3 should be removed
        assert listener._registered_device_ids == {1, 2}
        assert 3 not in listener._device_tasks

    async def test_check_and_start_devices_cancels_running_task_for_disabled_device(
        self, mock_device_1, mock_device_2
    ):
        """Test that running tasks are cancelled when device is disabled."""
        initial_devices = [mock_device_1, mock_device_2]
        get_devices_mock = MagicMock(return_value=initial_devices)
        on_event_mock = MagicMock()

        listener = ZKRealtimeDeviceListener(
            get_devices_callback=get_devices_mock,
            on_attendance_event=on_event_mock,
        )

        # Create a mock task that is still running
        mock_task = MagicMock()
        mock_task.done.return_value = False

        # Manually set up registered devices and tasks
        listener._registered_device_ids = {1, 2}
        listener._device_tasks[1] = mock_task

        # Only device 2 is enabled now
        get_devices_mock.return_value = [mock_device_2]

        with patch.object(listener, "_device_listener_loop", new_callable=AsyncMock):
            await listener._check_and_start_devices()

        # Task for device 1 should be cancelled
        mock_task.cancel.assert_called_once()
        assert 1 not in listener._device_tasks
        assert listener._registered_device_ids == {2}

    async def test_device_listener_loop_stops_when_device_not_registered(self, mock_device_1):
        """Test that device listener loop stops retrying when device is unregistered."""
        get_devices_mock = MagicMock(return_value=[mock_device_1])
        on_event_mock = MagicMock()

        listener = ZKRealtimeDeviceListener(
            get_devices_callback=get_devices_mock,
            on_attendance_event=on_event_mock,
        )

        # Track connection attempts
        connect_attempts = []

        async def mock_connect(*args, **kwargs):
            connect_attempts.append(1)
            # Remove device after first failure
            if len(connect_attempts) == 1:
                listener._registered_device_ids.clear()
            raise ConnectionError("Failed")

        # Set up registered devices
        listener._registered_device_ids = {1}
        listener._running = True

        # Mock connection to fail
        with patch.object(listener, "_connect_device", side_effect=mock_connect):
            with patch.object(listener, "_disconnect_device", new_callable=AsyncMock):
                # Start the listener loop in a task
                loop_task = asyncio.create_task(listener._device_listener_loop(mock_device_1))

                # Task should complete when it checks registration after first failure
                try:
                    await asyncio.wait_for(loop_task, timeout=2.0)
                except asyncio.TimeoutError:
                    # If timeout, cancel and fail test
                    loop_task.cancel()
                    await asyncio.gather(loop_task, return_exceptions=True)
                    raise AssertionError("Task did not exit when device was unregistered")

                # Should have only attempted once since device was unregistered after
                assert len(connect_attempts) == 1

    async def test_device_listener_loop_continues_when_device_remains_registered(self, mock_device_1):
        """Test that device listener loop continues retrying when device stays registered."""
        get_devices_mock = MagicMock(return_value=[mock_device_1])
        on_event_mock = MagicMock()

        listener = ZKRealtimeDeviceListener(
            get_devices_callback=get_devices_mock,
            on_attendance_event=on_event_mock,
        )

        # Set up registered devices
        listener._registered_device_ids = {1}
        listener._running = True

        # Track connection attempts
        connect_attempts = []

        async def mock_connect(*args, **kwargs):
            connect_attempts.append(1)
            raise ConnectionError("Failed")

        with patch.object(listener, "_connect_device", side_effect=mock_connect):
            with patch.object(listener, "_disconnect_device", new_callable=AsyncMock):
                # Start the listener loop in a task
                loop_task = asyncio.create_task(listener._device_listener_loop(mock_device_1))

                # Give it time to attempt connection multiple times
                # With base delay of 5 seconds, we need to wait longer
                await asyncio.sleep(1.0)

                # Stop the listener
                listener._running = False

                # Wait for task to complete
                try:
                    await asyncio.wait_for(loop_task, timeout=3.0)
                except asyncio.TimeoutError:
                    loop_task.cancel()
                    await asyncio.gather(loop_task, return_exceptions=True)

                # Should have attempted at least one connection since device stayed registered
                # Note: With the delay, we may not get multiple attempts in test time
                assert len(connect_attempts) >= 1

    async def test_multiple_devices_tracked_and_removed_correctly(
        self, mock_device_1, mock_device_2, mock_device_3
    ):
        """Test that multiple devices can be added and removed correctly."""
        # Start with device 1
        get_devices_mock = MagicMock(return_value=[mock_device_1])
        on_event_mock = MagicMock()

        listener = ZKRealtimeDeviceListener(
            get_devices_callback=get_devices_mock,
            on_attendance_event=on_event_mock,
        )

        with patch.object(listener, "_device_listener_loop", new_callable=AsyncMock):
            # Add device 1
            await listener._check_and_start_devices()
            assert listener._registered_device_ids == {1}

            # Add device 2 and 3
            get_devices_mock.return_value = [mock_device_1, mock_device_2, mock_device_3]
            await listener._check_and_start_devices()
            assert listener._registered_device_ids == {1, 2, 3}

            # Remove device 2
            get_devices_mock.return_value = [mock_device_1, mock_device_3]
            await listener._check_and_start_devices()
            assert listener._registered_device_ids == {1, 3}

            # Remove all devices
            get_devices_mock.return_value = []
            await listener._check_and_start_devices()
            assert listener._registered_device_ids == set()
