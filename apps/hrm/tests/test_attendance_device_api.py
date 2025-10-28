import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.hrm.models import AttendanceDevice

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


class AttendanceDeviceAPITest(TransactionTestCase, APITestMixin):
    """Test cases for AttendanceDevice API endpoints."""

    def setUp(self):
        """Set up test data."""
        # Clear all existing data for clean tests
        AttendanceDevice.objects.all().delete()
        User.objects.all().delete()

        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.device_data = {
            "name": "Main Entrance Device",
            "location": "Building A - Main Entrance",
            "ip_address": "192.168.1.100",
            "port": 4370,
            "password": "admin123",
            "is_enabled": True,
        }

    @patch("apps.hrm.api.serializers.attendance_device.AttendanceDeviceService")
    def test_create_attendance_device_success(self, mock_service):
        """Test creating an attendance device with successful connection."""
        # Arrange - Mock successful connection
        mock_service_instance = MagicMock()
        mock_service_instance.test_connection.return_value = (True, "Connection successful")
        mock_service_instance._zk_connection = MagicMock()
        mock_service_instance._zk_connection.get_serialnumber.return_value = "SN123456789"
        mock_service_instance._zk_connection.get_device_name.return_value = "REG001"
        mock_service_instance.__enter__ = MagicMock(return_value=mock_service_instance)
        mock_service_instance.__exit__ = MagicMock(return_value=False)
        mock_service.return_value = mock_service_instance

        # Act
        url = reverse("hrm:attendance-device-list")
        response = self.client.post(url, self.device_data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(AttendanceDevice.objects.count(), 1)

        device = AttendanceDevice.objects.first()
        self.assertEqual(device.name, self.device_data["name"])
        self.assertEqual(device.location, self.device_data["location"])
        self.assertEqual(device.ip_address, self.device_data["ip_address"])
        self.assertEqual(device.port, 4370)
        self.assertEqual(device.serial_number, "SN123456789")
        self.assertEqual(device.registration_number, "REG001")
        self.assertTrue(device.is_connected)
        self.assertTrue(device.is_enabled)

    @patch("apps.hrm.api.serializers.attendance_device.AttendanceDeviceService")
    def test_create_attendance_device_connection_failure(self, mock_service):
        """Test creating an attendance device with connection failure."""
        # Arrange - Mock failed connection
        mock_service_instance = MagicMock()
        mock_service_instance.test_connection.return_value = (False, "Network connection error: Connection timeout")
        mock_service.return_value = mock_service_instance

        # Act
        url = reverse("hrm:attendance-device-list")
        response = self.client.post(url, self.device_data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(AttendanceDevice.objects.count(), 0)

        # Check generic error message is returned (not the detailed one)
        content = json.loads(response.content.decode())
        self.assertIn("error", content)
        # The error message should be generic, not exposing stack traces
        error_data = content.get("error", {})
        if "ip_address" in error_data:
            self.assertIn("Unable to connect", str(error_data["ip_address"]))

    @patch("apps.hrm.api.serializers.attendance_device.AttendanceDeviceService")
    def test_list_attendance_devices(self, mock_service):
        """Test listing attendance devices."""
        # Arrange - Create devices directly in DB (bypass validation)
        device1 = AttendanceDevice.objects.create(
            name="Device 1", ip_address="192.168.1.100", serial_number="SN001", is_connected=True
        )
        device2 = AttendanceDevice.objects.create(
            name="Device 2", ip_address="192.168.1.101", serial_number="SN002", is_connected=False
        )

        # Act
        url = reverse("hrm:attendance-device-list")
        response = self.client.get(url)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 2)

    @patch("apps.hrm.api.serializers.attendance_device.AttendanceDeviceService")
    def test_retrieve_attendance_device(self, mock_service):
        """Test retrieving a specific attendance device."""
        # Arrange
        device = AttendanceDevice.objects.create(
            name="Test Device",
            location="Test Location",
            ip_address="192.168.1.100",
            port=4370,
            serial_number="SN123",
            registration_number="REG123",
            is_connected=True,
        )

        # Act
        url = reverse("hrm:attendance-device-detail", kwargs={"pk": device.id})
        response = self.client.get(url)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["name"], "Test Device")
        self.assertEqual(response_data["location"], "Test Location")
        self.assertEqual(response_data["serial_number"], "SN123")
        self.assertEqual(response_data["registration_number"], "REG123")
        self.assertTrue(response_data["is_connected"])

    @patch("apps.hrm.api.serializers.attendance_device.AttendanceDeviceService")
    def test_update_attendance_device(self, mock_service):
        """Test updating an attendance device."""
        # Arrange - Create initial device
        device = AttendanceDevice.objects.create(
            name="Original Name", ip_address="192.168.1.100", is_connected=False
        )

        # Mock successful connection for update
        mock_service_instance = MagicMock()
        mock_service_instance.test_connection.return_value = (True, "Connection successful")
        mock_service_instance._zk_connection = MagicMock()
        mock_service_instance._zk_connection.get_serialnumber.return_value = "SN999"
        mock_service_instance._zk_connection.get_device_name.return_value = "REG999"
        mock_service_instance.__enter__ = MagicMock(return_value=mock_service_instance)
        mock_service_instance.__exit__ = MagicMock(return_value=False)
        mock_service.return_value = mock_service_instance

        update_data = {
            "name": "Updated Name",
            "location": "New Location",
            "ip_address": "192.168.1.200",
            "port": 4370,
            "password": "newpass",
            "is_enabled": False,
        }

        # Act
        url = reverse("hrm:attendance-device-detail", kwargs={"pk": device.id})
        response = self.client.put(url, update_data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        device.refresh_from_db()
        self.assertEqual(device.name, "Updated Name")
        self.assertEqual(device.location, "New Location")
        self.assertEqual(device.ip_address, "192.168.1.200")
        self.assertEqual(device.serial_number, "SN999")
        self.assertEqual(device.registration_number, "REG999")
        self.assertTrue(device.is_connected)
        self.assertFalse(device.is_enabled)

    @patch("apps.hrm.api.serializers.attendance_device.AttendanceDeviceService")
    def test_partial_update_attendance_device(self, mock_service):
        """Test partially updating an attendance device."""
        # Arrange - Create initial device
        device = AttendanceDevice.objects.create(
            name="Original Name",
            location="Original Location",
            ip_address="192.168.1.100",
            is_connected=False,
            is_enabled=True,
        )

        # Mock successful connection for update (even though we're only changing name)
        mock_service_instance = MagicMock()
        mock_service_instance.test_connection.return_value = (True, "Connection successful")
        mock_service_instance._zk_connection = MagicMock()
        mock_service_instance._zk_connection.get_serialnumber.return_value = "SN888"
        mock_service_instance._zk_connection.get_device_name.return_value = "REG888"
        mock_service_instance.__enter__ = MagicMock(return_value=mock_service_instance)
        mock_service_instance.__exit__ = MagicMock(return_value=False)
        mock_service.return_value = mock_service_instance

        # Act - Only update name and is_enabled
        url = reverse("hrm:attendance-device-detail", kwargs={"pk": device.id})
        response = self.client.patch(url, {"name": "Partially Updated", "is_enabled": False}, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        device.refresh_from_db()
        self.assertEqual(device.name, "Partially Updated")
        self.assertEqual(device.location, "Original Location")  # Unchanged
        self.assertEqual(device.ip_address, "192.168.1.100")  # Unchanged
        self.assertFalse(device.is_enabled)

    @patch("apps.hrm.api.serializers.attendance_device.AttendanceDeviceService")
    def test_delete_attendance_device(self, mock_service):
        """Test deleting an attendance device."""
        # Arrange
        device = AttendanceDevice.objects.create(name="Device to Delete", ip_address="192.168.1.100")
        device_id = device.id

        # Act
        url = reverse("hrm:attendance-device-detail", kwargs={"pk": device_id})
        response = self.client.delete(url)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(AttendanceDevice.objects.filter(id=device_id).exists())

    @patch("apps.hrm.api.serializers.attendance_device.AttendanceDeviceService")
    def test_filter_by_is_enabled(self, mock_service):
        """Test filtering devices by is_enabled status."""
        # Arrange
        AttendanceDevice.objects.create(name="Enabled Device", ip_address="192.168.1.100", is_enabled=True)
        AttendanceDevice.objects.create(name="Disabled Device", ip_address="192.168.1.101", is_enabled=False)

        # Act
        url = reverse("hrm:attendance-device-list")
        response = self.client.get(url, {"is_enabled": "true"})

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["name"], "Enabled Device")

    @patch("apps.hrm.api.serializers.attendance_device.AttendanceDeviceService")
    def test_filter_by_is_connected(self, mock_service):
        """Test filtering devices by is_connected status."""
        # Arrange
        AttendanceDevice.objects.create(
            name="Connected Device", ip_address="192.168.1.100", is_connected=True, is_enabled=True
        )
        AttendanceDevice.objects.create(
            name="Disconnected Device", ip_address="192.168.1.101", is_connected=False, is_enabled=True
        )

        # Act
        url = reverse("hrm:attendance-device-list")
        response = self.client.get(url, {"is_connected": "true"})

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["name"], "Connected Device")

    @patch("apps.hrm.api.serializers.attendance_device.AttendanceDeviceService")
    def test_search_devices(self, mock_service):
        """Test searching devices by name, location, or IP address."""
        # Arrange
        AttendanceDevice.objects.create(
            name="Main Entrance", location="Building A", ip_address="192.168.1.100", is_enabled=True
        )
        AttendanceDevice.objects.create(
            name="Back Door", location="Building B", ip_address="192.168.1.101", is_enabled=True
        )

        # Act - Search by name
        url = reverse("hrm:attendance-device-list")
        response = self.client.get(url, {"search": "Main"})

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["name"], "Main Entrance")

    @patch("apps.hrm.api.serializers.attendance_device.AttendanceDeviceService")
    def test_ordering_by_name(self, mock_service):
        """Test ordering devices by name."""
        # Arrange
        AttendanceDevice.objects.create(name="Z Device", ip_address="192.168.1.100")
        AttendanceDevice.objects.create(name="A Device", ip_address="192.168.1.101")
        AttendanceDevice.objects.create(name="M Device", ip_address="192.168.1.102")

        # Act
        url = reverse("hrm:attendance-device-list")
        response = self.client.get(url, {"ordering": "name"})

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 3)
        self.assertEqual(response_data[0]["name"], "A Device")
        self.assertEqual(response_data[1]["name"], "M Device")
        self.assertEqual(response_data[2]["name"], "Z Device")

    @patch("apps.hrm.api.serializers.attendance_device.AttendanceDeviceService")
    def test_password_not_returned_in_response(self, mock_service):
        """Test that password is write-only and not returned in responses."""
        # Arrange
        device = AttendanceDevice.objects.create(
            name="Secure Device", ip_address="192.168.1.100", password="secret123"
        )

        # Act
        url = reverse("hrm:attendance-device-detail", kwargs={"pk": device.id})
        response = self.client.get(url)

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertNotIn("password", response_data)
