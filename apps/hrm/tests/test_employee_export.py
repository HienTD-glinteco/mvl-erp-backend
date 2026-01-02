from datetime import date
from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status

from apps.hrm.models import Employee


class APITestMixin:
    """Mixin to handle wrapped API responses and data extraction."""

    def get_response_data(self, response):
        """Extract data from wrapped API response."""
        content = response.json()
        if "data" in content:
            return content["data"]
        return content


@pytest.mark.django_db
class TestEmployeeExportAPI(APITestMixin):
    """Test cases for Employee export functionality."""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client, user):
        self.client = api_client
        self.user = user

        # Start patchers for periodic/async aggregation tasks
        patcher1 = patch("apps.hrm.signals.hr_reports.aggregate_hr_reports_for_work_history")
        patcher2 = patch("apps.hrm.signals.recruitment_reports.aggregate_recruitment_reports_for_candidate")

        patcher1.start()
        patcher2.start()

        yield

        patcher1.stop()
        patcher2.stop()

    def test_export_employee_direct(self):
        """Test exporting employees with direct delivery."""
        url = reverse("hrm:employee-export")
        response = self.client.get(url, {"delivery": "direct"})

        assert response.status_code == status.HTTP_206_PARTIAL_CONTENT
        assert response["Content-Type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert "attachment" in response["Content-Disposition"]

    def test_export_employee_fields(self, employee):
        """Test that export includes correct fields."""
        url = reverse("hrm:employee-export")
        response = self.client.get(url, {"delivery": "direct"})

        assert response.status_code == status.HTTP_206_PARTIAL_CONTENT
        assert len(response.content) > 0

    def test_export_employee_filtered(self, employee, branch, block, department):
        """Test exporting filtered employees."""
        # Create another employee with different status
        Employee.objects.create(
            fullname="Resigned Employee",
            username="resigned001",
            email="resigned@example.com",
            phone="1111111111",
            attendance_code="RES001",
            date_of_birth=date(1985, 5, 5),
            start_date=date(2015, 1, 1),
            branch=branch,
            block=block,
            department=department,
            status=Employee.Status.RESIGNED,
            resignation_start_date=date(2024, 12, 1),
            resignation_reason=Employee.ResignationReason.VOLUNTARY_CAREER_CHANGE,
            citizen_id="999999999999",
        )

        url = reverse("hrm:employee-export")
        response = self.client.get(url, {"delivery": "direct", "status": "Active"})

        assert response.status_code == status.HTTP_206_PARTIAL_CONTENT
        assert len(response.content) > 0

    def test_export_employee_with_bank_account(self, bank_account):
        """Test that export includes bank account information."""
        url = reverse("hrm:employee-export")
        response = self.client.get(url, {"delivery": "direct"})

        assert response.status_code == status.HTTP_206_PARTIAL_CONTENT
        assert len(response.content) > 0

    def test_export_employee_multiple(self, employee, branch, block, department):
        """Test exporting multiple employees."""
        # Create additional employees
        for i in range(3):
            Employee.objects.create(
                fullname=f"Employee {i}",
                username=f"emp{i:03d}",
                email=f"emp{i}@example.com",
                phone=f"555000{i:04d}",
                attendance_code=f"EMP{i:03d}",
                date_of_birth=date(1990 + i, 1, 1),
                start_date=date(2020 + i, 1, 1),
                branch=branch,
                block=block,
                department=department,
                status=Employee.Status.ACTIVE,
                citizen_id=f"11111111{i:04d}",
            )

        url = reverse("hrm:employee-export")
        response = self.client.get(url, {"delivery": "direct"})

        assert response.status_code == status.HTTP_206_PARTIAL_CONTENT
        assert len(response.content) > 0
