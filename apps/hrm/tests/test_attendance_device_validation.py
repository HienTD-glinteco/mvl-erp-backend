
import json
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import reverse
from unittest.mock import MagicMock
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import AdministrativeUnit, Province
from apps.core.models.device import UserDevice
from apps.hrm.models import AttendanceWifiDevice, Employee

User = get_user_model()

class APITestMixin:
    """Mixin to handle wrapped API responses and data extraction."""

    def get_response_data(self, response):
        """Extract data from wrapped API response."""
        content = json.loads(response.content.decode())
        if "data" in content:
            return content["data"]
        return content

class AttendanceDeviceValidationAPITest(TransactionTestCase, APITestMixin):
    """Test cases for attendance device validation logic."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_superuser(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # We need an employee for the view to proceed to validation
        self.province = Province.objects.create(code="01", name="Test Province")
        self.admin_unit = AdministrativeUnit.objects.create(
            code="01",
            name="Test Admin Unit",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )
        self.branch = Employee._meta.get_field("branch").related_model.objects.create(
            code="CN001",
            name="Test Branch",
            province=self.province,
            administrative_unit=self.admin_unit,
        )
        self.block = Employee._meta.get_field("block").related_model.objects.create(
            code="KH001",
            name="Test Block",
            branch=self.branch,
            block_type=Employee._meta.get_field("block").related_model.BlockType.BUSINESS,
        )
        self.department = Employee._meta.get_field("department").related_model.objects.create(
            code="PB001",
            name="Test Department",
            branch=self.branch,
            block=self.block,
        )
        self.employee = Employee.objects.create(
            user=self.user,
            fullname="Test Employee",
            username="testemployee",
            phone="0123456789",
            start_date="2024-01-01",
            attendance_code="531",
            email="employee@example.com",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="123456789",
        )

        self.wifi_device = AttendanceWifiDevice.objects.create(
            name="Office WiFi",
            code="WIFI001",
            bssid="00:11:22:33:44:55",
            state=AttendanceWifiDevice.State.IN_USE,
        )

    def test_validation_no_device_id_in_token(self):
        """Test validation fails when token has no device_id."""
        # Mock token without device_id
        token_mock = MagicMock()
        token_mock.get.side_effect = lambda k: None
        self.client.force_authenticate(user=self.user, token=token_mock)

        url = reverse("hrm:attendance-record-wifi-attendance")
        data = {"bssid": "00:11:22:33:44:55"}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Check error message
        # Since ValidationError returns list of strings in detail usually
        self.assertIn("Token does not contain device_id", str(response.content))

    def test_validation_user_device_not_found(self):
        """Test validation fails when UserDevice not found for device_id."""
        # Mock token with valid device_id
        token_mock = MagicMock()
        token_mock.get.side_effect = lambda k: "device123" if k == "device_id" else None
        self.client.force_authenticate(user=self.user, token=token_mock)

        # Do not create UserDevice

        url = reverse("hrm:attendance-record-wifi-attendance")
        data = {"bssid": "00:11:22:33:44:55"}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("User device not found", str(response.content))

    def test_validation_inactive_user_device(self):
        """Test validation fails when UserDevice is inactive."""
        # Create inactive user device
        UserDevice.objects.create(
            user=self.user,
            device_id="device123",
            platform=UserDevice.Platform.ANDROID,
            active=False
        )

        # Mock token with valid device_id
        token_mock = MagicMock()
        token_mock.get.side_effect = lambda k: "device123" if k == "device_id" else None
        self.client.force_authenticate(user=self.user, token=token_mock)

        url = reverse("hrm:attendance-record-wifi-attendance")
        data = {"bssid": "00:11:22:33:44:55"}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("User device not found", str(response.content))

    def test_validation_invalid_platform(self):
        """Test validation fails when platform is not mobile."""
        # Create user device with WEB platform
        UserDevice.objects.create(
            user=self.user,
            device_id="device123",
            platform=UserDevice.Platform.WEB,
            active=True
        )

        # Mock token with valid device_id
        token_mock = MagicMock()
        token_mock.get.side_effect = lambda k: "device123" if k == "device_id" else None
        self.client.force_authenticate(user=self.user, token=token_mock)

        url = reverse("hrm:attendance-record-wifi-attendance")
        data = {"bssid": "00:11:22:33:44:55"}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Attendance is only allowed from mobile devices", str(response.content))
