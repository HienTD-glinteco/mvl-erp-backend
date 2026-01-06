"""Tests for mobile timesheet views."""

from datetime import date

import pytest
from django.urls import reverse
from rest_framework import status

from apps.hrm.constants import ProposalStatus, ProposalType, TimesheetStatus
from apps.hrm.models import EmployeeMonthlyTimesheet, Proposal, ProposalTimeSheetEntry, TimeSheetEntry


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
class TestMyTimesheetViewSet(APITestMixin):
    """Test cases for MyTimesheetViewSet."""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client, employee):
        self.client = api_client
        self.employee = employee
        self.client.force_authenticate(user=employee.user)

    @pytest.fixture
    def timesheet_entries(self, employee):
        """Create test timesheet entries for the employee."""
        entries = []
        for day in range(1, 6):
            entry = TimeSheetEntry.objects.create(
                employee=employee,
                date=date(2026, 1, day),
                start_time=f"2026-01-{day:02d}T08:00:00Z",
                end_time=f"2026-01-{day:02d}T17:00:00Z",
                morning_hours=4.0,
                afternoon_hours=4.0,
                official_hours=8.0,
                working_days=1.0,
                status=TimesheetStatus.ON_TIME,
            )
            entries.append(entry)
        return entries

    @pytest.fixture
    def monthly_timesheet(self, employee):
        """Create a monthly timesheet summary."""
        EmployeeMonthlyTimesheet.objects.filter(employee=employee, month_key="202601").delete()
        return EmployeeMonthlyTimesheet.objects.create(
            employee=employee,
            month_key="202601",
            report_date=date(2026, 1, 31),
            official_working_days=20.0,
            total_working_days=20.0,
            probation_working_days=0.0,
            unexcused_absence_days=0.0,
            public_holiday_days=1.0,
        )

    def test_list_my_timesheets(self, timesheet_entries, monthly_timesheet):
        """Test listing current user's timesheets for the current month."""
        url = reverse("hrm-mobile:my-timesheet-list")
        response = self.client.get(url, {"month": "01/2026"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        timesheet_data = data["data"]
        assert timesheet_data["employee"]["id"] == self.employee.id
        assert len(timesheet_data["dates"]) == 31
        assert timesheet_data["official_work_days"] == "20.00"

    def test_list_my_timesheets_default_current_month(self, timesheet_entries):
        """Test listing timesheets defaults to current month."""
        url = reverse("hrm-mobile:my-timesheet-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["employee"]["id"] == self.employee.id

    def test_retrieve_my_timesheet(self, timesheet_entries, monthly_timesheet):
        """Test retrieving timesheet for a specific month."""
        url = reverse("hrm-mobile:my-timesheet-detail", kwargs={"pk": self.employee.pk})
        response = self.client.get(url, {"month": "01/2026"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["employee"]["id"] == self.employee.id

    def test_filter_by_month(self, timesheet_entries):
        """Test filtering timesheets by month."""
        url = reverse("hrm-mobile:my-timesheet-list")
        response = self.client.get(url, {"month": "01/2026"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        dates_with_entries = [d for d in data["data"]["dates"] if d.get("id")]
        assert len(dates_with_entries) == 5

    def test_future_month_validation(self):
        """Test that future months are rejected."""
        url = reverse("hrm-mobile:my-timesheet-list")
        response = self.client.get(url, {"month": "12/2099"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_timesheet_with_complaint(self, timesheet_entries, employee):
        """Test timesheet entries with complaints are flagged."""
        entry = timesheet_entries[0]
        proposal = Proposal.objects.create(
            created_by=employee,
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            proposal_status=ProposalStatus.PENDING,
            proposal_date=date.today(),
        )
        ProposalTimeSheetEntry.objects.create(
            proposal=proposal,
            timesheet_entry=entry,
        )

        url = reverse("hrm-mobile:my-timesheet-list")
        response = self.client.get(url, {"month": "01/2026"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        dates_data = data["data"]["dates"]
        complaint_entries = [d for d in dates_data if d.get("has_complaint")]
        assert len(complaint_entries) == 1

    def test_only_own_timesheets(self, timesheet_entries, employee_factory):
        """Test that users can only see their own timesheets."""
        other_employee = employee_factory()
        TimeSheetEntry.objects.create(
            employee=other_employee,
            date=date(2026, 1, 10),
            start_time="2026-01-10T08:00:00Z",
            end_time="2026-01-10T17:00:00Z",
        )

        url = reverse("hrm-mobile:my-timesheet-list")
        response = self.client.get(url, {"month": "01/2026"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"]["employee"]["id"] == self.employee.id
        dates_with_entries = [d for d in data["data"]["dates"] if d.get("id")]
        assert len(dates_with_entries) == 5

    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated users cannot access timesheets."""
        self.client.force_authenticate(user=None)
        url = reverse("hrm-mobile:my-timesheet-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestMyTimesheetEntryViewSet(APITestMixin):
    """Test cases for MyTimesheetEntryViewSet."""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client, employee):
        self.client = api_client
        self.employee = employee
        self.client.force_authenticate(user=employee.user)

    @pytest.fixture
    def timesheet_entry(self, employee):
        """Create a test timesheet entry."""
        return TimeSheetEntry.objects.create(
            employee=employee,
            date=date(2026, 1, 15),
            start_time="2026-01-15T08:00:00Z",
            end_time="2026-01-15T17:00:00Z",
            morning_hours=4.0,
            afternoon_hours=4.0,
            official_hours=8.0,
            working_days=1.0,
            status=TimesheetStatus.ON_TIME,
            note="Regular workday",
        )

    def test_retrieve_my_timesheet_entry(self, timesheet_entry):
        """Test retrieving a specific timesheet entry."""
        url = reverse("hrm-mobile:my-timesheet-entry-detail", kwargs={"pk": timesheet_entry.pk})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["id"] == timesheet_entry.id
        assert data["data"]["employee"]["id"] == self.employee.id
        assert data["data"]["date"] == "2026-01-15"
        assert data["data"]["morning_hours"] == "4.00"
        assert data["data"]["afternoon_hours"] == "4.00"
        assert data["data"]["note"] == "Regular workday"

    def test_cannot_access_other_employee_entry(self, timesheet_entry, employee_factory):
        """Test that users cannot access other employees' timesheet entries."""
        other_employee = employee_factory()
        other_entry = TimeSheetEntry.objects.create(
            employee=other_employee,
            date=date(2026, 1, 16),
            start_time="2026-01-16T08:00:00Z",
            end_time="2026-01-16T17:00:00Z",
        )

        url = reverse("hrm-mobile:my-timesheet-entry-detail", kwargs={"pk": other_entry.pk})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_entry_with_manual_correction(self, timesheet_entry, employee):
        """Test retrieving entry with manual correction information."""
        timesheet_entry.is_manually_corrected = True
        timesheet_entry.manually_corrected_by = employee
        timesheet_entry.save()

        url = reverse("hrm-mobile:my-timesheet-entry-detail", kwargs={"pk": timesheet_entry.pk})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["manually_corrected_by"]["id"] == employee.id

    def test_unauthenticated_access_denied(self, timesheet_entry):
        """Test that unauthenticated users cannot access entries."""
        self.client.force_authenticate(user=None)
        url = reverse("hrm-mobile:my-timesheet-entry-detail", kwargs={"pk": timesheet_entry.pk})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN
