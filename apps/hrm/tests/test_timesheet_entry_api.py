from datetime import date, time

import pytest
from django.urls import reverse
from rest_framework import status

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import Block, Branch, Department, Employee, TimeSheetEntry
from libs.datetimes import combine_datetime

pytestmark = pytest.mark.django_db


class TestTimeSheetEntryAPI:
    @pytest.fixture
    def employee(self):
        province = Province.objects.create(code="01", name="Test Province")
        admin_unit = AdministrativeUnit.objects.create(
            code="01",
            name="Test Admin Unit",
            parent_province=province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )
        branch = Branch.objects.create(
            code="CN001",
            name="Test Branch",
            province=province,
            administrative_unit=admin_unit,
        )
        block = Block.objects.create(
            code="KH001",
            name="Test Block",
            branch=branch,
            block_type=Block.BlockType.BUSINESS,
        )
        department = Department.objects.create(
            code="PB001",
            name="Test Department",
            branch=branch,
            block=block,
        )
        return Employee.objects.create(
            fullname="John Doe",
            username="johndoe",
            email="john@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="john.personal@example.com",
            start_date="2024-01-01",
            branch=branch,
            block=block,
            department=department,
            citizen_id="123456789",
        )

    def test_retrieve_timesheet_entry(self, api_client, superuser, employee):
        entry_date = date(2025, 1, 15)
        start_dt = combine_datetime(entry_date, time(8, 0))
        end_dt = combine_datetime(entry_date, time(17, 0))

        entry = TimeSheetEntry.objects.create(
            employee=employee, date=entry_date, check_in_time=start_dt, check_out_time=end_dt
        )

        url = reverse("hrm:timesheet-entry-detail", args=[entry.id])
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["id"] == entry.id
        assert data["data"]["date"] == "2025-01-15"
        # DRF DateTimeField serializes to ISO 8601 string.
        # Depending on settings, it might include 'Z' or offset.
        # We'll check if it starts with the expected time or contains it.
        assert "08:00:00" in data["data"]["start_time"]
        assert "17:00:00" in data["data"]["end_time"]

    def test_retrieve_timesheet_entry_not_found(self, api_client, superuser):
        url = reverse("hrm:timesheet-entry-detail", args=[99999])
        response = api_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND
