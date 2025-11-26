"""Tests for GeoLocation and WiFi attendance recording endpoints."""

import json
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.files.models import FileModel
from apps.hrm.models import AttendanceGeolocation, AttendanceRecord, AttendanceWifiDevice, Employee, Project
from apps.realestate.models import Project as RealEstateProject

User = get_user_model()


class APITestMixin:
    """Mixin to handle wrapped API responses and data extraction."""

    def get_response_data(self, response):
        """Extract data from wrapped API response."""
        content = json.loads(response.content.decode())
        if "data" in content:
            return content["data"]
        return content


class GeoLocationAttendanceAPITest(TransactionTestCase, APITestMixin):
    """Test cases for GeoLocation-based attendance recording."""

    def setUp(self):
        """Set up test data."""
        # Create superuser
        self.user = User.objects.create_superuser(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create employee for the user
        self.employee = Employee.objects.create(
            user=self.user,
            fullname="Test Employee",
            attendance_code="531",
            email="employee@example.com",
        )

        # Create project for geolocation
        self.project = RealEstateProject.objects.create(
            name="Test Project",
            code="PRJ001",
        )

        # Create active geolocation
        self.geolocation = AttendanceGeolocation.objects.create(
            name="Main Office",
            code="GEO001",
            project=self.project,
            latitude=Decimal("10.7769000"),
            longitude=Decimal("106.7009000"),
            radius_m=100,
            status=AttendanceGeolocation.Status.ACTIVE,
            created_by=self.user,
            updated_by=self.user,
        )

        # Create confirmed file for image
        self.image_file = FileModel.objects.create(
            file_name="attendance.jpg",
            file_path="attendance/attendance.jpg",
            purpose="attendance_photo",
            is_confirmed=True,
            uploaded_by=self.user,
        )

    def test_geolocation_attendance_success(self):
        """Test successful GeoLocation attendance recording."""
        # Arrange
        url = reverse("hrm:attendance-record-geolocation-attendance")
        data = {
            "latitude": "10.7769000",
            "longitude": "106.7009000",
            "attendance_geolocation_id": self.geolocation.id,
            "image_id": self.image_file.id,
        }

        # Act
        response = self.client.post(url, data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["attendance_type"], "geolocation")
        self.assertEqual(response_data["employee"]["id"], self.employee.id)
        self.assertEqual(response_data["attendance_code"], "531")
        self.assertEqual(response_data["latitude"], "10.77690000000000000")
        self.assertEqual(response_data["longitude"], "106.70090000000000000")

        # Verify record was created
        self.assertTrue(AttendanceRecord.objects.filter(employee=self.employee, attendance_type="geolocation").exists())

    def test_geolocation_attendance_outside_radius(self):
        """Test GeoLocation attendance recording fails when outside radius."""
        # Arrange - Location far from geolocation (more than 100m away)
        url = reverse("hrm:attendance-record-geolocation-attendance")
        data = {
            "latitude": "10.7800000",  # About 350m away
            "longitude": "106.7050000",
            "attendance_geolocation_id": self.geolocation.id,
            "image_id": self.image_file.id,
        }

        # Act
        response = self.client.post(url, data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        error_data = json.loads(response.content.decode())
        self.assertIn("error", error_data)
        self.assertIn("location", error_data["error"])

    def test_geolocation_attendance_inactive_location(self):
        """Test GeoLocation attendance fails with inactive geolocation."""
        # Arrange - Create inactive geolocation
        inactive_geolocation = AttendanceGeolocation.objects.create(
            name="Inactive Office",
            code="GEO002",
            project=self.project,
            latitude=Decimal("10.7769000"),
            longitude=Decimal("106.7009000"),
            radius_m=100,
            status=AttendanceGeolocation.Status.INACTIVE,
            created_by=self.user,
            updated_by=self.user,
        )

        url = reverse("hrm:attendance-record-geolocation-attendance")
        data = {
            "latitude": "10.7769000",
            "longitude": "106.7009000",
            "attendance_geolocation_id": inactive_geolocation.id,
            "image_id": self.image_file.id,
        }

        # Act
        response = self.client.post(url, data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_geolocation_attendance_unconfirmed_image(self):
        """Test GeoLocation attendance fails with unconfirmed image."""
        # Arrange - Create unconfirmed file
        unconfirmed_file = FileModel.objects.create(
            file_name="unconfirmed.jpg",
            file_path="attendance/unconfirmed.jpg",
            purpose="attendance_photo",
            is_confirmed=False,
            uploaded_by=self.user,
        )

        url = reverse("hrm:attendance-record-geolocation-attendance")
        data = {
            "latitude": "10.7769000",
            "longitude": "106.7009000",
            "attendance_geolocation_id": self.geolocation.id,
            "image_id": unconfirmed_file.id,
        }

        # Act
        response = self.client.post(url, data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class WiFiAttendanceAPITest(TransactionTestCase, APITestMixin):
    """Test cases for WiFi-based attendance recording."""

    def setUp(self):
        """Set up test data."""
        # Create superuser
        self.user = User.objects.create_superuser(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create employee for the user
        self.employee = Employee.objects.create(
            user=self.user,
            fullname="Test Employee",
            attendance_code="531",
            email="employee@example.com",
        )

        # Create WiFi device
        self.wifi_device = AttendanceWifiDevice.objects.create(
            name="Office WiFi",
            code="WIFI001",
            bssid="00:11:22:33:44:55",
            state=AttendanceWifiDevice.State.IN_USE,
        )

    def test_wifi_attendance_success(self):
        """Test successful WiFi attendance recording."""
        # Arrange
        url = reverse("hrm:attendance-record-wifi-attendance")
        data = {"bssid": "00:11:22:33:44:55"}

        # Act
        response = self.client.post(url, data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["attendance_type"], "wifi")
        self.assertEqual(response_data["employee"]["id"], self.employee.id)
        self.assertEqual(response_data["attendance_code"], "531")
        self.assertEqual(response_data["attendance_wifi_device"]["id"], self.wifi_device.id)

        # Verify record was created
        self.assertTrue(AttendanceRecord.objects.filter(employee=self.employee, attendance_type="wifi").exists())

    def test_wifi_attendance_not_in_use(self):
        """Test WiFi attendance fails when device is not in use."""
        # Arrange - Create WiFi device not in use
        inactive_wifi = AttendanceWifiDevice.objects.create(
            name="Inactive WiFi",
            code="WIFI002",
            bssid="AA:BB:CC:DD:EE:FF",
            state=AttendanceWifiDevice.State.STORED,
        )

        url = reverse("hrm:attendance-record-wifi-attendance")
        data = {"bssid": "AA:BB:CC:DD:EE:FF"}

        # Act
        response = self.client.post(url, data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        error_data = json.loads(response.content.decode())
        self.assertIn("error", error_data)
        self.assertIn("bssid", error_data["error"])

    def test_wifi_attendance_device_not_found(self):
        """Test WiFi attendance fails when device doesn't exist."""
        # Arrange
        url = reverse("hrm:attendance-record-wifi-attendance")
        data = {"bssid": "FF:FF:FF:FF:FF:FF"}  # Non-existent BSSID

        # Act
        response = self.client.post(url, data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        error_data = json.loads(response.content.decode())
        self.assertIn("error", error_data)
        self.assertIn("bssid", error_data["error"])
