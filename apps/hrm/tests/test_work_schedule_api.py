import json
from datetime import time

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.hrm.models import WorkSchedule

User = get_user_model()


class APITestMixin:
    """Mixin to handle wrapped API responses and data extraction"""

    def get_response_data(self, response):
        """Extract data from wrapped API response"""
        content = json.loads(response.content.decode())
        if "data" in content:
            data = content["data"]
            # Handle paginated responses - extract results list
            if isinstance(data, dict) and "results" in data:
                return data["results"]
            return data
        return content


class WorkScheduleAPITest(TransactionTestCase, APITestMixin):
    """Test cases for Work Schedule API endpoints"""

    def setUp(self):
        # Clear all existing data for clean tests
        WorkSchedule.objects.all().delete()
        User.objects.all().delete()

        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create test work schedules
        self.monday_schedule = WorkSchedule.objects.create(
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

        self.saturday_schedule = WorkSchedule.objects.create(
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

    def test_list_work_schedules(self):
        """Test listing work schedules via API"""
        url = reverse("hrm:work-schedule-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 2)

        # Find monday schedule in response
        monday_data = next((item for item in response_data if item["weekday"] == WorkSchedule.Weekday.MONDAY), None)
        self.assertIsNotNone(monday_data)
        self.assertEqual(monday_data["morning_time"], "08:00 - 12:00")
        self.assertEqual(monday_data["noon_time"], "12:00 - 13:30")
        self.assertEqual(monday_data["afternoon_time"], "13:30 - 17:30")
        self.assertEqual(monday_data["allowed_late_minutes"], 5)
        self.assertEqual(monday_data["note"], "Standard work schedule")

        # Find saturday schedule in response
        saturday_data = next(
            (item for item in response_data if item["weekday"] == WorkSchedule.Weekday.SATURDAY), None
        )
        self.assertIsNotNone(saturday_data)
        self.assertIsNone(saturday_data["morning_time"])
        self.assertIsNone(saturday_data["noon_time"])
        self.assertIsNone(saturday_data["afternoon_time"])
        self.assertEqual(saturday_data["note"], "Weekend - no work")

    def test_list_work_schedules_ordering(self):
        """Test work schedules are ordered by weekday"""
        url = reverse("hrm:work-schedule-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)

        # Check ordering (by weekday integer: 2=Monday, 7=Saturday)
        self.assertEqual(response_data[0]["weekday"], WorkSchedule.Weekday.MONDAY)
        self.assertEqual(response_data[1]["weekday"], WorkSchedule.Weekday.SATURDAY)

    def test_create_not_allowed(self):
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

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
