"""Celery tasks for HRM attendance synchronization."""

import logging
from datetime import timedelta

from celery import shared_task
from celery.exceptions import Retry
from django.utils import timezone as django_timezone

from apps.hrm.models import AttendanceDevice, AttendanceRecord
from apps.hrm.services import AttendanceDeviceConnectionError, AttendanceDeviceService

logger = logging.getLogger(__name__)

# Constants
SYNC_RETRY_DELAY = 300  # 5 minutes
SYNC_MAX_RETRIES = 3
SYNC_DEFAULT_LOOKBACK_DAYS = 1  # Default to sync last 1 day of logs
BULK_CREATE_BATCH_SIZE = 1000  # Number of records to create in each batch


@shared_task(bind=True, max_retries=SYNC_MAX_RETRIES)
def sync_attendance_logs_for_device(self, device_id: int) -> dict[str, any]:
    """Sync attendance logs from a single device.

    This task connects to an attendance device, fetches recent logs,
    and stores them in the database. It handles errors, retries,
    and updates device connection status.

    Args:
        self: Celery task instance
        device_id: ID of the AttendanceDevice to sync

    Returns:
        dict: Synchronization result with keys:
            - success: bool indicating if sync succeeded
            - device_id: int device ID
            - device_name: str device name
            - logs_synced: int number of new logs synced
            - error: str error message (if failed)
    """
    try:
        # Fetch device from database
        try:
            device = AttendanceDevice.objects.get(id=device_id)
        except AttendanceDevice.DoesNotExist:
            error_msg = f"Device with ID {device_id} does not exist"
            logger.error(error_msg)
            return {
                "success": False,
                "device_id": device_id,
                "device_name": "Unknown",
                "logs_synced": 0,
                "error": error_msg,
            }

        logger.info(f"Starting attendance log sync for device: {device.name} (ID: {device_id})")

        # Determine start time for log fetching
        # Use last successful sync time or default to 1 day ago
        start_datetime = device.polling_synced_at
        if not start_datetime:
            start_datetime = django_timezone.now() - timedelta(days=SYNC_DEFAULT_LOOKBACK_DAYS)
            logger.info(
                f"No previous sync time for device {device.name}. "
                f"Fetching logs from {SYNC_DEFAULT_LOOKBACK_DAYS} day(s) ago"
            )
        else:
            logger.info(f"Fetching logs for device {device.name} since last sync at {start_datetime}")

        # Connect to device and fetch logs
        logs_synced = 0
        service = AttendanceDeviceService(device)

        try:
            with service:
                # Fetch attendance logs
                logs = service.get_attendance_logs(start_datetime=start_datetime)

                # Filter for current day only (as per requirements)
                today_start = django_timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
                today_logs = [log for log in logs if log["timestamp"] >= today_start]

                logger.info(
                    f"Device {device.name}: Retrieved {len(logs)} total logs, "
                    f"{len(today_logs)} from today ({today_start.date()})"
                )

                # Save logs to database using bulk operations
                if not today_logs:
                    logger.info(f"No logs from today for device {device.name}")
                    logs_synced = 0
                else:
                    # Group logs by attendance_code for efficient querying
                    attendance_codes = {log["user_id"] for log in today_logs}

                    # Fetch existing records using iterator to avoid loading all into memory
                    # This prevents issues when dealing with large datasets (e.g., 50k records)
                    existing_records_query = AttendanceRecord.objects.filter(
                        device=device,
                        attendance_code__in=attendance_codes,
                        timestamp__gte=today_start,
                    ).values_list("attendance_code", "timestamp")
                    
                    # Use iterator to fetch records in chunks, reducing memory usage
                    existing_set = {(code, ts) for code, ts in existing_records_query.iterator(chunk_size=1000)}

                    # Determine which logs are missing
                    records_to_create = []
                    for log in today_logs:
                        # Check if this specific log already exists
                        key = (log["user_id"], log["timestamp"])
                        if key not in existing_set:
                            # Convert datetime to ISO format for JSON storage
                            raw_data = log.copy()
                            raw_data["timestamp"] = log["timestamp"].isoformat()

                            records_to_create.append(
                                AttendanceRecord(
                                    device=device,
                                    attendance_code=log["user_id"],
                                    timestamp=log["timestamp"],
                                    raw_data=raw_data,
                                )
                            )

                    # Bulk create all missing records in batches
                    if records_to_create:
                        AttendanceRecord.objects.bulk_create(records_to_create, batch_size=BULK_CREATE_BATCH_SIZE)
                        logs_synced = len(records_to_create)
                        logger.info(f"Created {logs_synced} new attendance records for device {device.name}")
                    else:
                        logs_synced = 0
                        logger.info(f"All logs already exist for device {device.name}, no new records created")

                # Update device status on success
                device.is_connected = True
                device.polling_synced_at = django_timezone.now()
                device.save(update_fields=["is_connected", "polling_synced_at", "updated_at"])

                logger.info(
                    f"Successfully synced {logs_synced} new attendance logs for device {device.name} "
                    f"(out of {len(today_logs)} total today's logs)"
                )

                return {
                    "success": True,
                    "device_id": device_id,
                    "device_name": device.name,
                    "logs_synced": logs_synced,
                    "total_today_logs": len(today_logs),
                    "error": None,
                }

        except AttendanceDeviceConnectionError as e:
            # Connection failed - update device status and retry
            error_msg = str(e)
            logger.warning(f"Connection failed for device {device.name}: {error_msg}")

            # Update device connection status
            device.is_connected = False
            device.save(update_fields=["is_connected", "updated_at"])

            # Retry the task with exponential backoff
            retry_countdown = SYNC_RETRY_DELAY * (2**self.request.retries)
            logger.info(
                f"Retrying sync for device {device.name} in {retry_countdown} seconds "
                f"(attempt {self.request.retries + 1}/{SYNC_MAX_RETRIES})"
            )

            raise self.retry(exc=e, countdown=retry_countdown)

    except Retry:
        # Re-raise Retry exceptions so they propagate correctly
        raise

    except Exception as e:
        # Unexpected error - log and return failure
        logger.exception(f"Unexpected error during sync for device ID {device_id}: {str(e)}")

        # Try to update device status if we have device object
        try:
            if "device" in locals():
                device.is_connected = False
                device.save(update_fields=["is_connected", "updated_at"])
        except Exception:
            pass

        return {
            "success": False,
            "device_id": device_id,
            "device_name": getattr(locals().get("device"), "name", "Unknown"),
            "logs_synced": 0,
            "error": str(e),
        }


@shared_task
def sync_all_attendance_devices() -> dict[str, any]:
    """Sync attendance logs from all active devices.

    This is the main periodic task that runs on schedule.
    It triggers individual sync tasks for each device.

    Returns:
        dict: Summary of sync results with keys:
            - total_devices: int total number of devices
            - tasks_triggered: int number of sync tasks started
            - device_ids: list of device IDs that were processed
    """
    logger.info("Starting periodic attendance log sync for all devices")

    # Get all enabled devices
    devices = list(AttendanceDevice.objects.filter(is_enabled=True))
    total_devices = len(devices)

    logger.info(f"Found {total_devices} enabled attendance device(s) to sync")

    # Trigger individual sync tasks for each device
    tasks_triggered = 0
    device_ids = []

    for device in devices:
        try:
            sync_attendance_logs_for_device.delay(device.id)
            tasks_triggered += 1
            device_ids.append(device.id)
            logger.debug(f"Triggered sync task for device: {device.name} (ID: {device.id})")
        except Exception as e:
            logger.error(f"Failed to trigger sync task for device {device.name} (ID: {device.id}): {str(e)}")

    logger.info(f"Triggered {tasks_triggered} sync tasks for {total_devices} devices")

    return {
        "total_devices": total_devices,
        "tasks_triggered": tasks_triggered,
        "device_ids": device_ids,
    }
