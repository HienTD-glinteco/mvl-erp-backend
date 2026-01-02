from datetime import datetime, timezone

import pytest
from django.urls import reverse
from rest_framework import status

from apps.hrm.models import AttendanceDevice, AttendanceRecord


class APITestMixin:
    """Mixin to handle wrapped API responses and data extraction."""

    def get_response_data(self, response):
        """Extract data from wrapped API response."""
        content = response.json()
        if "data" in content:
            data = content["data"]
            # Handle paginated responses - extract results list
            if isinstance(data, dict) and "results" in data:
                return data["results"]
            return data
        return content


@pytest.mark.django_db
class TestAttendanceRecordAPI(APITestMixin):
    """Test cases for AttendanceRecord API endpoints."""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client):
        self.client = api_client

    @pytest.fixture
    def devices(self, db):
        """Create test devices."""
        device1 = AttendanceDevice.objects.create(name="Main Entrance Device", ip_address="192.168.1.100", port=4370)
        device2 = AttendanceDevice.objects.create(name="Back Door Device", ip_address="192.168.1.101", port=4370)
        return device1, device2

    @pytest.fixture
    def records(self, devices):
        """Create test records."""
        device1, device2 = devices
        record1 = AttendanceRecord.objects.create(
            biometric_device=device1,
            attendance_code="531",
            timestamp=datetime(2025, 10, 28, 8, 30, 15, tzinfo=timezone.utc),
            raw_data={"uid": 3525, "user_id": "531", "timestamp": "2025-10-28T08:30:15", "status": 1, "punch": 0},
        )
        record2 = AttendanceRecord.objects.create(
            biometric_device=device1,
            attendance_code="531",
            timestamp=datetime(2025, 10, 28, 11, 49, 38, tzinfo=timezone.utc),
            raw_data={"uid": 3525, "user_id": "531", "timestamp": "2025-10-28T11:49:38", "status": 1, "punch": 0},
        )
        record3 = AttendanceRecord.objects.create(
            biometric_device=device2,
            attendance_code="100",
            timestamp=datetime(2025, 10, 28, 9, 0, 0, tzinfo=timezone.utc),
            raw_data={"uid": 1000, "user_id": "100", "timestamp": "2025-10-28T09:00:00", "status": 1, "punch": 0},
        )
        return record1, record2, record3

    def test_list_attendance_records(self, devices, records):
        """Test listing attendance records."""
        record1, record2, record3 = records

        # Act
        url = reverse("hrm:attendance-record-list")
        response = self.client.get(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 3

        # Check ordering (should be by timestamp descending)
        assert response_data[0]["id"] == record2.id  # Latest first
        assert response_data[1]["id"] == record3.id
        assert response_data[2]["id"] == record1.id  # Earliest last

    def test_retrieve_attendance_record(self, devices, records):
        """Test retrieving a specific attendance record."""
        record1, _, _ = records

        # Act
        url = reverse("hrm:attendance-record-detail", kwargs={"pk": record1.id})
        response = self.client.get(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert response_data["attendance_code"] == "531"
        assert response_data["biometric_device"]["name"] == "Main Entrance Device"
        assert "raw_data" in response_data
        assert response_data["raw_data"]["user_id"] == "531"

    def test_attendance_records_are_read_only(self, devices, records):
        """Test that attendance records cannot be created via API."""
        device1, _ = devices

        # Arrange
        record_data = {
            "device": device1.id,
            "attendance_code": "999",
            "timestamp": "2025-10-28T12:00:00Z",
        }

        # Act - Try to create
        url = reverse("hrm:attendance-record-list")
        response = self.client.post(url, record_data, format="json")

        # Assert - Should not be allowed
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_attendance_records_cannot_be_deleted(self, devices, records):
        """Test that attendance records cannot be deleted via API."""
        record1, _, _ = records

        # Act
        url = reverse("hrm:attendance-record-detail", kwargs={"pk": record1.id})
        response = self.client.delete(url)

        # Assert - Should not be allowed
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
        # Verify record still exists
        assert AttendanceRecord.objects.filter(id=record1.id).exists()

    def test_filter_by_device(self, devices, records):
        """Test filtering attendance records by biometric device."""
        device1, _ = devices

        # Act
        url = reverse("hrm:attendance-record-list")
        response = self.client.get(url, {"biometric_device": device1.id})

        # Assert
        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 2
        for record in response_data:
            assert record["biometric_device"]["id"] == device1.id

    def test_filter_by_attendance_code(self, devices, records):
        """Test filtering attendance records by attendance code."""
        # Act
        url = reverse("hrm:attendance-record-list")
        response = self.client.get(url, {"attendance_code": "531"})

        # Assert
        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 2
        for record in response_data:
            assert "531" in record["attendance_code"]

    def test_filter_by_timestamp_after(self, devices, records):
        """Test filtering attendance records by timestamp_after."""
        # Act
        url = reverse("hrm:attendance-record-list")
        response = self.client.get(url, {"timestamp_after": "2025-10-28T09:00:00Z"})

        # Assert
        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        # Should return record2 and record3 (at or after 09:00)
        assert len(response_data) == 2

    def test_filter_by_timestamp_before(self, devices, records):
        """Test filtering attendance records by timestamp_before."""
        # Act
        url = reverse("hrm:attendance-record-list")
        response = self.client.get(url, {"timestamp_before": "2025-10-28T09:00:00Z"})

        # Assert
        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        # Should return record1 and record3 (at or before 09:00)
        assert len(response_data) == 2

    def test_filter_by_date(self, devices, records):
        """Test filtering attendance records by specific date."""
        device1, _ = devices

        # Arrange - Create record on different date
        AttendanceRecord.objects.create(
            biometric_device=device1,
            attendance_code="531",
            timestamp=datetime(2025, 10, 27, 10, 0, 0, tzinfo=timezone.utc),
        )

        # Act
        url = reverse("hrm:attendance-record-list")
        response = self.client.get(url, {"date": "2025-10-28"})

        # Assert
        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 3  # Only records from Oct 28

    def test_combined_filters(self, devices, records):
        """Test combining multiple filters."""
        device1, _ = devices

        # Act - Filter by biometric device and attendance code
        url = reverse("hrm:attendance-record-list")
        response = self.client.get(url, {"biometric_device": device1.id, "attendance_code": "531"})

        # Assert
        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 2
        for record in response_data:
            assert record["biometric_device"]["id"] == device1.id
            assert "531" in record["attendance_code"]

    def test_search_by_attendance_code(self, devices, records):
        """Test searching attendance records by attendance code."""
        # Act
        url = reverse("hrm:attendance-record-list")
        response = self.client.get(url, {"search": "100"})

        # Assert
        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["attendance_code"] == "100"

    def test_ordering_by_timestamp_ascending(self, devices, records):
        """Test ordering attendance records by timestamp ascending."""
        record1, record2, record3 = records

        # Act
        url = reverse("hrm:attendance-record-list")
        response = self.client.get(url, {"ordering": "timestamp"})

        # Assert
        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 3
        # Check order - earliest first
        assert response_data[0]["id"] == record1.id
        assert response_data[1]["id"] == record3.id
        assert response_data[2]["id"] == record2.id

    def test_ordering_by_timestamp_descending(self, devices, records):
        """Test ordering attendance records by timestamp descending."""
        record1, record2, record3 = records

        # Act
        url = reverse("hrm:attendance-record-list")
        response = self.client.get(url, {"ordering": "-timestamp"})

        # Assert
        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 3
        # Check order - latest first (default)
        assert response_data[0]["id"] == record2.id
        assert response_data[1]["id"] == record3.id
        assert response_data[2]["id"] == record1.id

    def test_nested_device_information(self, devices, records):
        """Test that biometric device information is properly nested in response."""
        record1, _, _ = records
        device1, _ = devices

        # Act
        url = reverse("hrm:attendance-record-detail", kwargs={"pk": record1.id})
        response = self.client.get(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert "biometric_device" in response_data
        assert isinstance(response_data["biometric_device"], dict)
        assert response_data["biometric_device"]["id"] == device1.id
        assert response_data["biometric_device"]["name"] == "Main Entrance Device"

    def test_raw_data_preserved(self, devices, records):
        """Test that raw_data from device is preserved in response."""
        record1, _, _ = records

        # Act
        url = reverse("hrm:attendance-record-detail", kwargs={"pk": record1.id})
        response = self.client.get(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert "raw_data" in response_data
        assert response_data["raw_data"]["uid"] == 3525
        assert response_data["raw_data"]["user_id"] == "531"
        assert response_data["raw_data"]["status"] == 1
        assert response_data["raw_data"]["punch"] == 0

    def test_pagination(self, devices, records):
        """Test that attendance records are properly paginated."""
        device1, _ = devices

        # Arrange - Create many records to test pagination
        for i in range(15):
            AttendanceRecord.objects.create(
                biometric_device=device1,
                attendance_code=f"{i:03d}",
                timestamp=datetime(2025, 10, 28, 10, i, 0, tzinfo=timezone.utc),
            )

        # Act
        url = reverse("hrm:attendance-record-list")
        response = self.client.get(url, {"page_size": 10})

        # Assert
        assert response.status_code == status.HTTP_200_OK
        content = response.json()
        assert "data" in content
        assert "count" in content["data"]
        assert content["data"]["count"] == 18  # 3 original + 15 new
        assert "results" in content["data"]
        assert len(content["data"]["results"]) <= 10
