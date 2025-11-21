# Attendance Device Integration with PyZK

This document describes the PyZK integration for attendance log synchronization, including both polling-based and realtime capture systems.

## Overview

The system integrates with ZKTeco (and compatible) attendance devices using the PyZK library. It provides:

- **Service Layer**: Reusable connection and data fetching logic
- **Polling Tasks**: Automatic periodic synchronization via Celery
- **Realtime Listener**: Continuous event capture via asyncio
- **Error Handling**: Robust retry logic with exponential backoff
- **Data Storage**: Attendance records stored in PostgreSQL with timestamp indexing

## Architecture

### Polling Architecture (Celery-based)

```
┌─────────────────────┐
│  Celery Beat        │
│  (Every 5 minutes)  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────┐
│  sync_all_attendance_devices    │
│  (Triggers individual syncs)    │
└──────────┬──────────────────────┘
           │
           ▼
┌──────────────────────────────────────┐
│  sync_attendance_logs_for_device     │
│  (Per device sync task)              │
└──────────┬───────────────────────────┘
           │
           ▼
┌──────────────────────────────────────┐
│  AttendanceDeviceService             │
│  (PyZK connection & data fetch)      │
└──────────┬───────────────────────────┘
           │
           ▼
┌──────────────────────────────────────┐
│  AttendanceRecord Model              │
│  (PostgreSQL storage)                │
└──────────────────────────────────────┘
```

### Realtime Architecture (Asyncio-based)

```
┌────────────────────────────────────┐
│  RealtimeAttendanceListener        │
│  (Asyncio event loop)              │
└──────────┬─────────────────────────┘
           │
           ├─────────────────────────────────┐
           │                                 │
           ▼                                 ▼
┌──────────────────────────┐   ┌──────────────────────────┐
│  Device 1 Listener       │   │  Device 2 Listener       │
│  (Concurrent task)       │   │  (Concurrent task)       │
└──────────┬───────────────┘   └──────────┬───────────────┘
           │                              │
           ▼                              ▼
┌──────────────────────────┐   ┌──────────────────────────┐
│  PyZK live_capture()     │   │  PyZK live_capture()     │
│  (Real-time events)      │   │  (Real-time events)      │
└──────────┬───────────────┘   └──────────┬───────────────┘
           │                              │
           └──────────────┬───────────────┘
                          ▼
           ┌──────────────────────────────┐
           │  AttendanceRecord Model      │
           │  (PostgreSQL storage)        │
           └──────────────────────────────┘
```

## Models

### AttendanceDevice

Stores configuration for physical attendance devices.

**Key Fields:**
- `name`: Human-readable device identifier
- `block`: ForeignKey to Block (device location)
- `ip_address`: Device network address
- `port`: Network port (default: 4370)
- `password`: Device authentication password
- `serial_number`: Device serial number (auto-populated by realtime listener)
- `registration_number`: Device registration/platform info (auto-populated by realtime listener)
- `is_enabled`: Whether device is enabled for automatic sync
- `is_connected`: Current connection status (updated by both polling and realtime)
- `realtime_enabled`: Whether realtime listener is enabled for this device
- `realtime_disabled_at`: Timestamp when realtime was disabled due to failures
- `polling_synced_at`: Last successful polling sync timestamp

### AttendanceRecord

Stores individual attendance clock-in/out records from devices.

**Key Fields:**
- `device`: Foreign key to AttendanceDevice
- `attendance_code`: User ID from device (matches Employee.attendance_code)
- `timestamp`: Date/time of attendance event
- `is_valid`: Boolean indicating if record is valid
- `notes`: Additional notes or comments about the record
- `raw_data`: JSON field with complete device data for debugging

Note: Creating or updating an `AttendanceRecord` will now update or create the corresponding `TimeSheetEntry` (start/end times and hours), set the `EmployeeMonthlyTimesheet` `need_refresh` flag, and queue a background task to refresh monthly aggregates.

**Indexes:**
- `(attendance_code, -timestamp)` - Fast employee lookups
- `(device, -timestamp)` - Fast device-specific queries
- `(-timestamp)` - Overall chronological queries

## Service Layer

### AttendanceDeviceService

Main service class for device operations.

**Usage:**
```python
from apps.hrm.models import AttendanceDevice
from apps.hrm.services import AttendanceDeviceService

device = AttendanceDevice.objects.get(id=1)

# Context manager automatically handles connection/disconnection
with AttendanceDeviceService(device) as service:
    # Test connection
    success, message = service.test_connection()

    # Fetch logs
    logs = service.get_attendance_logs(start_datetime=some_datetime)
```

**Methods:**
- `connect()`: Establish connection to device
- `disconnect()`: Close connection
- `test_connection()`: Verify connectivity and get firmware version
- `get_attendance_logs(start_datetime=None)`: Fetch attendance records

**Error Handling:**
- Raises `AttendanceDeviceConnectionError` for all connection issues
- Automatic conversion of naive timestamps to UTC
- Comprehensive logging of all operations

## Tasks

### sync_attendance_logs_for_device(device_id)

Synchronize attendance logs from a single device.

**Behavior:**
- Connects to device and fetches logs
- Filters for current day only (as per requirements)
- Skips duplicate records (by device + code + timestamp)
- Updates device connection status
- Implements retry with exponential backoff on connection errors

**Parameters:**
- `device_id`: ID of AttendanceDevice to sync

**Returns:**
```python
{
    "success": bool,
    "device_id": int,
    "device_name": str,
    "logs_synced": int,
    "total_today_logs": int,
    "error": str | None
}
```

**Retry Configuration:**
- Max retries: 3
- Base delay: 300 seconds (5 minutes)
- Backoff: Exponential (5min, 10min, 20min)

### sync_all_attendance_devices()

Trigger sync for all configured devices.

**Behavior:**
- Queries all AttendanceDevice records
- Spawns individual sync_attendance_logs_for_device tasks
- Returns summary of triggered tasks

**Returns:**
```python
{
    "total_devices": int,
    "tasks_triggered": int,
    "device_ids": list[int]
}
```

## Realtime Listener

### RealtimeAttendanceListener

New asyncio-based service that maintains persistent connections to attendance devices for realtime event capture.

**Features:**
- Concurrent monitoring of multiple devices using asyncio
- Live event capture via PyZK's `live_capture()` method
- Automatic reconnection with exponential backoff on connection loss
- Device status tracking and updates
- Duplicate event prevention
- Periodic device info updates (serial number, registration number)
- Admin notifications on repeated failures

**Usage:**

Run as a standalone process using the management command:

```bash
poetry run python manage.py run_realtime_attendance_listener

# With custom log level
poetry run python manage.py run_realtime_attendance_listener --log-level DEBUG
```

**How It Works:**

1. **Initialization**: Listener queries all enabled devices (`is_enabled=True`)
2. **Connection**: Establishes asyncio task for each device
3. **Live Capture**: Uses PyZK's `live_capture(new_timeout=60)` to receive realtime events
4. **Event Processing**:
   - Converts naive timestamps to UTC
   - Checks for duplicates (by device + code + timestamp)
   - Stores in AttendanceRecord with raw_data
5. **Status Updates**:
   - Marks device as connected on successful connection
   - Updates `serial_number` and `registration_number` every 5 minutes
   - Marks device as disconnected on connection loss
6. **Reconnection**:
   - Implements exponential backoff (5s → 10s → 20s ... up to 300s)
   - Tracks consecutive failures
   - Logs critical admin alert after 5 consecutive failures

**Configuration Constants:**

Located in `apps/hrm/realtime_listener.py`:

```python
DEFAULT_LIVE_CAPTURE_TIMEOUT = 60      # Timeout for live_capture in seconds
RECONNECT_BASE_DELAY = 5               # Initial reconnect delay
RECONNECT_MAX_DELAY = 300              # Maximum reconnect delay (5 minutes)
RECONNECT_BACKOFF_MULTIPLIER = 2       # Exponential backoff multiplier
MAX_CONSECUTIVE_FAILURES = 5           # Alert threshold
MAX_RETRY_DURATION = 86400             # Stop retrying after 1 day (24 hours)
DEVICE_INFO_UPDATE_INTERVAL = 300      # Update device info every 5 minutes
DEVICE_CHECK_INTERVAL = 60             # Check for new/enabled devices every 60 seconds
```

**Dynamic Device Management:**

The realtime listener supports adding and enabling devices dynamically without requiring a restart:

1. **New device added**: Automatically detected and listener started within 60 seconds
2. **Device re-enabled**: If a disabled device is enabled again, listener automatically starts
3. **Reconnected device**: If realtime was disabled and is re-enabled (via admin or polling), listener automatically starts

The listener checks every 60 seconds for new or newly-enabled devices and starts monitoring them automatically.

**Automatic Realtime Disable/Re-enable:**

The realtime listener includes intelligent management of device connections:

1. **Auto-disable after 24 hours**: If a device fails to connect for 24 hours continuously, the realtime listener will automatically disable itself for that device by setting `realtime_enabled=False` and recording the time in `realtime_disabled_at`.

2. **Auto-enable on success**: When any of the following succeed, realtime is automatically re-enabled:
   - Successful realtime connection
   - Successful polling sync (via `mark_sync_success()`)

3. **Manual reconnect**: Devices with disabled realtime can be manually reconnected using the admin interface or API.

**Graceful Shutdown:**

The listener handles SIGINT and SIGTERM signals for graceful shutdown:

```bash
# Stop with Ctrl+C
^C

# Or send SIGTERM
kill -TERM <pid>
```

**Deployment:**

For production deployment, run the listener as a systemd service:

```ini
[Unit]
Description=Attendance Realtime Listener
After=network.target postgresql.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/backend
Environment="PATH=/path/to/.venv/bin"
ExecStart=/path/to/.venv/bin/python manage.py run_realtime_attendance_listener
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Monitoring:**

Check listener logs for connection status and events:

```bash
# If running in foreground
poetry run python manage.py run_realtime_attendance_listener

# If running as systemd service
journalctl -u attendance-listener -f

# Filter for specific events
journalctl -u attendance-listener -f | grep "Captured attendance event"
journalctl -u attendance-listener -f | grep "ADMIN ALERT"
```

**When to Use Realtime vs Polling:**

| Use Case | Realtime Listener | Polling (Celery) |
|----------|------------------|------------------|
| Immediate event capture | ✓ Yes | ✗ No (5-min delay) |
| Low network latency required | ✓ Yes | ~ Acceptable |
| Multiple devices | ✓ Concurrent | ✓ Sequential |
| Resource usage | Higher (persistent connections) | Lower (periodic) |
| Complexity | Higher (async management) | Lower (task-based) |
| Reliability | Requires process monitoring | Built-in with Celery |
| Historical data sync | ✗ No | ✓ Yes |

**Recommendation:** Use both systems:
- **Realtime Listener**: For immediate event capture during business hours
- **Polling Tasks**: As a backup for missed events and historical sync

## Configuration

### Celery Beat Schedule

Located in `settings/base/celery.py`:

```python
CELERY_BEAT_SCHEDULE = {
    "sync_all_attendance_devices": {
        "task": "apps.hrm.tasks.sync_all_attendance_devices",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
    },
}
```

Additional timesheet-specific tasks:

- `apps.hrm.tasks.timesheets.prepare_monthly_timesheets` (cron: 1st of month at 00:01): prepares `TimeSheetEntry` rows and monthly aggregates for all active employees, also increments `available_leave_days` for eligible employees by 1.
- `apps.hrm.tasks.timesheets.update_monthly_timesheet_async` (interval: 30s): processes `EmployeeMonthlyTimesheet` rows flagged with `need_refresh`.



**Customization:**
- Modify crontab schedule as needed
- Default: Every 5 minutes
- Can be changed to hourly, daily, etc.

## Manual Testing

Use the provided manual test script:

```bash
poetry run python scripts/manual_test_attendance_sync.py
```

**Features:**
- List all configured devices
- Test device connectivity
- Manually trigger sync for single device
- Manually trigger sync for all devices
- View recent attendance records

## API Integration

To create/manage devices via API:

```bash
# Create device
POST /api/hrm/attendance-devices/
{
    "name": "Main Office Device",
    "location": "Building A - Main Entrance",
    "ip_address": "192.168.1.100",
    "port": 4370,
    "password": "admin123"
}

# List devices
GET /api/hrm/attendance-devices/

# Get device details
GET /api/hrm/attendance-devices/{id}/

# Update device
PATCH /api/hrm/attendance-devices/{id}/

# Delete device
DELETE /api/hrm/attendance-devices/{id}/
```

## Monitoring

### Check Sync Status

```python
from apps.hrm.models import AttendanceDevice

# Check last sync time for all devices
devices = AttendanceDevice.objects.all()
for device in devices:
    print(f"{device.name}: Last sync at {device.polling_synced_at}")
    print(f"  Connected: {device.is_connected}")
```

### View Recent Logs

```python
from apps.hrm.models import AttendanceRecord
from datetime import timedelta
from django.utils import timezone

# Get today's records
today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
records = AttendanceRecord.objects.filter(timestamp__gte=today)

# Group by device
for device_id, count in records.values('device__name').annotate(count=Count('id')):
    print(f"{device_id}: {count} records today")
```

### Celery Logs

Monitor Celery worker logs for sync operations:

```bash
# Check worker logs
tail -f /path/to/celery/worker.log | grep "sync_attendance"

# Check beat scheduler logs
tail -f /path/to/celery/beat.log | grep "sync_all_attendance_devices"
```

## Troubleshooting

### Connection Failures

**Symptoms:**
- Device shows `is_connected=False`
- No new records synced
- Logs show "Connection failed"

**Solutions:**
1. Verify network connectivity to device IP
2. Check device is powered on and responding
3. Verify port number (default: 4370)
4. Check password if device requires authentication
5. Review firewall rules

### Duplicate Records

**Symptoms:**
- Same attendance event appears multiple times

**Prevention:**
- System automatically checks for duplicates before creating records
- Uniqueness based on: device + attendance_code + timestamp

**Manual Cleanup:**
```python
from apps.hrm.models import AttendanceRecord
from django.db.models import Count

# Find duplicates
duplicates = AttendanceRecord.objects.values(
    'device', 'attendance_code', 'timestamp'
).annotate(count=Count('id')).filter(count__gt=1)

# Review and delete manually if needed
```

### No Logs Syncing

**Check:**
1. Celery beat is running: `ps aux | grep celery`
2. Beat schedule is configured correctly
3. Worker is processing tasks: Check Flower or Celery logs
4. Device has attendance logs in the current day
5. System time is synchronized (timezone issues)

## Future Enhancements

**Implemented:**
- ✓ Real-time log synchronization via asyncio listener
- ✓ Device status monitoring and updates
- ✓ Exponential backoff retry logic
- ✓ Admin alerts on repeated failures

**Not implemented yet:**
- Employee matching based on attendance_code
- Attendance analytics and reporting
- Web UI for device management
- Device health monitoring dashboard
- Historical data migration
- Email/SMS notifications for admin alerts (currently logs only)

## Testing

### Unit Tests

```bash
# Run all attendance-related tests
poetry run pytest apps/hrm/tests/test_services.py -v
poetry run pytest apps/hrm/tests/test_tasks.py -v
poetry run pytest apps/hrm/tests/test_realtime_listener.py -v

# Run specific test
poetry run pytest apps/hrm/tests/test_services.py::TestAttendanceDeviceService::test_connect_success -v

# Run realtime listener tests
poetry run pytest apps/hrm/tests/test_realtime_listener.py -v
```

### Integration Tests

**Prerequisites:**
- Real attendance device accessible on network
- Device configured in database

**Steps:**
1. Create test device via Django admin or API
2. Run manual test script
3. Select option 2 (Test connection)
4. Select option 3 (Manual sync)
5. Select option 5 (View records)

## Security Considerations

1. **Password Storage**: Device passwords stored in database - consider encryption at rest
2. **Network Security**: Devices should be on isolated/secured network
3. **API Access**: Device CRUD operations should be restricted to admins only
4. **Raw Data**: Contains potentially sensitive information - access control required

## Performance

### Optimization Tips

1. **Indexing**: Ensure database indexes are maintained
2. **Filtering**: Only sync current day logs (configurable in task)
3. **Batch Processing**: Records saved in transaction for atomicity
4. **Connection Pooling**: Each task creates new connection (stateless)

### Scalability

- System scales horizontally with more Celery workers
- Each device sync runs independently
- No shared state between device syncs
- Database handles concurrent writes with row-level locking

## Support

For issues or questions:
1. Check logs in `apps/hrm/tasks.py` and `apps/hrm/services.py`
2. Review Celery worker and beat logs
3. Use manual test script for debugging
4. Contact development team for assistance
