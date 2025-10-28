import json
from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.hrm.models import AttendanceDevice, AttendanceRecord

User = get_user_model()


class APITestMixin:
    """Mixin to handle wrapped API responses and data extraction."""

    def get_response_data(self, response):
        """Extract data from wrapped API response."""
        content = json.loads(response.content.decode())
        if "data" in content:
            data = content["data"]
            # Handle paginated responses - extract results list
            if isinstance(data, dict) and "results" in data:
                return data["results"]
            return data
        return content


class AttendanceRecordAPITest(TransactionTestCase, APITestMixin):
    """Test cases for AttendanceRecord API endpoints."""

    def setUp(self):
        """Set up test data."""
        # Clear all existing data for clean tests
        AttendanceRecord.objects.all().delete()
        AttendanceDevice.objects.all().delete()
        User.objects.all().delete()

        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create test devices
        self.device1 = AttendanceDevice.objects.create(
            name="Main Entrance Device", location="Building A", ip_address="192.168.1.100"
        )
        self.device2 = AttendanceDevice.objects.create(
            name="Back Door Device", location="Building B", ip_address="192.168.1.101"
        )

        # Create test records
        self.record1 = AttendanceRecord.objects.create(
            device=self.device1,
            attendance_code="531",
            timestamp=datetime(2025, 10, 28, 8, 30, 15, tzinfo=timezone.utc),
            raw_data={"uid": 3525, "user_id": "531", "timestamp": "2025-10-28T08:30:15", "status": 1, "punch": 0},
        )
        self.record2 = AttendanceRecord.objects.create(
            device=self.device1,
            attendance_code="531",
            timestamp=datetime(2025, 10, 28, 11, 49, 38, tzinfo=timezone.utc),
            raw_data={"uid": 3525, "user_id": "531", "timestamp": "2025-10-28T11:49:38", "status": 1, "punch": 0},
        )
        self.record3 = AttendanceRecord.objects.create(
            device=self.device2,
            attendance_code="100",
            timestamp=datetime(2025, 10, 28, 9, 0, 0, tzinfo=timezone.utc),
            raw_data={"uid": 1000, "user_id": "100", "timestamp": "2025-10-28T09:00:00", "status": 1, "punch": 0},
        )

    def test_list_attendance_records(self):
        """Test listing attendance records."""
        # Act
        url = reverse("hrm:attendance-record-list")
        response = self.client.get(url)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 3)

        # Check ordering (should be by timestamp descending)
        self.assertEqual(response_data[0]["id"], self.record2.id)  # Latest first
        self.assertEqual(response_data[1]["id"], self.record3.id)
        self.assertEqual(response_data[2]["id"], self.record1.id)  # Earliest last

    def test_retrieve_attendance_record(self):
        """Test retrieving a specific attendance record."""
        # Act
        url = reverse("hrm:attendance-record-detail", kwargs={"pk": self.record1.id})
        response = self.client.get(url)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["attendance_code"], "531")
        self.assertEqual(response_data["device"]["name"], "Main Entrance Device")
        self.assertEqual(response_data["device"]["location"], "Building A")
        self.assertIn("raw_data", response_data)
        self.assertEqual(response_data["raw_data"]["user_id"], "531")

    def test_attendance_records_are_read_only(self):
        """Test that attendance records cannot be created via API."""
        # Arrange
        record_data = {
            "device": self.device1.id,
            "attendance_code": "999",
            "timestamp": "2025-10-28T12:00:00Z",
        }

        # Act - Try to create
        url = reverse("hrm:attendance-record-list")
        response = self.client.post(url, record_data, format="json")

        # Assert - Should not be allowed
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_attendance_records_cannot_be_updated(self):
        """Test that attendance records cannot be updated via API."""
        # Act - Try to update
        url = reverse("hrm:attendance-record-detail", kwargs={"pk": self.record1.id})
        response = self.client.put(url, {"attendance_code": "999"}, format="json")

        # Assert - Should not be allowed
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_attendance_records_cannot_be_deleted(self):
        """Test that attendance records cannot be deleted via API."""
        # Act
        url = reverse("hrm:attendance-record-detail", kwargs={"pk": self.record1.id})
        response = self.client.delete(url)

        # Assert - Should not be allowed
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        # Verify record still exists
        self.assertTrue(AttendanceRecord.objects.filter(id=self.record1.id).exists())

    def test_filter_by_device(self):
        """Test filtering attendance records by device."""
        # Act
        url = reverse("hrm:attendance-record-list")
        response = self.client.get(url, {"device": self.device1.id})

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 2)
        for record in response_data:
            self.assertEqual(record["device"]["id"], self.device1.id)

    def test_filter_by_attendance_code(self):
        """Test filtering attendance records by attendance code."""
        # Act
        url = reverse("hrm:attendance-record-list")
        response = self.client.get(url, {"attendance_code": "531"})

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 2)
        for record in response_data:
            self.assertIn("531", record["attendance_code"])

    def test_filter_by_timestamp_after(self):
        """Test filtering attendance records by timestamp_after."""
        # Act
        url = reverse("hrm:attendance-record-list")
        response = self.client.get(url, {"timestamp_after": "2025-10-28T09:00:00Z"})

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        # Should return record2 and record3 (at or after 09:00)
        self.assertEqual(len(response_data), 2)

    def test_filter_by_timestamp_before(self):
        """Test filtering attendance records by timestamp_before."""
        # Act
        url = reverse("hrm:attendance-record-list")
        response = self.client.get(url, {"timestamp_before": "2025-10-28T09:00:00Z"})

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        # Should return record1 and record3 (at or before 09:00)
        self.assertEqual(len(response_data), 2)

    def test_filter_by_date(self):
        """Test filtering attendance records by specific date."""
        # Arrange - Create record on different date
        AttendanceRecord.objects.create(
            device=self.device1,
            attendance_code="531",
            timestamp=datetime(2025, 10, 27, 10, 0, 0, tzinfo=timezone.utc),
        )

        # Act
        url = reverse("hrm:attendance-record-list")
        response = self.client.get(url, {"date": "2025-10-28"})

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 3)  # Only records from Oct 28

    def test_combined_filters(self):
        """Test combining multiple filters."""
        # Act - Filter by device and attendance code
        url = reverse("hrm:attendance-record-list")
        response = self.client.get(url, {"device": self.device1.id, "attendance_code": "531"})

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 2)
        for record in response_data:
            self.assertEqual(record["device"]["id"], self.device1.id)
            self.assertIn("531", record["attendance_code"])

    def test_search_by_attendance_code(self):
        """Test searching attendance records by attendance code."""
        # Act
        url = reverse("hrm:attendance-record-list")
        response = self.client.get(url, {"search": "100"})

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["attendance_code"], "100")

    def test_ordering_by_timestamp_ascending(self):
        """Test ordering attendance records by timestamp ascending."""
        # Act
        url = reverse("hrm:attendance-record-list")
        response = self.client.get(url, {"ordering": "timestamp"})

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 3)
        # Check order - earliest first
        self.assertEqual(response_data[0]["id"], self.record1.id)
        self.assertEqual(response_data[1]["id"], self.record3.id)
        self.assertEqual(response_data[2]["id"], self.record2.id)

    def test_ordering_by_timestamp_descending(self):
        """Test ordering attendance records by timestamp descending."""
        # Act
        url = reverse("hrm:attendance-record-list")
        response = self.client.get(url, {"ordering": "-timestamp"})

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 3)
        # Check order - latest first (default)
        self.assertEqual(response_data[0]["id"], self.record2.id)
        self.assertEqual(response_data[1]["id"], self.record3.id)
        self.assertEqual(response_data[2]["id"], self.record1.id)

    def test_nested_device_information(self):
        """Test that device information is properly nested in response."""
        # Act
        url = reverse("hrm:attendance-record-detail", kwargs={"pk": self.record1.id})
        response = self.client.get(url)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertIn("device", response_data)
        self.assertIsInstance(response_data["device"], dict)
        self.assertEqual(response_data["device"]["id"], self.device1.id)
        self.assertEqual(response_data["device"]["name"], "Main Entrance Device")
        self.assertEqual(response_data["device"]["location"], "Building A")

    def test_raw_data_preserved(self):
        """Test that raw_data from device is preserved in response."""
        # Act
        url = reverse("hrm:attendance-record-detail", kwargs={"pk": self.record1.id})
        response = self.client.get(url)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertIn("raw_data", response_data)
        self.assertEqual(response_data["raw_data"]["uid"], 3525)
        self.assertEqual(response_data["raw_data"]["user_id"], "531")
        self.assertEqual(response_data["raw_data"]["status"], 1)
        self.assertEqual(response_data["raw_data"]["punch"], 0)

    def test_pagination(self):
        """Test that attendance records are properly paginated."""
        # Arrange - Create many records to test pagination
        for i in range(15):
            AttendanceRecord.objects.create(
                device=self.device1,
                attendance_code=f"{i:03d}",
                timestamp=datetime(2025, 10, 28, 12 + i, 0, 0, tzinfo=timezone.utc),
            )

        # Act
        url = reverse("hrm:attendance-record-list")
        response = self.client.get(url, {"page_size": 10})

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = json.loads(response.content.decode())
        self.assertIn("data", content)
        self.assertIn("count", content["data"])
        self.assertEqual(content["data"]["count"], 18)  # 3 original + 15 new
        self.assertIn("results", content["data"])
        self.assertLessEqual(len(content["data"]["results"]), 10)
