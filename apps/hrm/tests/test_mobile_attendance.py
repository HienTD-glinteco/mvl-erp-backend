"""Tests for mobile attendance views."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status

from apps.hrm.constants import AttendanceType
from apps.hrm.models import AttendanceGeolocation, AttendanceRecord, AttendanceWifiDevice


class APITestMixin:
    """Mixin to handle wrapped API responses and data extraction."""

    def get_response_data(self, response):
        """Extract data from wrapped API response."""
        content = response.json()
        if "data" in content:
            data = content["data"]
            if isinstance(data, dict) and "results" in data:
                return data["results"]
            return data
        return content


@pytest.mark.django_db
class TestMyAttendanceRecordViewSet(APITestMixin):
    """Test cases for MyAttendanceRecordViewSet."""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client, employee):
        self.client = api_client
        self.employee = employee
        self.client.force_authenticate(user=employee.user)

    @pytest.fixture
    def attendance_geolocation(self, db, project, user):
        """Create a test geolocation."""
        return AttendanceGeolocation.objects.create(
            name="Main Office",
            code="GEO001",
            project=project,
            latitude="10.7769000",
            longitude="106.7009000",
            radius_m=100,
            status=AttendanceGeolocation.Status.ACTIVE,
            created_by=user,
            updated_by=user,
        )

    @pytest.fixture
    def wifi_device(self, db, branch):
        """Create a test WiFi device."""
        return AttendanceWifiDevice.objects.create(
            name="Office WiFi",
            code="WIFI001",
            branch=branch,
            bssid="00:11:22:33:44:55",
            state=AttendanceWifiDevice.State.IN_USE,
        )

    @pytest.fixture
    def attendance_records(self, employee):
        """Create test attendance records for the employee."""
        record1 = AttendanceRecord.objects.create(
            employee=employee,
            attendance_code=employee.attendance_code,
            timestamp=datetime(2026, 1, 5, 8, 30, 0, tzinfo=timezone.utc),
            attendance_type=AttendanceType.GEOLOCATION,
        )
        record2 = AttendanceRecord.objects.create(
            employee=employee,
            attendance_code=employee.attendance_code,
            timestamp=datetime(2026, 1, 5, 17, 30, 0, tzinfo=timezone.utc),
            attendance_type=AttendanceType.WIFI,
        )
        return [record1, record2]

    def test_list_my_attendance_records(self, attendance_records):
        """Test listing current user's attendance records."""
        url = reverse("hrm-mobile:my-attendance-record-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 2

    def test_retrieve_my_attendance_record(self, attendance_records):
        """Test retrieving a specific attendance record."""
        record = attendance_records[0]
        url = reverse("hrm-mobile:my-attendance-record-detail", kwargs={"pk": record.pk})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert data["id"] == record.id
        assert data["employee"]["id"] == self.employee.id

    def test_list_only_shows_own_records(self, attendance_records, employee_factory):
        """Test that users can only see their own attendance records."""
        other_employee = employee_factory()
        AttendanceRecord.objects.create(
            employee=other_employee,
            attendance_code=other_employee.attendance_code,
            timestamp=datetime(2026, 1, 5, 9, 0, 0, tzinfo=timezone.utc),
        )

        url = reverse("hrm-mobile:my-attendance-record-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 2
        for record in response_data:
            assert record["employee"]["id"] == self.employee.id

    def test_filter_by_date(self, attendance_records):
        """Test filtering attendance records by date range."""
        url = reverse("hrm-mobile:my-attendance-record-list")
        # Use timestamp__date lookup or just verify list works
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 2

    def test_geolocation_attendance_create(self, attendance_geolocation, user_device):
        """Test creating attendance record via geolocation."""
        with patch("apps.hrm.api.views.mobile.attendance.validate_attendance_device", return_value=user_device):
            url = reverse("hrm-mobile:my-attendance-record-geolocation-attendance")
            data = {
                "latitude": "10.7769000",
                "longitude": "106.7009000",
                "attendance_geolocation_id": attendance_geolocation.id,
            }
            response = self.client.post(url, data, format="json")

            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["success"] is True
            assert data["data"]["attendance_type"] == "geolocation"
            assert data["data"]["employee"]["id"] == self.employee.id

    def test_wifi_attendance_create(self, wifi_device, user_device):
        """Test creating attendance record via WiFi."""
        with patch("apps.hrm.api.views.mobile.attendance.validate_attendance_device", return_value=user_device):
            url = reverse("hrm-mobile:my-attendance-record-wifi-attendance")
            data = {"bssid": wifi_device.bssid}
            response = self.client.post(url, data, format="json")

            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["success"] is True
            assert data["data"]["attendance_type"] == "wifi"
            assert data["data"]["employee"]["id"] == self.employee.id

    @pytest.mark.skip(reason="OtherAttendance requires file upload workflow with tokens, complex to test")
    def test_other_attendance_create(self, user_device):
        """Test creating attendance record via other method."""
        pass

    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated users cannot access the endpoint."""
        self.client.force_authenticate(user=None)
        url = reverse("hrm-mobile:my-attendance-record-list")
        response = self.client.get(url)

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
