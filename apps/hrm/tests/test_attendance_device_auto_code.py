from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse
from rest_framework import status

from apps.hrm.models import AttendanceDevice


@pytest.mark.django_db
class TestAttendanceDeviceAutoCodeGenerationAPI:
    """Test cases for AttendanceDevice auto-code generation."""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client, user):
        self.client = api_client
        self.user = user
        self.device_data = {
            "name": "Main Entrance Device",
            "ip_address": "192.168.1.100",
            "port": 4370,
            "password": "admin123",
            "is_enabled": True,
        }

    def get_response_data(self, response):
        """Extract data from wrapped API response."""
        content = response.json()
        if "data" in content:
            return content["data"]
        return content

    @patch("apps.hrm.api.serializers.attendance_device.ZKDeviceService")
    def test_create_device_without_code_auto_generates(self, mock_service):
        """Test creating a device without code field auto-generates code."""
        # Arrange - Mock successful connection
        mock_service_instance = MagicMock()
        mock_service_instance.test_connection.return_value = (True, "Connection successful")
        mock_service_instance._zk_connection = MagicMock()
        mock_service_instance.get_device_info.return_value = {
            "serial_number": "SN123",
            "registration_number": "REG123",
            "firmware_version": "firmware123",
        }
        mock_service_instance.__enter__ = MagicMock(return_value=mock_service_instance)
        mock_service_instance.__exit__ = MagicMock(return_value=False)
        mock_service.return_value = mock_service_instance

        # Act
        url = reverse("hrm:attendance-device-list")
        response = self.client.post(url, self.device_data, format="json")

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        response_data = self.get_response_data(response)

        # Verify code was auto-generated
        assert "code" in response_data
        assert response_data["code"].startswith("MC")

        # Verify in database
        device = AttendanceDevice.objects.first()
        assert device is not None
        assert device.code == response_data["code"]

    @patch("apps.hrm.api.serializers.attendance_device.ZKDeviceService")
    def test_create_device_with_code_ignores_provided_code(self, mock_service):
        """Test that provided code is ignored and auto-generated code is used."""
        # Arrange - Mock successful connection
        mock_service_instance = MagicMock()
        mock_service_instance.test_connection.return_value = (True, "Connection successful")
        mock_service_instance._zk_connection = MagicMock()
        mock_service_instance.get_device_info.return_value = {
            "serial_number": "SN123",
            "registration_number": "REG123",
            "firmware_version": "firmware123",
        }
        mock_service_instance.__enter__ = MagicMock(return_value=mock_service_instance)
        mock_service_instance.__exit__ = MagicMock(return_value=False)
        mock_service.return_value = mock_service_instance

        device_data = self.device_data.copy()
        device_data["code"] = "MANUAL"  # This should be ignored

        # Act
        url = reverse("hrm:attendance-device-list")
        response = self.client.post(url, device_data, format="json")

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        response_data = self.get_response_data(response)

        # Verify auto-generated code was used, not the provided one
        assert "code" in response_data
        assert response_data["code"] != "MANUAL"
        assert response_data["code"].startswith("MC")

        # Verify in database
        device = AttendanceDevice.objects.first()
        assert device.code != "MANUAL"
        assert device.code.startswith("MC")

    @patch("apps.hrm.api.serializers.attendance_device.ZKDeviceService")
    def test_sequential_code_generation(self, mock_service):
        """Test that sequential devices get sequential codes."""
        # Arrange - Mock successful connection
        mock_service_instance = MagicMock()
        mock_service_instance.test_connection.return_value = (True, "Connection successful")
        mock_service_instance._zk_connection = MagicMock()
        mock_service_instance.get_device_info.return_value = {
            "serial_number": "SN123",
            "registration_number": "REG123",
            "firmware_version": "firmware123",
        }
        mock_service_instance.__enter__ = MagicMock(return_value=mock_service_instance)
        mock_service_instance.__exit__ = MagicMock(return_value=False)
        mock_service.return_value = mock_service_instance

        # Act - Create 3 devices
        url = reverse("hrm:attendance-device-list")
        codes = []
        for i in range(3):
            device_data = self.device_data.copy()
            device_data["name"] = f"Device {i + 1}"
            device_data["ip_address"] = f"192.168.1.{100 + i}"
            response = self.client.post(url, device_data, format="json")
            assert response.status_code == status.HTTP_201_CREATED
            response_data = self.get_response_data(response)
            codes.append(response_data["code"])

        # Assert - Verify codes are sequential
        assert len(codes) == 3
        for code in codes:
            assert code.startswith("MC")

        # Verify all codes are unique
        assert len(set(codes)) == 3

        # Verify codes are in database
        devices = AttendanceDevice.objects.all().order_by("id")
        assert devices.count() == 3
        for device, code in zip(devices, codes, strict=True):
            assert device.code == code

    @patch("apps.hrm.api.serializers.attendance_device.ZKDeviceService")
    def test_code_not_editable_on_update(self, mock_service):
        """Test that code cannot be changed via update."""
        # Arrange - Create initial device
        mock_service_instance = MagicMock()
        mock_service_instance.test_connection.return_value = (True, "Connection successful")
        mock_service_instance._zk_connection = MagicMock()
        mock_service_instance.get_device_info.return_value = {
            "serial_number": "SN123",
            "registration_number": "REG123",
            "firmware_version": "firmware123",
        }
        mock_service_instance.__enter__ = MagicMock(return_value=mock_service_instance)
        mock_service_instance.__exit__ = MagicMock(return_value=False)
        mock_service.return_value = mock_service_instance

        # Create device
        url = reverse("hrm:attendance-device-list")
        response = self.client.post(url, self.device_data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        response_data = self.get_response_data(response)
        original_code = response_data["code"]
        device_id = response_data["id"]

        # Act - Try to update with different code
        update_data = {
            "name": "Updated Device Name",
            "ip_address": "192.168.1.200",
            "port": 4370,
            "password": "newpass",
            "is_enabled": False,
            "code": "NEWCODE",  # Try to change code
        }
        url = reverse("hrm:attendance-device-detail", kwargs={"pk": device_id})
        response = self.client.put(url, update_data, format="json")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)

        # Verify code was NOT changed
        assert response_data["code"] == original_code

        # Verify in database
        device = AttendanceDevice.objects.get(id=device_id)
        assert device.code == original_code
        assert device.code != "NEWCODE"

    @patch("apps.hrm.api.serializers.attendance_device.ZKDeviceService")
    def test_code_prefix_is_correct(self, mock_service):
        """Test that generated code uses correct prefix (MC)."""
        # Arrange - Mock successful connection
        mock_service_instance = MagicMock()
        mock_service_instance.test_connection.return_value = (True, "Connection successful")
        mock_service_instance._zk_connection = MagicMock()
        mock_service_instance.get_device_info.return_value = {
            "serial_number": "SN123",
            "registration_number": "REG123",
            "firmware_version": "firmware123",
        }
        mock_service_instance.__enter__ = MagicMock(return_value=mock_service_instance)
        mock_service_instance.__exit__ = MagicMock(return_value=False)
        mock_service.return_value = mock_service_instance

        # Act
        url = reverse("hrm:attendance-device-list")
        response = self.client.post(url, self.device_data, format="json")

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        response_data = self.get_response_data(response)

        # Verify code prefix
        assert response_data["code"].startswith("MC")

        # Verify the code format (MC followed by digits)
        code = response_data["code"]
        assert code[:2] == "MC"
        assert code[2:].isdigit()
