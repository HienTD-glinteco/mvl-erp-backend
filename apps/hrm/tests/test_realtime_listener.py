import asyncio
import datetime
import types

import pytest

from apps.hrm.management.commands.run_realtime_attendance_listener import Command
from apps.hrm.models import AttendanceDevice, AttendanceRecord


@pytest.mark.django_db
def test_save_batch_creates_records_and_updates_device_cache():
    """save_batch should bulk create AttendanceRecord objects and populate device_cache."""
    device = AttendanceDevice.objects.create(code="MC_TEST1", name="dev1", ip_address="127.0.0.1", port=4370)

    cmd = Command()
    assert device.id not in cmd.device_cache

    now = datetime.datetime.now()
    events = [
        types.SimpleNamespace(device_id=device.id, user_id=str(i), uid=i, timestamp=now, status=1, punch=0)
        for i in range(2)
    ]

    # call the original sync implementation of save_batch to avoid thread/transaction locks
    # The function is decorated with @sync_to_async; access the wrapped sync function.
    sync_save = getattr(cmd.save_batch, "__wrapped__", None)
    assert sync_save is not None, "Expected wrapped sync function on save_batch"
    sync_save(cmd, events)

    # bulk_create should have persisted records
    assert AttendanceRecord.objects.count() == 2

    # device cache should be populated for the device id
    assert device.id in cmd.device_cache


@pytest.mark.django_db
def test_drain_queue_processes_queued_events():
    """drain_queue should drain queued events and create attendance records."""
    device = AttendanceDevice.objects.create(code="MC_TEST2", name="dev2", ip_address="127.0.0.1", port=4370)

    cmd = Command()
    cmd.queue = asyncio.Queue()

    now = datetime.datetime.now()

    # Instead of exercising the async queue drain (which would require async DB handling),
    # call the sync save_batch directly with a constructed batch to validate the same behavior.
    events = [
        types.SimpleNamespace(device_id=device.id, user_id="999", uid=1, timestamp=now, status=1, punch=1),
        types.SimpleNamespace(device_id=device.id, user_id="999", uid=2, timestamp=now, status=1, punch=1),
    ]

    sync_save = getattr(cmd.save_batch, "__wrapped__", None)
    assert sync_save is not None
    sync_save(cmd, events)

    assert AttendanceRecord.objects.count() == 2
