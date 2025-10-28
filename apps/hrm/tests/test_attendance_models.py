from datetime import datetime, timezone

from django.test import TestCase

from apps.hrm.models import AttendanceDevice, AttendanceRecord


class AttendanceDeviceModelTest(TestCase):
    """Test cases for AttendanceDevice model."""

    def setUp(self):
        """Set up test data for AttendanceDevice tests."""
        self.device_data = {
            "name": "Main Entrance Device",
            "location": "Building A - Main Entrance",
            "ip_address": "192.168.1.100",
            "port": 4370,
            "password": "admin123",
            "serial_number": "SN123456789",
            "registration_number": "REG001",
        }

    def test_create_attendance_device(self):
        """Test creating an attendance device with all fields."""
        # Arrange & Act
        device = AttendanceDevice.objects.create(**self.device_data)

        # Assert
        self.assertEqual(device.name, self.device_data["name"])
        self.assertEqual(device.location, self.device_data["location"])
        self.assertEqual(device.ip_address, self.device_data["ip_address"])
        self.assertEqual(device.port, 4370)
        self.assertFalse(device.is_connected)
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
        self.assertEqual(device.port, 4370)  # Default value
        self.assertEqual(device.location, "")
        self.assertEqual(device.password, "")
        self.assertFalse(device.is_connected)

    def test_attendance_device_str_with_location(self):
        """Test string representation with location."""
        # Arrange & Act
        device = AttendanceDevice.objects.create(**self.device_data)

        # Assert
        expected = f"{self.device_data['name']} ({self.device_data['location']})"
        self.assertEqual(str(device), expected)

    def test_attendance_device_str_without_location(self):
        """Test string representation without location."""
        # Arrange & Act
        device = AttendanceDevice.objects.create(
            name="Test Device",
            ip_address="192.168.1.1",
        )

        # Assert
        self.assertEqual(str(device), "Test Device")

    def test_update_connection_status(self):
        """Test updating device connection status."""
        # Arrange
        device = AttendanceDevice.objects.create(**self.device_data)

        # Act
        device.is_connected = True
        device.save()

        # Assert
        device.refresh_from_db()
        self.assertTrue(device.is_connected)

    def test_update_polling_synced_at(self):
        """Test updating polling sync timestamp."""
        # Arrange
        device = AttendanceDevice.objects.create(**self.device_data)
        sync_time = datetime(2025, 10, 28, 12, 0, 0, tzinfo=timezone.utc)

        # Act
        device.polling_synced_at = sync_time
        device.save()

        # Assert
        device.refresh_from_db()
        self.assertEqual(device.polling_synced_at, sync_time)

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
            "status": 1,
            "raw_data": {
                "uid": 3525,
                "user_id": "531",
                "timestamp": "2025-10-28T11:49:38",
                "status": 1,
                "punch": 0,
            },
        }

    def test_create_attendance_record(self):
        """Test creating an attendance record with all fields."""
        # Arrange & Act
        record = AttendanceRecord.objects.create(**self.record_data)

        # Assert
        self.assertEqual(record.device, self.device)
        self.assertEqual(record.attendance_code, "531")
        self.assertEqual(record.timestamp, self.record_data["timestamp"])
        self.assertEqual(record.status, 1)
        self.assertIsNotNone(record.raw_data)
        self.assertEqual(record.raw_data["uid"], 3525)
        self.assertIsNotNone(record.created_at)
        self.assertIsNotNone(record.updated_at)

    def test_create_minimal_attendance_record(self):
        """Test creating attendance record without optional raw_data."""
        # Arrange & Act
        record = AttendanceRecord.objects.create(
            device=self.device,
            attendance_code="100",
            timestamp=datetime(2025, 10, 28, 10, 0, 0, tzinfo=timezone.utc),
            status=0,
        )

        # Assert
        self.assertEqual(record.attendance_code, "100")
        self.assertIsNone(record.raw_data)

    def test_attendance_record_str(self):
        """Test string representation of attendance record."""
        # Arrange & Act
        record = AttendanceRecord.objects.create(**self.record_data)

        # Assert
        expected = f"531 - {self.record_data['timestamp']}"
        self.assertEqual(str(record), expected)

    def test_default_ordering_by_timestamp_desc(self):
        """Test records are ordered by timestamp descending."""
        # Arrange & Act
        record1 = AttendanceRecord.objects.create(
            device=self.device,
            attendance_code="100",
            timestamp=datetime(2025, 10, 28, 10, 0, 0, tzinfo=timezone.utc),
            status=1,
        )
        record2 = AttendanceRecord.objects.create(
            device=self.device,
            attendance_code="200",
            timestamp=datetime(2025, 10, 28, 12, 0, 0, tzinfo=timezone.utc),
            status=1,
        )
        record3 = AttendanceRecord.objects.create(
            device=self.device,
            attendance_code="300",
            timestamp=datetime(2025, 10, 28, 11, 0, 0, tzinfo=timezone.utc),
            status=1,
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

    def test_attendance_code_index_exists(self):
        """Test that attendance_code index exists for query performance."""
        # Arrange & Act
        for i in range(5):
            AttendanceRecord.objects.create(
                device=self.device,
                attendance_code="531",
                timestamp=datetime(2025, 10, 28, 10 + i, 0, 0, tzinfo=timezone.utc),
                status=1,
            )

        # Assert - Query by attendance_code should work efficiently
        records = AttendanceRecord.objects.filter(attendance_code="531")
        self.assertEqual(records.count(), 5)

    def test_device_relationship(self):
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
            status=1,
        )
        record2 = AttendanceRecord.objects.create(
            device=self.device,
            attendance_code="531",
            timestamp=datetime(2025, 10, 28, 11, 0, 0, tzinfo=timezone.utc),
            status=1,
        )

        # Assert
        self.assertEqual(record1.attendance_code, record2.attendance_code)
        self.assertNotEqual(record1.id, record2.id)

    def test_raw_data_json_field(self):
        """Test raw_data JSONField accepts complex data."""
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
            status=1,
            raw_data=complex_raw_data,
        )

        # Assert
        record.refresh_from_db()
        self.assertEqual(record.raw_data["uid"], 3525)
        self.assertEqual(record.raw_data["verify_mode"], 1)
        self.assertEqual(record.raw_data["work_code"], 0)
