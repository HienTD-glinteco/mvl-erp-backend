from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse
from rest_framework import status

from apps.hrm.models import AttendanceDevice


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
class TestAttendanceDeviceAPI(APITestMixin):
    """Test cases for AttendanceDevice API endpoints."""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client):
        self.client = api_client

    @pytest.fixture
    def device_data(self):
        return {
            "name": "Main Entrance Device",
            "ip_address": "192.168.1.100",
            "port": 4370,
            "password": "admin123",
            "is_enabled": True,
        }

    @patch("apps.hrm.api.serializers.attendance_device.ZKDeviceService")
    def test_create_attendance_device_success(self, mock_service, device_data):
        """Test creating an attendance device with successful connection."""
        # Arrange - Mock successful connection
        mock_service_instance = MagicMock()
        mock_service_instance.test_connection.return_value = (True, "Connection successful")
        mock_service_instance._zk_connection = MagicMock()
        mock_service_instance.get_device_info.return_value = {
            "serial_number": "SN123456789",
            "registration_number": "REG001",
            "firmware_version": "6.60",
        }
        mock_service_instance.__enter__ = MagicMock(return_value=mock_service_instance)
        mock_service_instance.__exit__ = MagicMock(return_value=False)
        mock_service.return_value = mock_service_instance

        # Act
        url = reverse("hrm:attendance-device-list")
        response = self.client.post(url, device_data, format="json")

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        assert AttendanceDevice.objects.count() == 1

        device = AttendanceDevice.objects.first()
        assert device.name == device_data["name"]
        assert device.ip_address == device_data["ip_address"]
        assert device.port == 4370
        assert device.serial_number == "SN123456789"
        assert device.registration_number == ""
        assert device.is_connected is True
        assert device.is_enabled is True

        # Verify code is returned in response
        response_data = self.get_response_data(response)
        assert "code" in response_data
        assert response_data["code"] is not None

    @patch("apps.hrm.api.serializers.attendance_device.ZKDeviceService")
    def test_create_attendance_device_connection_failure(self, mock_service, device_data):
        """Test creating an attendance device with connection failure."""
        # Arrange - Mock failed connection
        mock_service_instance = MagicMock()
        mock_service_instance.test_connection.return_value = (False, "Network connection error: Connection timeout")
        mock_service_instance.get_device_info.return_value = {
            "serial_number": "",
            "registration_number": "",
            "firmware_version": "",
        }
        mock_service_instance.__enter__ = MagicMock(
            side_effect=Exception("Network connection error: Connection timeout")
        )
        mock_service.return_value = mock_service_instance

        # Act
        url = reverse("hrm:attendance-device-list")
        response = self.client.post(url, device_data, format="json")

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        assert AttendanceDevice.objects.count() == 1

        device = AttendanceDevice.objects.first()
        assert device.name == device_data["name"]
        assert device.ip_address == device_data["ip_address"]
        assert device.port == 4370
        assert device.serial_number == ""
        assert device.registration_number == ""
        assert device.is_connected is False
        assert device.is_enabled is True

    @patch("apps.hrm.api.serializers.attendance_device.ZKDeviceService")
    def test_list_attendance_devices(self, mock_service, device_data):
        """Test listing attendance devices."""
        # Arrange - Create devices directly in DB (bypass validation)
        AttendanceDevice.objects.create(
            name="Device 1", ip_address="192.168.1.100", port=4370, serial_number="SN001", is_connected=True
        )
        AttendanceDevice.objects.create(
            name="Device 2", ip_address="192.168.1.101", port=4370, serial_number="SN002", is_connected=False
        )

        # Act
        url = reverse("hrm:attendance-device-list")
        response = self.client.get(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 2

    def test_filter_attendance_devices_by_invalid_block_returns_empty(self, device_data):
        """Filtering by a non-existent block should return an empty list."""
        AttendanceDevice.objects.create(
            name="Unassigned Device",
            ip_address="192.168.1.150",
            port=4370,
            serial_number="SN999",
        )

        url = reverse("hrm:attendance-device-list")
        response = self.client.get(url, {"block": 999999})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 0

    @patch("apps.hrm.api.serializers.attendance_device.ZKDeviceService")
    def test_retrieve_attendance_device(self, mock_service, device_data):
        """Test retrieving a specific attendance device."""
        # Arrange
        device = AttendanceDevice.objects.create(
            name="Test Device",
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
        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert response_data["name"] == "Test Device"
        assert response_data["serial_number"] == "SN123"
        assert response_data["registration_number"] == "REG123"
        assert response_data["is_connected"] is True

    @patch("apps.hrm.api.serializers.attendance_device.ZKDeviceService")
    def test_update_attendance_device(self, mock_service, device_data):
        """Test updating an attendance device."""
        # Arrange - Create initial device
        device = AttendanceDevice.objects.create(
            name="Original Name", ip_address="192.168.1.100", port=4370, is_connected=False
        )

        # Mock successful connection for update
        mock_service_instance = MagicMock()
        mock_service_instance.test_connection.return_value = (True, "Connection successful")
        mock_service_instance._zk_connection = MagicMock()
        mock_service_instance.get_device_info.return_value = {
            "serial_number": "SN999",
            "registration_number": "REG999",
            "firmware_version": "6.60",
        }
        mock_service_instance.__enter__ = MagicMock(return_value=mock_service_instance)
        mock_service_instance.__exit__ = MagicMock(return_value=False)
        mock_service.return_value = mock_service_instance

        update_data = {
            "name": "Updated Name",
            "ip_address": "192.168.1.200",
            "port": 4370,
            "password": "newpass",
            "is_enabled": False,
        }

        # Act
        url = reverse("hrm:attendance-device-detail", kwargs={"pk": device.id})
        response = self.client.put(url, update_data, format="json")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        device.refresh_from_db()
        assert device.name == "Updated Name"
        assert device.ip_address == "192.168.1.200"
        assert device.serial_number == ""
        assert device.registration_number == ""
        assert device.is_connected is False
        assert device.is_enabled is False

    @patch("apps.hrm.api.serializers.attendance_device.ZKDeviceService")
    def test_partial_update_attendance_device(self, mock_service, device_data):
        """Test partially updating an attendance device."""
        # Arrange - Create initial device
        device = AttendanceDevice.objects.create(
            name="Original Name",
            ip_address="192.168.1.100",
            port=4370,
            is_connected=False,
            is_enabled=True,
        )

        # Mock successful connection for update
        mock_service_instance = MagicMock()
        mock_service_instance.test_connection.return_value = (True, "Connection successful")
        mock_service_instance._zk_connection = MagicMock()
        mock_service_instance.get_device_info.return_value = {
            "serial_number": "SN888",
            "registration_number": "REG888",
            "firmware_version": "6.60",
        }
        mock_service_instance.__enter__ = MagicMock(return_value=mock_service_instance)
        mock_service_instance.__exit__ = MagicMock(return_value=False)
        mock_service.return_value = mock_service_instance

        # Act - Only update name and is_enabled
        url = reverse("hrm:attendance-device-detail", kwargs={"pk": device.id})
        response = self.client.patch(url, {"name": "Partially Updated", "is_enabled": False}, format="json")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        device.refresh_from_db()
        assert device.name == "Partially Updated"
        assert device.ip_address == "192.168.1.100"  # Unchanged
        assert device.is_enabled is False

    @patch("apps.hrm.api.serializers.attendance_device.ZKDeviceService")
    def test_delete_attendance_device(self, mock_service, device_data):
        """Test deleting an attendance device."""
        # Arrange
        device = AttendanceDevice.objects.create(name="Device to Delete", ip_address="192.168.1.100", port=4370)
        device_id = device.id

        # Act
        url = reverse("hrm:attendance-device-detail", kwargs={"pk": device_id})
        response = self.client.delete(url)

        # Assert
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not AttendanceDevice.objects.filter(id=device_id).exists()

    @patch("apps.hrm.api.serializers.attendance_device.ZKDeviceService")
    def test_filter_by_is_enabled(self, mock_service, device_data):
        """Test filtering devices by is_enabled status."""
        # Arrange
        AttendanceDevice.objects.create(name="Enabled Device", ip_address="192.168.1.100", port=4370, is_enabled=True)
        AttendanceDevice.objects.create(
            name="Disabled Device", ip_address="192.168.1.101", port=4370, is_enabled=False
        )

        # Act
        url = reverse("hrm:attendance-device-list")
        response = self.client.get(url, {"is_enabled": "true"})

        # Assert
        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["name"] == "Enabled Device"

    @patch("apps.hrm.api.serializers.attendance_device.ZKDeviceService")
    def test_filter_by_is_connected(self, mock_service, device_data):
        """Test filtering devices by is_connected status."""
        # Arrange
        AttendanceDevice.objects.create(
            name="Connected Device", ip_address="192.168.1.100", port=4370, is_connected=True, is_enabled=True
        )
        AttendanceDevice.objects.create(
            name="Disconnected Device", ip_address="192.168.1.101", port=4370, is_connected=False, is_enabled=True
        )

        # Act
        url = reverse("hrm:attendance-device-list")
        response = self.client.get(url, {"is_connected": "true"})

        # Assert
        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["name"] == "Connected Device"

    @patch("apps.hrm.api.serializers.attendance_device.ZKDeviceService")
    def test_search_devices(self, mock_service, device_data):
        """Test searching devices by name or IP address."""
        # Arrange
        AttendanceDevice.objects.create(name="Main Entrance", ip_address="192.168.1.100", port=4370, is_enabled=True)
        AttendanceDevice.objects.create(name="Back Door", ip_address="192.168.1.101", port=4370, is_enabled=True)

        # Act - Search by name
        url = reverse("hrm:attendance-device-list")
        response = self.client.get(url, {"search": "Main"})

        # Assert
        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 1
        assert response_data[0]["name"] == "Main Entrance"

    @patch("apps.hrm.api.serializers.attendance_device.ZKDeviceService")
    def test_ordering_by_name(self, mock_service, device_data):
        """Test ordering devices by name."""
        # Arrange
        AttendanceDevice.objects.create(name="Z Device", ip_address="192.168.1.100", port=4370)
        AttendanceDevice.objects.create(name="A Device", ip_address="192.168.1.101", port=4370)
        AttendanceDevice.objects.create(name="M Device", ip_address="192.168.1.102", port=4370)

        # Act
        url = reverse("hrm:attendance-device-list")
        response = self.client.get(url, {"ordering": "name"})

        # Assert
        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 3
        assert response_data[0]["name"] == "A Device"
        assert response_data[1]["name"] == "M Device"
        assert response_data[2]["name"] == "Z Device"

    @patch("apps.hrm.models.attendance_device.ZKDeviceService")
    def test_toggle_enabled_enable_device_success(self, mock_service, device_data):
        """Test toggling device from disabled to enabled with successful connection."""
        # Arrange - Create disabled device
        device = AttendanceDevice.objects.create(
            name="Test Device", ip_address="192.168.1.100", port=4370, is_enabled=False, is_connected=False
        )

        # Mock successful connection
        mock_service_instance = MagicMock()
        mock_service_instance.test_connection.return_value = (True, "Connection successful")
        mock_service_instance._zk_connection = MagicMock()
        mock_service_instance.get_device_info.return_value = {
            "serial_number": "SN123",
            "registration_number": "REG123",
            "firmware_version": "6.60",
        }
        mock_service_instance.__enter__ = MagicMock(return_value=mock_service_instance)
        mock_service_instance.__exit__ = MagicMock(return_value=False)
        mock_service.return_value = mock_service_instance

        # Act
        url = reverse("hrm:attendance-device-toggle-enabled", kwargs={"pk": device.id})
        response = self.client.post(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        device.refresh_from_db()
        assert device.is_enabled is True
        assert device.is_connected is True
        assert device.serial_number == "SN123"
        assert device.registration_number == ""

    @patch("apps.hrm.models.attendance_device.ZKDeviceService")
    def test_toggle_enabled_enable_device_connection_failure(self, mock_service, device_data):
        """Test toggling device from disabled to enabled with connection failure."""
        # Arrange - Create disabled device
        device = AttendanceDevice.objects.create(
            name="Test Device", ip_address="192.168.1.100", port=4370, is_enabled=False, is_connected=False
        )

        # Mock failed connection
        mock_service_instance = MagicMock()
        mock_service_instance.test_connection.return_value = (False, "Connection timeout")
        mock_service_instance.get_device_info.return_value = {
            "serial_number": "",
            "registration_number": "",
            "firmware_version": "",
        }
        mock_service_instance.__enter__ = MagicMock(side_effect=Exception("Connection timeout"))
        mock_service.return_value = mock_service_instance

        # Act
        url = reverse("hrm:attendance-device-toggle-enabled", kwargs={"pk": device.id})
        response = self.client.post(url)

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        device.refresh_from_db()
        assert device.is_enabled is False
        assert device.is_connected is False

    @patch("apps.hrm.models.attendance_device.ZKDeviceService")
    def test_toggle_enabled_disable_device(self, mock_service, device_data):
        """Test toggling device from enabled to disabled."""
        # Arrange - Create enabled device
        device = AttendanceDevice.objects.create(
            name="Test Device", ip_address="192.168.1.100", port=4370, is_enabled=True, is_connected=True
        )

        # Act
        url = reverse("hrm:attendance-device-toggle-enabled", kwargs={"pk": device.id})
        response = self.client.post(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        device.refresh_from_db()
        assert device.is_enabled is False
        assert device.is_connected is False

    @patch("apps.hrm.models.attendance_device.ZKDeviceService")
    def test_check_connection_success(self, mock_service, device_data):
        """Test checking connection with successful result."""
        # Arrange
        device = AttendanceDevice.objects.create(
            name="Test Device", ip_address="192.168.1.100", port=4370, is_connected=False
        )

        # Mock successful connection
        mock_service_instance = MagicMock()
        mock_service_instance.test_connection.return_value = (True, "Connection successful. Firmware: 6.60")
        mock_service_instance._zk_connection = MagicMock()
        mock_service_instance.get_device_info.return_value = {
            "serial_number": "SN456",
            "registration_number": "REG456",
            "firmware_version": "6.60",
        }
        mock_service_instance.__enter__ = MagicMock(return_value=mock_service_instance)
        mock_service_instance.__exit__ = MagicMock(return_value=False)
        mock_service.return_value = mock_service_instance

        # Act
        url = reverse("hrm:attendance-device-check-connection", kwargs={"pk": device.id})
        response = self.client.post(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert response_data["message"] == "Connection successful. Firmware: 6.60"
        device.refresh_from_db()
        assert device.is_connected is True
        assert device.serial_number == "SN456"
        assert device.registration_number == ""

    @patch("apps.hrm.models.attendance_device.ZKDeviceService")
    def test_check_connection_failure(self, mock_service, device_data):
        """Test checking connection with failed result."""
        # Arrange
        device = AttendanceDevice.objects.create(
            name="Test Device", ip_address="192.168.1.100", port=4370, is_connected=True
        )

        # Mock failed connection
        mock_service_instance = MagicMock()
        mock_service_instance.test_connection.return_value = (False, "Network connection error: Connection timeout")
        mock_service_instance.get_device_info.return_value = {
            "serial_number": "",
            "registration_number": "",
            "firmware_version": "",
        }
        mock_service_instance.__enter__ = MagicMock(
            side_effect=Exception("Network connection error: Connection timeout")
        )
        mock_service.return_value = mock_service_instance

        # Act
        url = reverse("hrm:attendance-device-check-connection", kwargs={"pk": device.id})
        response = self.client.post(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert response_data["message"] == "Network connection error: Connection timeout"
        device.refresh_from_db()
        assert device.is_connected is False

    @patch("apps.hrm.api.serializers.attendance_device.ZKDeviceService")
    def test_create_device_with_note(self, mock_service, device_data):
        """Test creating a device with a note."""
        # Arrange - Mock successful connection
        mock_service_instance = MagicMock()
        mock_service_instance.test_connection.return_value = (True, "Connection successful")
        mock_service_instance._zk_connection = MagicMock()
        mock_service_instance.get_device_info.return_value = {
            "serial_number": "SN123",
            "registration_number": "REG123",
            "firmware_version": "6.60",
        }
        mock_service_instance.__enter__ = MagicMock(return_value=mock_service_instance)
        mock_service_instance.__exit__ = MagicMock(return_value=False)
        mock_service.return_value = mock_service_instance

        device_data_with_note = {
            "name": "Test Device",
            "ip_address": "192.168.1.100",
            "port": 4370,
            "password": "admin123",
            "is_enabled": True,
            "note": "This is a test device note",
        }

        # Act
        url = reverse("hrm:attendance-device-list")
        response = self.client.post(url, device_data_with_note, format="json")

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        device = AttendanceDevice.objects.first()
        assert device.note == "This is a test device note"

        # Verify note is returned in response
        response_data = self.get_response_data(response)
        assert "note" in response_data
        assert response_data["note"] == "This is a test device note"

    @patch("apps.hrm.api.serializers.attendance_device.ZKDeviceService")
    def test_create_device_without_note_defaults_to_empty(self, mock_service, device_data):
        """Test creating a device without a note defaults to empty string."""
        # Arrange - Mock successful connection
        mock_service_instance = MagicMock()
        mock_service_instance.test_connection.return_value = (True, "Connection successful")
        mock_service_instance._zk_connection = MagicMock()
        mock_service_instance.get_device_info.return_value = {
            "serial_number": "SN123",
            "registration_number": "REG123",
            "firmware_version": "6.60",
        }
        mock_service_instance.__enter__ = MagicMock(return_value=mock_service_instance)
        mock_service_instance.__exit__ = MagicMock(return_value=False)
        mock_service.return_value = mock_service_instance

        # Act
        url = reverse("hrm:attendance-device-list")
        response = self.client.post(url, device_data, format="json")

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        device = AttendanceDevice.objects.first()
        assert device.note == ""

    @patch("apps.hrm.api.serializers.attendance_device.ZKDeviceService")
    def test_update_device_note(self, mock_service, device_data):
        """Test updating a device's note."""
        # Arrange
        device = AttendanceDevice.objects.create(
            name="Test Device",
            ip_address="192.168.1.100",
            port=4370,
            note="Original note",
        )

        # Mock successful connection
        mock_service_instance = MagicMock()
        mock_service_instance.test_connection.return_value = (True, "Connection successful")
        mock_service_instance._zk_connection = MagicMock()
        mock_service_instance._zk_connection.get_serialnumber.return_value = "SN123"
        mock_service_instance._zk_connection.get_device_name.return_value = "REG123"
        mock_service_instance.__enter__ = MagicMock(return_value=mock_service_instance)
        mock_service_instance.__exit__ = MagicMock(return_value=False)
        mock_service.return_value = mock_service_instance

        # Act
        url = reverse("hrm:attendance-device-detail", kwargs={"pk": device.id})
        response = self.client.patch(url, {"note": "Updated note", "password": "admin123"}, format="json")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        device.refresh_from_db()
        assert device.note == "Updated note"

    @patch("apps.hrm.api.serializers.attendance_device.ZKDeviceService")
    def test_password_required_on_create(self, mock_service, device_data):
        """Test that password is required when creating a device."""
        # Arrange
        device_data_no_password = {
            "name": "Test Device",
            "ip_address": "192.168.1.100",
            "port": 4370,
            "is_enabled": True,
            # password is missing
        }

        # Act
        url = reverse("hrm:attendance-device-list")
        response = self.client.post(url, device_data_no_password, format="json")

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        response_content = response.json()
        assert "error" in response_content

    @patch("apps.hrm.api.serializers.attendance_device.ZKDeviceService")
    def test_code_field_returned_in_response(self, mock_service, device_data):
        """Test that code field is returned in API responses."""
        # Arrange
        device = AttendanceDevice.objects.create(
            name="Test Device",
            ip_address="192.168.1.100",
            port=4370,
        )

        # Act
        url = reverse("hrm:attendance-device-detail", kwargs={"pk": device.id})
        response = self.client.get(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert "code" in response_data
        assert response_data["code"] == device.code
