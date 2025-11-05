"""Tests for Employee Status Breakdown Report model and API endpoints."""

import json
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import Block, Branch, Department, Employee, EmployeeStatusBreakdownReport

User = get_user_model()


class APITestMixin:
    """Mixin to handle wrapped API responses and data extraction"""

    def get_response_data(self, response):
        """Extract data from wrapped API response"""
        content = json.loads(response.content.decode())
        if "data" in content:
            data = content["data"]
            if isinstance(data, dict) and "results" in data:
                return data["results"]
            return data
        return content


class EmployeeStatusBreakdownReportModelTest(TransactionTestCase):
    """Test cases for EmployeeStatusBreakdownReport model"""

    def setUp(self):
        """Set up test data"""
        EmployeeStatusBreakdownReport.objects.all().delete()
        Department.objects.all().delete()
        Block.objects.all().delete()
        Branch.objects.all().delete()

        self.province = Province.objects.create(name="Hanoi", code="01")
        self.admin_unit = AdministrativeUnit.objects.create(
            name="City",
            code="TP",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )

        self.branch = Branch.objects.create(
            name="Hanoi Branch",
            province=self.province,
            administrative_unit=self.admin_unit,
        )

        self.block = Block.objects.create(
            name="Business Block",
            branch=self.branch,
            block_type=Block.BlockType.BUSINESS,
        )

        self.department = Department.objects.create(
            name="IT Department",
            branch=self.branch,
            block=self.block,
            function=Department.DepartmentFunction.BUSINESS,
        )

    def test_create_report_with_all_fields(self):
        """Test creating report with all fields"""
        # Arrange & Act
        report = EmployeeStatusBreakdownReport.objects.create(
            report_date=date(2025, 11, 1),
            branch=self.branch,
            block=self.block,
            department=self.department,
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

        # Assert
        self.assertEqual(report.count_active, 50)
        self.assertEqual(report.count_onboarding, 5)
        self.assertEqual(report.count_maternity_leave, 2)
        self.assertEqual(report.count_unpaid_leave, 1)
        self.assertEqual(report.count_resigned, 3)
        self.assertEqual(report.total_not_resigned, 58)
        self.assertEqual(len(report.count_resigned_reasons), 2)
        self.assertEqual(report.count_resigned_reasons[Employee.ResignationReason.VOLUNTARY_CAREER_CHANGE], 1)

    def test_unique_constraint_on_date_and_org_units(self):
        """Test unique constraint on report_date + branch + block + department"""
        # Arrange
        EmployeeStatusBreakdownReport.objects.create(
            report_date=date(2025, 11, 1),
            branch=self.branch,
            block=self.block,
            department=self.department,
            count_active=50,
            total_not_resigned=58,
        )

        # Act & Assert
        with self.assertRaises(IntegrityError):
            EmployeeStatusBreakdownReport.objects.create(
                report_date=date(2025, 11, 1),
                branch=self.branch,
                block=self.block,
                department=self.department,
                count_active=60,
                total_not_resigned=68,
            )

    def test_json_field_default(self):
        """Test that count_resigned_reasons defaults to empty dict"""
        # Arrange & Act
        report = EmployeeStatusBreakdownReport.objects.create(
            report_date=date(2025, 11, 1),
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

        # Assert
        self.assertIsInstance(report.count_resigned_reasons, dict)
        self.assertEqual(len(report.count_resigned_reasons), 0)


class EmployeeStatusBreakdownReportAPITest(TransactionTestCase, APITestMixin):
    """Test cases for Employee Status Breakdown Report API endpoints"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.province = Province.objects.create(name="Hanoi", code="01")
        self.admin_unit = AdministrativeUnit.objects.create(
            name="City",
            code="TP",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )

        self.branch = Branch.objects.create(
            name="Hanoi Branch",
            province=self.province,
            administrative_unit=self.admin_unit,
        )

        self.block = Block.objects.create(
            name="Business Block",
            branch=self.branch,
            block_type=Block.BlockType.BUSINESS,
        )

        self.department = Department.objects.create(
            name="IT Department",
            branch=self.branch,
            block=self.block,
            function=Department.DepartmentFunction.BUSINESS,
        )

    def test_employee_status_breakdown_weekly(self):
        """Test employee status breakdown report with weekly aggregation"""
        # Arrange: Create test data for 3 weeks
        week1_monday = date(2025, 10, 20)
        week2_monday = date(2025, 10, 27)
        week3_monday = date(2025, 11, 3)

        EmployeeStatusBreakdownReport.objects.create(
            report_date=week1_monday + timedelta(days=6),
            branch=self.branch,
            block=self.block,
            department=self.department,
            total_not_resigned=100,
        )

        EmployeeStatusBreakdownReport.objects.create(
            report_date=week2_monday + timedelta(days=6),
            branch=self.branch,
            block=self.block,
            department=self.department,
            total_not_resigned=105,
        )

        EmployeeStatusBreakdownReport.objects.create(
            report_date=week3_monday + timedelta(days=6),
            branch=self.branch,
            block=self.block,
            department=self.department,
            total_not_resigned=110,
        )

        # Act: Call the API
        url = reverse("hrm:employee-reports-employee-status-breakdown")
        response = self.client.get(
            url,
            {
                "period_type": "week",
                "from_date": week1_monday.isoformat(),
                "to_date": (week3_monday + timedelta(days=6)).isoformat(),
            },
        )

        # Assert: Verify response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        self.assertIn("time_headers", data)
        self.assertIn("data", data)

        # Should have 3 weeks + Average column
        self.assertEqual(len(data["time_headers"]), 4)
        self.assertIn("Average", data["time_headers"][-1])

        # Verify nested structure
        self.assertEqual(len(data["data"]), 1)
        branch_item = data["data"][0]
        self.assertEqual(branch_item["type"], "branch")
        self.assertEqual(branch_item["name"], "Hanoi Branch")

        # Verify statistics (3 weeks + average)
        self.assertEqual(len(branch_item["statistics"]), 4)
        self.assertEqual(branch_item["statistics"][0], 100)
        self.assertEqual(branch_item["statistics"][1], 105)
        self.assertEqual(branch_item["statistics"][2], 110)
        self.assertAlmostEqual(branch_item["statistics"][3], 105.00, places=2)

    def test_employee_resigned_breakdown_monthly(self):
        """Test employee resigned breakdown report with monthly aggregation"""
        # Arrange: Create test data for 2 months
        month1 = date(2025, 10, 31)
        month2 = date(2025, 11, 30)

        EmployeeStatusBreakdownReport.objects.create(
            report_date=month1,
            branch=self.branch,
            block=self.block,
            department=self.department,
            count_resigned=5,
        )

        EmployeeStatusBreakdownReport.objects.create(
            report_date=month2,
            branch=self.branch,
            block=self.block,
            department=self.department,
            count_resigned=8,
        )

        # Act: Call the API
        url = reverse("hrm:employee-reports-employee-resigned-breakdown")
        response = self.client.get(
            url,
            {
                "period_type": "month",
                "from_date": date(2025, 10, 1).isoformat(),
                "to_date": date(2025, 11, 30).isoformat(),
            },
        )

        # Assert: Verify response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        self.assertIn("time_headers", data)
        self.assertIn("data", data)

        # Should have 2 months + Average column
        self.assertEqual(len(data["time_headers"]), 3)

        # Verify branch statistics
        branch_item = data["data"][0]
        self.assertEqual(len(branch_item["statistics"]), 3)
        self.assertEqual(branch_item["statistics"][0], 5)
        self.assertEqual(branch_item["statistics"][1], 8)
        # Average of 5 and 8 should be 6.5
        # Check type and value
        avg_value = branch_item["statistics"][2]
        self.assertIsInstance(avg_value, float, f"Expected float but got {type(avg_value)}")
        self.assertAlmostEqual(avg_value, 6.50, places=2)

    def test_bucket_target_date_priority(self):
        """Test that target date (bucket_end) is prioritized over fallback"""
        # Arrange: Create report on target date and another date in bucket
        target_date = date(2025, 10, 31)
        other_date = date(2025, 10, 15)

        EmployeeStatusBreakdownReport.objects.create(
            report_date=other_date,
            branch=self.branch,
            block=self.block,
            department=self.department,
            total_not_resigned=50,
        )

        EmployeeStatusBreakdownReport.objects.create(
            report_date=target_date,
            branch=self.branch,
            block=self.block,
            department=self.department,
            total_not_resigned=100,
        )

        # Act: Call the API for October
        url = reverse("hrm:employee-reports-employee-status-breakdown")
        response = self.client.get(
            url,
            {
                "period_type": "month",
                "from_date": date(2025, 10, 1).isoformat(),
                "to_date": date(2025, 10, 31).isoformat(),
            },
        )

        # Assert: Should use target_date value (100), not other_date (50)
        data = self.get_response_data(response)
        branch_item = data["data"][0]
        self.assertEqual(branch_item["statistics"][0], 100)

    def test_bucket_fallback_to_latest_in_bucket(self):
        """Test fallback to latest record within bucket when target date missing"""
        # Arrange: Create reports but NOT on target date (month end)
        date1 = date(2025, 10, 10)
        date2 = date(2025, 10, 25)

        EmployeeStatusBreakdownReport.objects.create(
            report_date=date1,
            branch=self.branch,
            block=self.block,
            department=self.department,
            total_not_resigned=50,
        )

        EmployeeStatusBreakdownReport.objects.create(
            report_date=date2,
            branch=self.branch,
            block=self.block,
            department=self.department,
            total_not_resigned=75,
        )

        # Act: Call the API for October (target would be Oct 31)
        url = reverse("hrm:employee-reports-employee-status-breakdown")
        response = self.client.get(
            url,
            {
                "period_type": "month",
                "from_date": date(2025, 10, 1).isoformat(),
                "to_date": date(2025, 10, 31).isoformat(),
            },
        )

        # Assert: Should use latest date in bucket (Oct 25 value of 75)
        data = self.get_response_data(response)
        branch_item = data["data"][0]
        self.assertEqual(branch_item["statistics"][0], 75)

    def test_missing_bucket_returns_zero(self):
        """Test that missing buckets return 0"""
        # Arrange: Create report only for October
        EmployeeStatusBreakdownReport.objects.create(
            report_date=date(2025, 10, 31),
            branch=self.branch,
            block=self.block,
            department=self.department,
            total_not_resigned=100,
        )

        # Act: Call the API for Oct-Nov (Nov has no data)
        url = reverse("hrm:employee-reports-employee-status-breakdown")
        response = self.client.get(
            url,
            {
                "period_type": "month",
                "from_date": date(2025, 10, 1).isoformat(),
                "to_date": date(2025, 11, 30).isoformat(),
            },
        )

        # Assert: October should have 100, November should have 0
        data = self.get_response_data(response)
        branch_item = data["data"][0]
        self.assertEqual(len(branch_item["statistics"]), 3)
        self.assertEqual(branch_item["statistics"][0], 100)
        self.assertEqual(branch_item["statistics"][1], 0)
        self.assertAlmostEqual(branch_item["statistics"][2], 50.00, places=2)

    def test_quarterly_aggregation(self):
        """Test quarterly aggregation"""
        # Arrange: Create data for Q4 2025 (Oct, Nov, Dec)
        EmployeeStatusBreakdownReport.objects.create(
            report_date=date(2025, 12, 31),
            branch=self.branch,
            block=self.block,
            department=self.department,
            count_resigned=12,
        )

        # Act: Call the API for Q4
        url = reverse("hrm:employee-reports-employee-resigned-breakdown")
        response = self.client.get(
            url,
            {
                "period_type": "quarter",
                "from_date": date(2025, 10, 1).isoformat(),
                "to_date": date(2025, 12, 31).isoformat(),
            },
        )

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data["time_headers"]), 2)
        self.assertIn("Quarter", data["time_headers"][0])

    def test_yearly_aggregation(self):
        """Test yearly aggregation"""
        # Arrange: Create data for 2025
        EmployeeStatusBreakdownReport.objects.create(
            report_date=date(2025, 12, 31),
            branch=self.branch,
            block=self.block,
            department=self.department,
            total_not_resigned=200,
        )

        # Act: Call the API for 2025
        url = reverse("hrm:employee-reports-employee-status-breakdown")
        response = self.client.get(
            url,
            {
                "period_type": "year",
                "from_date": date(2025, 1, 1).isoformat(),
                "to_date": date(2025, 12, 31).isoformat(),
            },
        )

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data["time_headers"]), 2)
        self.assertIn("Year", data["time_headers"][0])

    def test_missing_required_params(self):
        """Test that missing required parameters return validation error"""
        # Act: Call API without required params
        url = reverse("hrm:employee-reports-employee-status-breakdown")
        response = self.client.get(url, {"period_type": "week"})

        # Assert
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        content = json.loads(response.content.decode())
        self.assertFalse(content["success"])
        self.assertIsNotNone(content["error"])

    def test_response_envelope_format(self):
        """Test that response uses correct envelope format"""
        # Arrange
        EmployeeStatusBreakdownReport.objects.create(
            report_date=date(2025, 10, 31),
            branch=self.branch,
            block=self.block,
            department=self.department,
            total_not_resigned=100,
        )

        # Act
        url = reverse("hrm:employee-reports-employee-status-breakdown")
        response = self.client.get(
            url,
            {
                "period_type": "month",
                "from_date": date(2025, 10, 1).isoformat(),
                "to_date": date(2025, 10, 31).isoformat(),
            },
        )

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = json.loads(response.content.decode())
        self.assertIn("success", content)
        self.assertIn("data", content)
        self.assertIn("error", content)
        self.assertTrue(content["success"])
        self.assertIsNotNone(content["data"])

    def test_organizational_filters(self):
        """Test filtering by branch/block/department"""
        # Arrange: Create another branch/block/department
        branch2 = Branch.objects.create(
            name="HCMC Branch",
            province=self.province,
            administrative_unit=self.admin_unit,
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
            branch=self.branch,
            block=self.block,
            department=self.department,
            total_not_resigned=100,
        )

        EmployeeStatusBreakdownReport.objects.create(
            report_date=date(2025, 10, 31),
            branch=branch2,
            block=block2,
            department=dept2,
            total_not_resigned=50,
        )

        # Act: Filter by first branch
        url = reverse("hrm:employee-reports-employee-status-breakdown")
        response = self.client.get(
            url,
            {
                "period_type": "month",
                "from_date": date(2025, 10, 1).isoformat(),
                "to_date": date(2025, 10, 31).isoformat(),
                "branch": self.branch.id,
            },
        )

        # Assert: Should only have first branch
        data = self.get_response_data(response)
        self.assertEqual(len(data["data"]), 1)
        self.assertEqual(data["data"][0]["name"], "Hanoi Branch")
        self.assertEqual(data["data"][0]["statistics"][0], 100)
