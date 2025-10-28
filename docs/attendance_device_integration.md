# Attendance Device Integration with PyZK

This document describes the PyZK integration and polling-based attendance log synchronization system.

## Overview

The system integrates with ZKTeco (and compatible) attendance devices using the PyZK library. It provides:

- **Service Layer**: Reusable connection and data fetching logic
- **Polling Tasks**: Automatic periodic synchronization via Celery
- **Error Handling**: Robust retry logic with exponential backoff
- **Data Storage**: Attendance records stored in PostgreSQL with timestamp indexing

## Architecture

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

## Models

### AttendanceDevice

Stores configuration for physical attendance devices.

**Key Fields:**
- `name`: Human-readable device identifier
- `ip_address`: Device network address
- `port`: Network port (default: 4370)
- `password`: Device authentication password
- `is_connected`: Current connection status
- `polling_synced_at`: Last successful sync timestamp

### AttendanceRecord

Stores individual attendance clock-in/out records from devices.

**Key Fields:**
- `device`: Foreign key to AttendanceDevice
- `attendance_code`: User ID from device (matches Employee.attendance_code)
- `timestamp`: Date/time of attendance event
- `raw_data`: JSON field with complete device data for debugging

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

**Customization:**
- Modify crontab schedule as needed
- Default: Every 5 minutes
- Can be changed to hourly, daily, etc.

## Manual Testing

Use the provided manual test script:

```bash
poetry run python -m apps.hrm.manual_test_attendance_sync
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

**Not implemented yet (out of scope for this task):**
- Real-time log synchronization (push-based)
- Employee matching based on attendance_code
- Attendance analytics and reporting
- Web UI for device management
- Device health monitoring dashboard
- Historical data migration

## Testing

### Unit Tests

```bash
# Run all attendance-related tests
poetry run pytest apps/hrm/tests/test_services.py -v
poetry run pytest apps/hrm/tests/test_tasks.py -v

# Run specific test
poetry run pytest apps/hrm/tests/test_services.py::TestAttendanceDeviceService::test_connect_success -v
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
