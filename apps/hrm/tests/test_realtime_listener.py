from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.devices.zk import ZKAttendanceEvent
from apps.hrm.management.commands.run_realtime_attendance_listener import Command


class TestRealtimeListenerCommand:
    @pytest.fixture
    def cmd(self):
        return Command()

    @pytest.mark.asyncio
    async def test_on_attendance_event_dispatches_task(self, cmd):
        # Mock the process_realtime_attendance_event task
        with patch(
            "apps.hrm.management.commands.run_realtime_attendance_listener.process_realtime_attendance_event"
        ) as mock_task:
            # Setup command
            cmd.running = True

            # Create event
            now = timezone.now()
            event = ZKAttendanceEvent(
                device_id=1, device_name="Test Device", user_id="12345", uid=1, timestamp=now, status=0, punch=0
            )

            # Call handler
            await cmd.on_attendance_event(event)

            # Verify task was called
            # We need to verify what was passed to .delay()
            mock_task.delay.assert_called_once()

            # Check args
            call_args = mock_task.delay.call_args
            event_data = call_args[0][0]

            assert event_data["device_id"] == 1
            assert event_data["user_id"] == "12345"
            assert event_data["timestamp"] == now.isoformat()

            assert cmd.processed_count == 1

    @pytest.mark.asyncio
    async def test_on_attendance_event_does_not_dispatch_if_not_running(self, cmd):
        with patch(
            "apps.hrm.management.commands.run_realtime_attendance_listener.process_realtime_attendance_event"
        ) as mock_task:
            # Setup command
            cmd.running = False

            # Create event
            event = ZKAttendanceEvent(
                device_id=1,
                device_name="Test Device",
                user_id="12345",
                uid=1,
                timestamp=timezone.now(),
                status=0,
                punch=0,
            )

            # Call handler
            await cmd.on_attendance_event(event)

            # Verify task was NOT called
            mock_task.delay.assert_not_called()
            assert cmd.processed_count == 0
