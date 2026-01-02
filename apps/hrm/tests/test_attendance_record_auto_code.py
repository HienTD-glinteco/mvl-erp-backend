"""Tests for AttendanceRecord auto-code generation."""

from datetime import datetime, timezone

import pytest

from apps.hrm.models import AttendanceDevice, AttendanceRecord


@pytest.mark.django_db
class TestAttendanceRecordAutoCodeGeneration:
    """Test cases for AttendanceRecord auto-code generation.

    Note: AttendanceRecord doesn't have a create API endpoint.
    Records are created by the system during device synchronization.
    These tests verify the auto-code generation at the model level.
    """

    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        """Set up test data."""
        # Create a device for records
        self.device = AttendanceDevice.objects.create(
            name="Test Device",
            ip_address="192.168.1.100",
            port=4370,
        )

    def test_create_record_without_code_auto_generates(self):
        """Test creating a record without code field auto-generates code."""
        # Act
        record = AttendanceRecord.objects.create(
            biometric_device=self.device,
            attendance_code="EMP001",
            timestamp=datetime(2025, 11, 14, 8, 0, 0, tzinfo=timezone.utc),
            is_valid=True,
        )

        # Assert
        assert record.code is not None
        assert record.code.startswith("DD")

    def test_sequential_code_generation(self):
        """Test that sequential records get sequential codes."""
        # Act - Create 3 records
        codes = []
        for i in range(3):
            record = AttendanceRecord.objects.create(
                biometric_device=self.device,
                attendance_code=f"EMP00{i + 1}",
                timestamp=datetime(2025, 11, 14, 8, i, 0, tzinfo=timezone.utc),
                is_valid=True,
            )
            codes.append(record.code)

        # Assert - Verify codes are sequential
        assert len(codes) == 3
        for code in codes:
            assert code.startswith("DD")

        # Verify all codes are unique
        assert len(set(codes)) == 3

        # Verify codes are in database
        records = AttendanceRecord.objects.all().order_by("id")
        assert records.count() == 3
        for record, code in zip(records, codes, strict=True):
            assert record.code == code

    def test_code_not_changed_on_update(self):
        """Test that code is not changed when record is updated."""
        # Arrange - Create initial record
        record = AttendanceRecord.objects.create(
            biometric_device=self.device,
            attendance_code="EMP001",
            timestamp=datetime(2025, 11, 14, 8, 0, 0, tzinfo=timezone.utc),
            is_valid=True,
        )
        original_code = record.code

        # Act - Update record
        record.attendance_code = "EMP002"
        record.is_valid = False
        record.save()

        # Assert - Verify code was NOT changed
        record.refresh_from_db()
        assert record.code == original_code

    def test_code_prefix_is_correct(self):
        """Test that generated code uses correct prefix (DD)."""
        # Act
        record = AttendanceRecord.objects.create(
            biometric_device=self.device,
            attendance_code="EMP001",
            timestamp=datetime(2025, 11, 14, 8, 0, 0, tzinfo=timezone.utc),
            is_valid=True,
        )

        # Assert
        assert record.code.startswith("DD")

        # Verify the code format (DD followed by digits)
        code = record.code
        assert code[:2] == "DD"
        assert code[2:].isdigit()

    def test_code_generation_with_existing_records(self):
        """Test that code generation continues from last code when records exist."""
        # Arrange - Create first record
        record1 = AttendanceRecord.objects.create(
            biometric_device=self.device,
            attendance_code="EMP001",
            timestamp=datetime(2025, 11, 14, 8, 0, 0, tzinfo=timezone.utc),
            is_valid=True,
        )
        first_code = record1.code

        # Act - Create second record
        record2 = AttendanceRecord.objects.create(
            biometric_device=self.device,
            attendance_code="EMP002",
            timestamp=datetime(2025, 11, 14, 9, 0, 0, tzinfo=timezone.utc),
            is_valid=True,
        )
        second_code = record2.code

        # Assert - Verify second code is different and sequential
        assert first_code != second_code
        assert first_code.startswith("DD")
        assert second_code.startswith("DD")

        # Extract numbers and verify they're sequential
        first_num = int(first_code[2:])
        second_num = int(second_code[2:])
        assert second_num == first_num + 1

    def test_code_uniqueness_constraint(self):
        """Test that duplicate codes cannot be created."""
        # Arrange - Create first record
        record1 = AttendanceRecord.objects.create(
            biometric_device=self.device,
            attendance_code="EMP001",
            timestamp=datetime(2025, 11, 14, 8, 0, 0, tzinfo=timezone.utc),
            is_valid=True,
        )

        # Act & Assert - Try to create another record with same code should fail
        with pytest.raises(Exception):
            AttendanceRecord.objects.create(
                biometric_device=self.device,
                code=record1.code,  # Use same code
                attendance_code="EMP002",
                timestamp=datetime(2025, 11, 14, 9, 0, 0, tzinfo=timezone.utc),
                is_valid=True,
            )
