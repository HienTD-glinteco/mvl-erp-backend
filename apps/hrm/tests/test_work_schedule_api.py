from datetime import time

import pytest
from django.urls import reverse
from rest_framework import status

from apps.hrm.models import WorkSchedule


class APITestMixin:
    """Mixin to handle wrapped API responses and data extraction"""

    def get_response_data(self, response):
        """Extract data from wrapped API response"""
        content = response.json()
        if "data" in content:
            data = content["data"]
            # Handle paginated responses - extract results list
            if isinstance(data, dict) and "results" in data:
                return data["results"]
            return data
        return content


@pytest.mark.django_db
class TestWorkScheduleAPI(APITestMixin):
    """Test cases for Work Schedule API endpoints"""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client):
        self.client = api_client

    @pytest.fixture
    def schedules(self, db):
        """Create test work schedules."""
        monday_schedule = WorkSchedule.objects.create(
            weekday=WorkSchedule.Weekday.MONDAY,
            morning_start_time=time(8, 0),
            morning_end_time=time(12, 0),
            noon_start_time=time(12, 0),
            noon_end_time=time(13, 30),
            afternoon_start_time=time(13, 30),
            afternoon_end_time=time(17, 30),
            allowed_late_minutes=5,
            note="Standard work schedule",
        )

        saturday_schedule = WorkSchedule.objects.create(
            weekday=WorkSchedule.Weekday.SATURDAY,
            morning_start_time=None,
            morning_end_time=None,
            noon_start_time=None,
            noon_end_time=None,
            afternoon_start_time=None,
            afternoon_end_time=None,
            allowed_late_minutes=None,
            note="Weekend - no work",
        )
        return monday_schedule, saturday_schedule

    def test_list_work_schedules(self, schedules):
        """Test listing work schedules via API"""
        url = reverse("hrm:work-schedule-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert len(response_data) == 2

        # Find monday schedule in response
        monday_data = next((item for item in response_data if item["weekday"] == WorkSchedule.Weekday.MONDAY), None)
        assert monday_data is not None
        assert monday_data["morning_time"] == "08:00 - 12:00"
        assert monday_data["noon_time"] == "12:00 - 13:30"
        assert monday_data["afternoon_time"] == "13:30 - 17:30"
        assert monday_data["allowed_late_minutes"] == 5
        assert monday_data["note"] == "Standard work schedule"

        # Find saturday schedule in response
        saturday_data = next(
            (item for item in response_data if item["weekday"] == WorkSchedule.Weekday.SATURDAY), None
        )
        assert saturday_data is not None
        assert saturday_data["morning_time"] is None
        assert saturday_data["noon_time"] is None
        assert saturday_data["afternoon_time"] is None
        assert saturday_data["note"] == "Weekend - no work"

    def test_list_work_schedules_ordering(self, schedules):
        """Test work schedules are ordered by weekday"""
        url = reverse("hrm:work-schedule-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)

        # Check ordering (by weekday integer: 2=Monday, 7=Saturday)
        assert response_data[0]["weekday"] == WorkSchedule.Weekday.MONDAY
        assert response_data[1]["weekday"] == WorkSchedule.Weekday.SATURDAY

    def test_create_not_allowed(self, schedules):
        """Test that create operation is not allowed (list-only viewset)"""
        url = reverse("hrm:work-schedule-list")
        data = {
            "weekday": WorkSchedule.Weekday.TUESDAY,
            "morning_time": "08:00-12:00",
            "noon_time": "12:00-13:30",
            "afternoon_time": "13:30-17:30",
            "allowed_late_minutes": 5,
        }
        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
