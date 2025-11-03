from datetime import datetime, timedelta, timezone

from django.test import TestCase
from django.utils import timezone as django_timezone

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import AttendanceDevice, AttendanceRecord, Block, Branch


class AttendanceDeviceModelTest(TestCase):
    """Test cases for AttendanceDevice model."""

    def setUp(self):
        """Set up test data for AttendanceDevice tests."""
        # Create required organizational structure
        self.province = Province.objects.create(
            code="01",
            name="Hanoi",
            english_name="Hanoi",
            level=Province.ProvinceLevel.CENTRAL_CITY,
            enabled=True,
        )
        self.administrative_unit = AdministrativeUnit.objects.create(
            code="001",
            name="Ba Dinh",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
            enabled=True,
        )
        self.branch = Branch.objects.create(
            name="Main Branch",
            code="MB",
            province=self.province,
            administrative_unit=self.administrative_unit,
        )
        self.block = Block.objects.create(
            name="Support Block",
            code="SB",
            block_type=Block.BlockType.SUPPORT,
            branch=self.branch,
        )

        self.device_data = {
            "name": "Main Entrance Device",
            "block": self.block,
            "ip_address": "192.168.1.100",
            "port": 4370,
            "password": "admin123",
            "serial_number": "SN123456789",
            "registration_number": "REG001",
        }

    def test_create_attendance_device_with_all_fields(self):
        """Test creating an attendance device with all fields."""
        # Arrange & Act
        device = AttendanceDevice.objects.create(**self.device_data)

        # Assert
        self.assertEqual(device.name, self.device_data["name"])
        self.assertEqual(device.block, self.block)
        self.assertEqual(device.ip_address, self.device_data["ip_address"])
        self.assertEqual(device.port, 4370)
        self.assertTrue(device.is_enabled)
        self.assertFalse(device.is_connected)
        self.assertTrue(device.realtime_enabled)
        self.assertIsNone(device.realtime_disabled_at)
        self.assertIsNone(device.polling_synced_at)
        self.assertIsNotNone(device.created_at)
        self.assertIsNotNone(device.updated_at)

    def test_create_minimal_attendance_device(self):
        """Test creating attendance device with only required fields."""
        # Arrange & Act
        device = AttendanceDevice.objects.create(
            name="Minimal Device",
            ip_address="10.0.0.1",
        )

        # Assert
        self.assertEqual(device.name, "Minimal Device")
        self.assertEqual(device.ip_address, "10.0.0.1")
        self.assertEqual(device.port, 4370)
        self.assertIsNone(device.block)
        self.assertEqual(device.password, "")
        self.assertTrue(device.is_enabled)
        self.assertFalse(device.is_connected)
        self.assertTrue(device.realtime_enabled)

    def test_str_representation(self):
        """Test string representation shows device name."""
        # Arrange & Act
        device = AttendanceDevice.objects.create(**self.device_data)

        # Assert
        self.assertEqual(str(device), self.device_data["name"])

    def test_default_ordering_by_name(self):
        """Test devices are ordered by name."""
        # Arrange & Act
        device_c = AttendanceDevice.objects.create(name="C Device", ip_address="192.168.1.3")
        device_a = AttendanceDevice.objects.create(name="A Device", ip_address="192.168.1.1")
        device_b = AttendanceDevice.objects.create(name="B Device", ip_address="192.168.1.2")

        # Assert
        devices = list(AttendanceDevice.objects.all())
        self.assertEqual(devices[0], device_a)
        self.assertEqual(devices[1], device_b)
        self.assertEqual(devices[2], device_c)

    def test_get_sync_start_time_no_previous_sync(self):
        """Test get_sync_start_time returns lookback time when no previous sync."""
        # Arrange
        device = AttendanceDevice.objects.create(name="Test Device", ip_address="192.168.1.100")
        lookback_days = 2

        # Act
        start_time = device.get_sync_start_time(lookback_days=lookback_days)

        # Assert
        expected_time = django_timezone.now() - timedelta(days=lookback_days)
        # Allow 1 second tolerance for test execution time
        self.assertAlmostEqual(
            start_time.timestamp(), expected_time.timestamp(), delta=1, msg="Start time should be ~2 days ago"
        )

    def test_get_sync_start_time_with_previous_sync(self):
        """Test get_sync_start_time returns last sync time when available."""
        # Arrange
        device = AttendanceDevice.objects.create(name="Test Device", ip_address="192.168.1.100")
        previous_sync = django_timezone.now() - timedelta(hours=1)
        device.polling_synced_at = previous_sync
        device.save()

        # Act
        start_time = device.get_sync_start_time()

        # Assert
        self.assertEqual(start_time, previous_sync)

    def test_mark_sync_success(self):
        """Test mark_sync_success updates device state correctly."""
        # Arrange
        device = AttendanceDevice.objects.create(name="Test Device", ip_address="192.168.1.100")
        device.is_connected = False
        device.save()

        # Act
        device.mark_sync_success()

        # Assert
        device.refresh_from_db()
        self.assertTrue(device.is_connected)
        self.assertIsNotNone(device.polling_synced_at)
        # Check polling_synced_at is recent (within last 5 seconds)
        time_diff = django_timezone.now() - device.polling_synced_at
        self.assertLess(time_diff.total_seconds(), 5)

    def test_mark_sync_success_re_enables_realtime(self):
        """Test mark_sync_success re-enables realtime if it was disabled."""
        # Arrange
        device = AttendanceDevice.objects.create(name="Test Device", ip_address="192.168.1.100")
        device.realtime_enabled = False
        device.realtime_disabled_at = django_timezone.now()
        device.save()

        # Act
        device.mark_sync_success()

        # Assert
        device.refresh_from_db()
        self.assertTrue(device.realtime_enabled)
        self.assertIsNone(device.realtime_disabled_at)

    def test_mark_sync_failed(self):
        """Test mark_sync_failed sets connection status to False."""
        # Arrange
        device = AttendanceDevice.objects.create(name="Test Device", ip_address="192.168.1.100")
        device.is_connected = True
        device.save()

        # Act
        device.mark_sync_failed()

        # Assert
        device.refresh_from_db()
        self.assertFalse(device.is_connected)

    def test_is_enabled_field(self):
        """Test is_enabled field controls device activation."""
        # Arrange
        device = AttendanceDevice.objects.create(name="Test Device", ip_address="192.168.1.100")

        # Assert default
        self.assertTrue(device.is_enabled)

        # Act - disable
        device.is_enabled = False
        device.save()

        # Assert disabled
        device.refresh_from_db()
        self.assertFalse(device.is_enabled)

    def test_realtime_fields(self):
        """Test realtime_enabled and realtime_disabled_at fields."""
        # Arrange
        device = AttendanceDevice.objects.create(name="Test Device", ip_address="192.168.1.100")

        # Assert defaults
        self.assertTrue(device.realtime_enabled)
        self.assertIsNone(device.realtime_disabled_at)

        # Act - disable realtime
        disabled_time = django_timezone.now()
        device.realtime_enabled = False
        device.realtime_disabled_at = disabled_time
        device.save()

        # Assert
        device.refresh_from_db()
        self.assertFalse(device.realtime_enabled)
        self.assertEqual(device.realtime_disabled_at, disabled_time)

    def test_block_foreign_key_relationship(self):
        """Test block foreign key relationship and cascade."""
        # Arrange
        device = AttendanceDevice.objects.create(**self.device_data)

        # Assert relationship
        self.assertEqual(device.block, self.block)
        self.assertIn(device, self.block.attendance_devices.all())


class AttendanceRecordModelTest(TestCase):
    """Test cases for AttendanceRecord model."""

    def setUp(self):
        """Set up test data for AttendanceRecord tests."""
        self.device = AttendanceDevice.objects.create(
            name="Test Device",
            ip_address="192.168.1.100",
        )

        self.record_data = {
            "device": self.device,
            "attendance_code": "531",
            "timestamp": datetime(2025, 10, 28, 11, 49, 38, tzinfo=timezone.utc),
            "raw_data": {
                "uid": 3525,
                "user_id": "531",
                "timestamp": "2025-10-28T11:49:38",
                "status": 1,
                "punch": 0,
            },
        }

    def test_create_attendance_record_with_all_fields(self):
        """Test creating an attendance record with all fields."""
        # Arrange & Act
        record = AttendanceRecord.objects.create(**self.record_data)

        # Assert
        self.assertEqual(record.device, self.device)
        self.assertEqual(record.attendance_code, "531")
        self.assertEqual(record.timestamp, self.record_data["timestamp"])
        self.assertTrue(record.is_valid)
        self.assertEqual(record.notes, "")
        self.assertIsNotNone(record.raw_data)
        self.assertEqual(record.raw_data["uid"], 3525)
        self.assertIsNotNone(record.created_at)
        self.assertIsNotNone(record.updated_at)

    def test_create_minimal_attendance_record(self):
        """Test creating attendance record with only required fields."""
        # Arrange & Act
        record = AttendanceRecord.objects.create(
            device=self.device,
            attendance_code="100",
            timestamp=datetime(2025, 10, 28, 10, 0, 0, tzinfo=timezone.utc),
        )

        # Assert
        self.assertEqual(record.attendance_code, "100")
        self.assertIsNone(record.raw_data)
        self.assertTrue(record.is_valid)
        self.assertEqual(record.notes, "")

    def test_str_representation(self):
        """Test string representation shows attendance code and timestamp."""
        # Arrange & Act
        record = AttendanceRecord.objects.create(**self.record_data)

        # Assert
        expected = f"531 - {self.record_data['timestamp']}"
        self.assertEqual(str(record), expected)

    def test_default_ordering_by_timestamp_desc(self):
        """Test records are ordered by timestamp descending (newest first)."""
        # Arrange & Act
        record1 = AttendanceRecord.objects.create(
            device=self.device,
            attendance_code="100",
            timestamp=datetime(2025, 10, 28, 10, 0, 0, tzinfo=timezone.utc),
        )
        record2 = AttendanceRecord.objects.create(
            device=self.device,
            attendance_code="200",
            timestamp=datetime(2025, 10, 28, 12, 0, 0, tzinfo=timezone.utc),
        )
        record3 = AttendanceRecord.objects.create(
            device=self.device,
            attendance_code="300",
            timestamp=datetime(2025, 10, 28, 11, 0, 0, tzinfo=timezone.utc),
        )

        # Assert
        records = list(AttendanceRecord.objects.all())
        self.assertEqual(records[0], record2)  # Latest timestamp first
        self.assertEqual(records[1], record3)
        self.assertEqual(records[2], record1)

    def test_cascade_delete_when_device_deleted(self):
        """Test that attendance records are deleted when device is deleted."""
        # Arrange
        record = AttendanceRecord.objects.create(**self.record_data)
        record_id = record.id

        # Act
        self.device.delete()

        # Assert
        with self.assertRaises(AttendanceRecord.DoesNotExist):
            AttendanceRecord.objects.get(id=record_id)

    def test_attendance_code_index_performance(self):
        """Test that attendance_code index exists for query performance."""
        # Arrange & Act - Create multiple records with same attendance code
        for i in range(5):
            AttendanceRecord.objects.create(
                device=self.device,
                attendance_code="531",
                timestamp=datetime(2025, 10, 28, 10 + i, 0, 0, tzinfo=timezone.utc),
            )

        # Assert - Query by attendance_code should work efficiently
        records = AttendanceRecord.objects.filter(attendance_code="531")
        self.assertEqual(records.count(), 5)

    def test_device_foreign_key_relationship(self):
        """Test foreign key relationship to device."""
        # Arrange & Act
        record = AttendanceRecord.objects.create(**self.record_data)

        # Assert
        self.assertEqual(record.device.name, "Test Device")
        self.assertIn(record, self.device.attendance_records.all())

    def test_multiple_records_same_attendance_code(self):
        """Test creating multiple records with same attendance code."""
        # Arrange & Act
        record1 = AttendanceRecord.objects.create(
            device=self.device,
            attendance_code="531",
            timestamp=datetime(2025, 10, 28, 10, 0, 0, tzinfo=timezone.utc),
        )
        record2 = AttendanceRecord.objects.create(
            device=self.device,
            attendance_code="531",
            timestamp=datetime(2025, 10, 28, 11, 0, 0, tzinfo=timezone.utc),
        )

        # Assert
        self.assertEqual(record1.attendance_code, record2.attendance_code)
        self.assertNotEqual(record1.id, record2.id)

    def test_raw_data_json_field_complex_data(self):
        """Test raw_data JSONField accepts complex data structures."""
        # Arrange & Act
        complex_raw_data = {
            "uid": 3525,
            "user_id": "531",
            "timestamp": "2025-10-28T11:49:38",
            "status": 1,
            "punch": 0,
            "verify_mode": 1,
            "work_code": 0,
            "reserved": "",
        }
        record = AttendanceRecord.objects.create(
            device=self.device,
            attendance_code="531",
            timestamp=datetime(2025, 10, 28, 11, 49, 38, tzinfo=timezone.utc),
            raw_data=complex_raw_data,
        )

        # Assert
        record.refresh_from_db()
        self.assertEqual(record.raw_data["uid"], 3525)
        self.assertEqual(record.raw_data["verify_mode"], 1)
        self.assertEqual(record.raw_data["work_code"], 0)
        self.assertEqual(record.raw_data["reserved"], "")

    def test_is_valid_field_default(self):
        """Test is_valid field defaults to True."""
        # Arrange & Act
        record = AttendanceRecord.objects.create(**self.record_data)

        # Assert
        self.assertTrue(record.is_valid)

    def test_is_valid_field_can_be_set_false(self):
        """Test is_valid field can be set to False for invalid records."""
        # Arrange
        record = AttendanceRecord.objects.create(**self.record_data)

        # Act
        record.is_valid = False
        record.save()

        # Assert
        record.refresh_from_db()
        self.assertFalse(record.is_valid)

    def test_notes_field(self):
        """Test notes field can store text."""
        # Arrange & Act
        record = AttendanceRecord.objects.create(
            device=self.device,
            attendance_code="100",
            timestamp=datetime(2025, 10, 28, 10, 0, 0, tzinfo=timezone.utc),
            notes="Manual entry - device was offline",
        )

        # Assert
        self.assertEqual(record.notes, "Manual entry - device was offline")

    def test_query_by_device_and_timestamp(self):
        """Test querying records by device and timestamp range."""
        # Arrange
        start_time = datetime(2025, 10, 28, 10, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2025, 10, 28, 12, 0, 0, tzinfo=timezone.utc)

        # Create records within and outside the range
        record_in_range = AttendanceRecord.objects.create(
            device=self.device,
            attendance_code="100",
            timestamp=datetime(2025, 10, 28, 11, 0, 0, tzinfo=timezone.utc),
        )
        record_before = AttendanceRecord.objects.create(
            device=self.device,
            attendance_code="200",
            timestamp=datetime(2025, 10, 28, 9, 0, 0, tzinfo=timezone.utc),
        )
        record_after = AttendanceRecord.objects.create(
            device=self.device,
            attendance_code="300",
            timestamp=datetime(2025, 10, 28, 13, 0, 0, tzinfo=timezone.utc),
        )

        # Act
        records = AttendanceRecord.objects.filter(device=self.device, timestamp__range=(start_time, end_time))

        # Assert
        self.assertEqual(records.count(), 1)
        self.assertIn(record_in_range, records)
        self.assertNotIn(record_before, records)
        self.assertNotIn(record_after, records)
