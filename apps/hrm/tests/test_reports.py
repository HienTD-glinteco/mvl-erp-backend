"""Tests for Employee Status Breakdown Report model and API endpoints."""

from datetime import date, timedelta

import pytest
from django.db import IntegrityError
from django.urls import reverse
from rest_framework import status

from apps.hrm.models import Block, Branch, Department, Employee, EmployeeStatusBreakdownReport


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
class TestEmployeeStatusBreakdownReportModel:
    """Test cases for EmployeeStatusBreakdownReport model."""

    def test_create_report_with_all_fields(self, branch, block, department):
        """Test creating report with all fields."""
        report = EmployeeStatusBreakdownReport.objects.create(
            report_date=date(2025, 11, 1),
            branch=branch,
            block=block,
            department=department,
            count_active=50,
            count_onboarding=5,
            count_maternity_leave=2,
            count_unpaid_leave=1,
            count_resigned=3,
            total_not_resigned=58,
            count_resigned_reasons={
                Employee.ResignationReason.VOLUNTARY_CAREER_CHANGE: 1,
                Employee.ResignationReason.VOLUNTARY_PERSONAL: 2,
            },
        )

        assert report.count_active == 50
        assert report.count_onboarding == 5
        assert report.count_maternity_leave == 2
        assert report.count_unpaid_leave == 1
        assert report.count_resigned == 3
        assert report.total_not_resigned == 58
        assert len(report.count_resigned_reasons) == 2
        assert report.count_resigned_reasons[Employee.ResignationReason.VOLUNTARY_CAREER_CHANGE] == 1

    def test_unique_constraint_on_date_and_org_units(self, branch, block, department):
        """Test unique constraint on report_date + branch + block + department."""
        EmployeeStatusBreakdownReport.objects.create(
            report_date=date(2025, 11, 1),
            branch=branch,
            block=block,
            department=department,
            count_active=50,
            total_not_resigned=58,
        )

        with pytest.raises(IntegrityError):
            EmployeeStatusBreakdownReport.objects.create(
                report_date=date(2025, 11, 1),
                branch=branch,
                block=block,
                department=department,
                count_active=60,
                total_not_resigned=68,
            )

    def test_json_field_default(self, branch, block, department):
        """Test that count_resigned_reasons defaults to empty dict."""
        report = EmployeeStatusBreakdownReport.objects.create(
            report_date=date(2025, 11, 1),
            branch=branch,
            block=block,
            department=department,
        )

        assert isinstance(report.count_resigned_reasons, dict)
        assert len(report.count_resigned_reasons) == 0


@pytest.mark.django_db
class TestEmployeeStatusBreakdownReportAPI(APITestMixin):
    """Test cases for Employee Status Breakdown Report API endpoints."""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client, user):
        self.client = api_client
        self.user = user

    def test_employee_status_breakdown_weekly(self, branch, block, department):
        """Test employee status breakdown report with weekly aggregation."""
        week1_monday = date(2025, 10, 20)
        week2_monday = date(2025, 10, 27)
        week3_monday = date(2025, 11, 3)

        EmployeeStatusBreakdownReport.objects.create(
            report_date=week1_monday + timedelta(days=6),
            branch=branch,
            block=block,
            department=department,
            total_not_resigned=100,
        )

        EmployeeStatusBreakdownReport.objects.create(
            report_date=week2_monday + timedelta(days=6),
            branch=branch,
            block=block,
            department=department,
            total_not_resigned=105,
        )

        EmployeeStatusBreakdownReport.objects.create(
            report_date=week3_monday + timedelta(days=6),
            branch=branch,
            block=block,
            department=department,
            total_not_resigned=110,
        )

        url = reverse("hrm:employee-reports-employee-status-breakdown")
        response = self.client.get(
            url,
            {
                "period_type": "week",
                "from_date": week1_monday.isoformat(),
                "to_date": (week3_monday + timedelta(days=6)).isoformat(),
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)

        assert "time_headers" in data
        assert "data" in data
        assert len(data["time_headers"]) == 4
        assert "Average" in data["time_headers"][-1]

        assert len(data["data"]) == 1
        branch_item = data["data"][0]
        assert branch_item["type"] == "branch"
        assert branch_item["name"] == branch.name

        assert len(branch_item["statistics"]) == 4
        assert branch_item["statistics"][0] == 100
        assert branch_item["statistics"][1] == 105
        assert branch_item["statistics"][2] == 110
        assert abs(branch_item["statistics"][3] - 105.00) < 0.01

    def test_employee_resigned_breakdown_monthly(self, branch, block, department):
        """Test employee resigned breakdown report with monthly aggregation."""
        month1 = date(2025, 10, 31)
        month2 = date(2025, 11, 30)

        EmployeeStatusBreakdownReport.objects.create(
            report_date=month1,
            branch=branch,
            block=block,
            department=department,
            count_resigned=5,
        )

        EmployeeStatusBreakdownReport.objects.create(
            report_date=month2,
            branch=branch,
            block=block,
            department=department,
            count_resigned=8,
        )

        url = reverse("hrm:employee-reports-employee-resigned-breakdown")
        response = self.client.get(
            url,
            {
                "period_type": "month",
                "from_date": date(2025, 10, 1).isoformat(),
                "to_date": date(2025, 11, 30).isoformat(),
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)

        assert "time_headers" in data
        assert "data" in data
        assert len(data["time_headers"]) == 3

        branch_item = data["data"][0]
        assert len(branch_item["statistics"]) == 3
        assert branch_item["statistics"][0] == 5
        assert branch_item["statistics"][1] == 8
        assert abs(branch_item["statistics"][2] - 6.50) < 0.01

    def test_bucket_target_date_priority(self, branch, block, department):
        """Test that target date (bucket_end) is prioritized over fallback."""
        target_date = date(2025, 10, 31)
        other_date = date(2025, 10, 15)

        EmployeeStatusBreakdownReport.objects.create(
            report_date=other_date,
            branch=branch,
            block=block,
            department=department,
            total_not_resigned=50,
        )

        EmployeeStatusBreakdownReport.objects.create(
            report_date=target_date,
            branch=branch,
            block=block,
            department=department,
            total_not_resigned=100,
        )

        url = reverse("hrm:employee-reports-employee-status-breakdown")
        response = self.client.get(
            url,
            {
                "period_type": "month",
                "from_date": date(2025, 10, 1).isoformat(),
                "to_date": date(2025, 10, 31).isoformat(),
            },
        )

        data = self.get_response_data(response)
        branch_item = data["data"][0]
        assert branch_item["statistics"][0] == 100

    def test_bucket_fallback_to_latest_in_bucket(self, branch, block, department):
        """Test fallback to latest record within bucket when target date missing."""
        date1 = date(2025, 10, 10)
        date2 = date(2025, 10, 25)

        EmployeeStatusBreakdownReport.objects.create(
            report_date=date1,
            branch=branch,
            block=block,
            department=department,
            total_not_resigned=50,
        )

        EmployeeStatusBreakdownReport.objects.create(
            report_date=date2,
            branch=branch,
            block=block,
            department=department,
            total_not_resigned=75,
        )

        url = reverse("hrm:employee-reports-employee-status-breakdown")
        response = self.client.get(
            url,
            {
                "period_type": "month",
                "from_date": date(2025, 10, 1).isoformat(),
                "to_date": date(2025, 10, 31).isoformat(),
            },
        )

        data = self.get_response_data(response)
        branch_item = data["data"][0]
        assert branch_item["statistics"][0] == 75

    def test_missing_bucket_returns_zero(self, branch, block, department):
        """Test that missing buckets return 0."""
        EmployeeStatusBreakdownReport.objects.create(
            report_date=date(2025, 10, 31),
            branch=branch,
            block=block,
            department=department,
            total_not_resigned=100,
        )

        url = reverse("hrm:employee-reports-employee-status-breakdown")
        response = self.client.get(
            url,
            {
                "period_type": "month",
                "from_date": date(2025, 10, 1).isoformat(),
                "to_date": date(2025, 11, 30).isoformat(),
            },
        )

        data = self.get_response_data(response)
        branch_item = data["data"][0]
        assert len(branch_item["statistics"]) == 3
        assert branch_item["statistics"][0] == 100
        assert branch_item["statistics"][1] == 0
        assert abs(branch_item["statistics"][2] - 50.00) < 0.01

    def test_quarterly_aggregation(self, branch, block, department):
        """Test quarterly aggregation."""
        EmployeeStatusBreakdownReport.objects.create(
            report_date=date(2025, 12, 31),
            branch=branch,
            block=block,
            department=department,
            count_resigned=12,
        )

        url = reverse("hrm:employee-reports-employee-resigned-breakdown")
        response = self.client.get(
            url,
            {
                "period_type": "quarter",
                "from_date": date(2025, 10, 1).isoformat(),
                "to_date": date(2025, 12, 31).isoformat(),
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data["time_headers"]) == 2
        assert "Quarter" in data["time_headers"][0]

    def test_yearly_aggregation(self, branch, block, department):
        """Test yearly aggregation."""
        EmployeeStatusBreakdownReport.objects.create(
            report_date=date(2025, 12, 31),
            branch=branch,
            block=block,
            department=department,
            total_not_resigned=200,
        )

        url = reverse("hrm:employee-reports-employee-status-breakdown")
        response = self.client.get(
            url,
            {
                "period_type": "year",
                "from_date": date(2025, 1, 1).isoformat(),
                "to_date": date(2025, 12, 31).isoformat(),
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data["time_headers"]) == 2
        assert "Year" in data["time_headers"][0]

    def test_missing_required_params(self):
        """Test that missing required parameters return validation error."""
        url = reverse("hrm:employee-reports-employee-status-breakdown")
        response = self.client.get(url, {})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        content = response.json()
        assert content["success"] is False
        assert content["error"] is not None

    def test_response_envelope_format(self, branch, block, department):
        """Test that response uses correct envelope format."""
        EmployeeStatusBreakdownReport.objects.create(
            report_date=date(2025, 10, 31),
            branch=branch,
            block=block,
            department=department,
            total_not_resigned=100,
        )

        url = reverse("hrm:employee-reports-employee-status-breakdown")
        response = self.client.get(
            url,
            {
                "period_type": "month",
                "from_date": date(2025, 10, 1).isoformat(),
                "to_date": date(2025, 10, 31).isoformat(),
            },
        )

        assert response.status_code == status.HTTP_200_OK
        content = response.json()
        assert "success" in content
        assert "data" in content
        assert "error" in content
        assert content["success"] is True
        assert content["data"] is not None

    def test_organizational_filters(self, branch, block, department, province, admin_unit):
        """Test filtering by branch/block/department."""
        branch2 = Branch.objects.create(
            name="HCMC Branch",
            province=province,
            administrative_unit=admin_unit,
        )
        block2 = Block.objects.create(
            name="Support Block",
            branch=branch2,
            block_type=Block.BlockType.SUPPORT,
        )
        dept2 = Department.objects.create(
            name="HR Department",
            branch=branch2,
            block=block2,
            function=Department.DepartmentFunction.HR_ADMIN,
        )

        EmployeeStatusBreakdownReport.objects.create(
            report_date=date(2025, 10, 31),
            branch=branch,
            block=block,
            department=department,
            total_not_resigned=100,
        )

        EmployeeStatusBreakdownReport.objects.create(
            report_date=date(2025, 10, 31),
            branch=branch2,
            block=block2,
            department=dept2,
            total_not_resigned=50,
        )

        url = reverse("hrm:employee-reports-employee-status-breakdown")
        response = self.client.get(
            url,
            {
                "period_type": "month",
                "from_date": date(2025, 10, 1).isoformat(),
                "to_date": date(2025, 10, 31).isoformat(),
                "branch": branch.id,
            },
        )

        data = self.get_response_data(response)
        assert len(data["data"]) == 1
        assert data["data"][0]["name"] == branch.name
        assert data["data"][0]["statistics"][0] == 100

    def test_filter_by_block_type_business(self, branch, block, department, province, admin_unit):
        """Test filtering by business block type."""
        branch2 = Branch.objects.create(
            name="HCMC Branch",
            province=province,
            administrative_unit=admin_unit,
        )
        support_block = Block.objects.create(
            name="Support Block",
            branch=branch2,
            block_type=Block.BlockType.SUPPORT,
        )
        support_dept = Department.objects.create(
            name="HR Department",
            branch=branch2,
            block=support_block,
            function=Department.DepartmentFunction.HR_ADMIN,
        )

        EmployeeStatusBreakdownReport.objects.create(
            report_date=date(2025, 10, 31),
            branch=branch,
            block=block,
            department=department,
            total_not_resigned=100,
        )

        EmployeeStatusBreakdownReport.objects.create(
            report_date=date(2025, 10, 31),
            branch=branch2,
            block=support_block,
            department=support_dept,
            total_not_resigned=50,
        )

        url = reverse("hrm:employee-reports-employee-status-breakdown")
        response = self.client.get(
            url,
            {
                "period_type": "month",
                "from_date": date(2025, 10, 1).isoformat(),
                "to_date": date(2025, 10, 31).isoformat(),
                "block_type": "business",
            },
        )

        data = self.get_response_data(response)
        assert len(data["data"]) == 1
        assert data["data"][0]["name"] == branch.name
        assert data["data"][0]["statistics"][0] == 100
        assert data["data"][0]["children"][0]["name"] == block.name

    def test_filter_by_block_type_support(self, branch, block, department, province, admin_unit):
        """Test filtering by support block type."""
        branch2 = Branch.objects.create(
            name="HCMC Branch",
            province=province,
            administrative_unit=admin_unit,
        )
        support_block = Block.objects.create(
            name="Support Block",
            branch=branch2,
            block_type=Block.BlockType.SUPPORT,
        )
        support_dept = Department.objects.create(
            name="HR Department",
            branch=branch2,
            block=support_block,
            function=Department.DepartmentFunction.HR_ADMIN,
        )

        EmployeeStatusBreakdownReport.objects.create(
            report_date=date(2025, 10, 31),
            branch=branch,
            block=block,
            department=department,
            total_not_resigned=100,
        )

        EmployeeStatusBreakdownReport.objects.create(
            report_date=date(2025, 10, 31),
            branch=branch2,
            block=support_block,
            department=support_dept,
            total_not_resigned=50,
        )

        url = reverse("hrm:employee-reports-employee-status-breakdown")
        response = self.client.get(
            url,
            {
                "period_type": "month",
                "from_date": date(2025, 10, 1).isoformat(),
                "to_date": date(2025, 10, 31).isoformat(),
                "block_type": "support",
            },
        )

        data = self.get_response_data(response)
        assert len(data["data"]) == 1
        assert data["data"][0]["name"] == "HCMC Branch"
        assert data["data"][0]["statistics"][0] == 50
        assert data["data"][0]["children"][0]["name"] == "Support Block"
