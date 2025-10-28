"""Manual test script for PyZK integration and attendance synchronization.

This script provides manual testing utilities for:
1. Testing connection to attendance devices
2. Manually triggering sync tasks
3. Inspecting synced attendance records

Usage:
    poetry run python -m apps.hrm.manual_test_attendance_sync

Requirements:
    - At least one AttendanceDevice configured in the database
    - Network access to the attendance device
"""

import logging
import sys

import django

# Setup Django
django.setup()

# ruff: noqa: E402 - Django imports must come after django.setup()
from apps.hrm.models import AttendanceDevice, AttendanceRecord
from apps.hrm.services import AttendanceDeviceService
from apps.hrm.tasks import sync_all_attendance_devices, sync_attendance_logs_for_device

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def test_device_connection(device_id: int) -> None:
    """Test connection to a specific device.

    Args:
        device_id: ID of the AttendanceDevice to test
    """
    logger.info(f"Testing connection to device ID: {device_id}")

    try:
        device = AttendanceDevice.objects.get(id=device_id)
        logger.info(f"Found device: {device.name} at {device.ip_address}:{device.port}")

        service = AttendanceDeviceService(device)
        success, message = service.test_connection()

        if success:
            logger.info(f"✓ Connection test successful: {message}")
        else:
            logger.error(f"✗ Connection test failed: {message}")

    except AttendanceDevice.DoesNotExist:
        logger.error(f"Device with ID {device_id} not found")
    except Exception as e:
        logger.exception(f"Error testing device connection: {str(e)}")


def manual_sync_device(device_id: int) -> None:
    """Manually trigger sync for a specific device.

    Args:
        device_id: ID of the AttendanceDevice to sync
    """
    logger.info(f"Manually triggering sync for device ID: {device_id}")

    try:
        result = sync_attendance_logs_for_device(device_id)
        logger.info(f"Sync result: {result}")

        if result["success"]:
            logger.info(f"✓ Sync successful: {result['logs_synced']} new logs synced")
        else:
            logger.error(f"✗ Sync failed: {result['error']}")

    except Exception as e:
        logger.exception(f"Error during manual sync: {str(e)}")


def manual_sync_all() -> None:
    """Manually trigger sync for all devices."""
    logger.info("Manually triggering sync for all devices")

    try:
        result = sync_all_attendance_devices()
        logger.info(f"Sync all result: {result}")
        logger.info(f"✓ Triggered {result['tasks_triggered']} sync tasks for {result['total_devices']} devices")

    except Exception as e:
        logger.exception(f"Error during sync all: {str(e)}")


def list_devices() -> None:
    """List all configured attendance devices."""
    logger.info("Listing all attendance devices")

    devices = AttendanceDevice.objects.all()
    if not devices:
        logger.info("No attendance devices configured")
        return

    logger.info(f"Found {devices.count()} device(s):")
    for device in devices:
        logger.info(
            f"  - ID: {device.id}, Name: {device.name}, "
            f"IP: {device.ip_address}:{device.port}, "
            f"Connected: {device.is_connected}, "
            f"Last sync: {device.polling_synced_at or 'Never'}"
        )


def list_recent_records(device_id: int | None = None, limit: int = 10) -> None:
    """List recent attendance records.

    Args:
        device_id: Optional device ID to filter records
        limit: Maximum number of records to show
    """
    logger.info(f"Listing recent attendance records (limit: {limit})")

    records = AttendanceRecord.objects.all()
    if device_id:
        records = records.filter(device_id=device_id)

    records = records[:limit]

    if not records:
        logger.info("No attendance records found")
        return

    logger.info(f"Found {records.count()} recent record(s):")
    for record in records:
        logger.info(
            f"  - ID: {record.id}, Device: {record.device.name}, "
            f"Code: {record.attendance_code}, "
            f"Time: {record.timestamp}, "
            f"Raw: {record.raw_data}"
        )


def interactive_menu() -> None:  # noqa: C901 - Menu function naturally has many branches
    """Interactive menu for manual testing."""
    while True:
        print("\n" + "=" * 60)
        print("Attendance Sync Manual Testing")
        print("=" * 60)
        print("1. List all devices")
        print("2. Test device connection")
        print("3. Manual sync single device")
        print("4. Manual sync all devices")
        print("5. List recent attendance records")
        print("6. Exit")
        print("=" * 60)

        choice = input("Enter choice (1-6): ").strip()

        if choice == "1":
            list_devices()
        elif choice == "2":
            device_id = input("Enter device ID: ").strip()
            try:
                test_device_connection(int(device_id))
            except ValueError:
                logger.error("Invalid device ID")
        elif choice == "3":
            device_id = input("Enter device ID: ").strip()
            try:
                manual_sync_device(int(device_id))
            except ValueError:
                logger.error("Invalid device ID")
        elif choice == "4":
            manual_sync_all()
        elif choice == "5":
            device_id = input("Enter device ID (leave empty for all): ").strip()
            limit = input("Enter limit (default 10): ").strip()
            try:
                device_id = int(device_id) if device_id else None
                limit = int(limit) if limit else 10
                list_recent_records(device_id, limit)
            except ValueError:
                logger.error("Invalid input")
        elif choice == "6":
            logger.info("Exiting...")
            sys.exit(0)
        else:
            logger.warning("Invalid choice. Please try again.")


if __name__ == "__main__":
    logger.info("Starting manual test script")
    interactive_menu()
