"""Tests for Employee Resigned Reason Report model and API endpoints."""

import json
from datetime import date

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import Block, Branch, Department, Employee, EmployeeResignedReasonReport

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


class EmployeeResignedReasonReportModelTest(TransactionTestCase):
    """Test cases for EmployeeResignedReasonReport model"""

    def setUp(self):
        """Set up test data"""
        EmployeeResignedReasonReport.objects.all().delete()
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
        """Test creating report with all resignation reason fields"""
        # Arrange & Act
        report = EmployeeResignedReasonReport.objects.create(
            report_date=date(2025, 11, 1),
            branch=self.branch,
            block=self.block,
            department=self.department,
            count_resigned=10,
            agreement_termination=1,
            probation_fail=2,
            voluntary_career_change=3,
            voluntary_personal=2,
            contract_expired=1,
            other=1,
        )

        # Assert
        self.assertEqual(report.count_resigned, 10)
        self.assertEqual(report.agreement_termination, 1)
        self.assertEqual(report.probation_fail, 2)
        self.assertEqual(report.voluntary_career_change, 3)
        self.assertEqual(report.voluntary_personal, 2)
        self.assertEqual(report.contract_expired, 1)
        self.assertEqual(report.other, 1)
        # Check other fields default to 0
        self.assertEqual(report.job_abandonment, 0)
        self.assertEqual(report.disciplinary_termination, 0)

    def test_unique_constraint_on_date_and_org_units(self):
        """Test unique constraint prevents duplicate records for same date and organizational unit"""
        # Arrange
        EmployeeResignedReasonReport.objects.create(
            report_date=date(2025, 11, 1),
            branch=self.branch,
            block=self.block,
            department=self.department,
            count_resigned=5,
        )

        # Act & Assert
        with self.assertRaises(IntegrityError):
            EmployeeResignedReasonReport.objects.create(
                report_date=date(2025, 11, 1),
                branch=self.branch,
                block=self.block,
                department=self.department,
                count_resigned=3,
            )

    def test_different_dates_same_org_units_allowed(self):
        """Test that different dates with same org units are allowed"""
        # Arrange & Act
        report1 = EmployeeResignedReasonReport.objects.create(
            report_date=date(2025, 11, 1),
            branch=self.branch,
            block=self.block,
            department=self.department,
            count_resigned=5,
        )

        report2 = EmployeeResignedReasonReport.objects.create(
            report_date=date(2025, 11, 2),
            branch=self.branch,
            block=self.block,
            department=self.department,
            count_resigned=3,
        )

        # Assert
        self.assertEqual(EmployeeResignedReasonReport.objects.count(), 2)
        self.assertNotEqual(report1.id, report2.id)

    def test_default_values(self):
        """Test that all reason fields default to 0"""
        # Arrange & Act
        report = EmployeeResignedReasonReport.objects.create(
            report_date=date(2025, 11, 1),
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

        # Assert
        self.assertEqual(report.count_resigned, 0)
        self.assertEqual(report.agreement_termination, 0)
        self.assertEqual(report.probation_fail, 0)
        self.assertEqual(report.job_abandonment, 0)
        self.assertEqual(report.disciplinary_termination, 0)
        self.assertEqual(report.workforce_reduction, 0)
        self.assertEqual(report.underperforming, 0)
        self.assertEqual(report.contract_expired, 0)
        self.assertEqual(report.voluntary_health, 0)
        self.assertEqual(report.voluntary_personal, 0)
        self.assertEqual(report.voluntary_career_change, 0)
        self.assertEqual(report.voluntary_other, 0)
        self.assertEqual(report.other, 0)


class EmployeeResignedReasonSummaryAPITest(TransactionTestCase, APITestMixin):
    """Test cases for Employee Resigned Reason Summary API endpoint"""

    def setUp(self):
        """Set up test data"""
        EmployeeResignedReasonReport.objects.all().delete()
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

        # Create a user and authenticate
        # Changed to superuser to bypass RoleBasedPermission for API tests
        self.user = User.objects.create_superuser(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_aggregated_summary_with_multiple_records(self):
        """Test aggregated summary across multiple date records"""
        # Arrange: Create 3 records across different dates
        EmployeeResignedReasonReport.objects.create(
            report_date=date(2025, 1, 15),
            branch=self.branch,
            block=self.block,
            department=self.department,
            count_resigned=10,
            voluntary_career_change=5,
            voluntary_personal=3,
            probation_fail=2,
        )

        EmployeeResignedReasonReport.objects.create(
            report_date=date(2025, 2, 15),
            branch=self.branch,
            block=self.block,
            department=self.department,
            count_resigned=15,
            voluntary_career_change=8,
            voluntary_personal=4,
            contract_expired=3,
        )

        EmployeeResignedReasonReport.objects.create(
            report_date=date(2025, 3, 15),
            branch=self.branch,
            block=self.block,
            department=self.department,
            count_resigned=5,
            voluntary_health=2,
            other=3,
        )

        # Act: Call the API
        url = reverse("hrm:employee-reports-employee-resigned-reasons-summary")
        response = self.client.get(
            url,
            {
                "from_date": "2025-01-01",
                "to_date": "2025-03-31",
            },
        )

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        self.assertEqual(data["total_resigned"], 30)
        self.assertEqual(data["from_date"], "2025-01-01")
        self.assertEqual(data["to_date"], "2025-03-31")

        # Verify reasons are sorted by count descending
        reasons = data["reasons"]
        self.assertEqual(len(reasons), 6)  # Only non-zero reasons

        # Check voluntary_career_change (5+8 = 13)
        voluntary_career = next(r for r in reasons if r["code"] == Employee.ResignationReason.VOLUNTARY_CAREER_CHANGE)
        self.assertEqual(voluntary_career["count"], 13)
        self.assertAlmostEqual(float(voluntary_career["percentage"]), 43.33, places=2)

        # Check voluntary_personal (3+4 = 7)
        voluntary_personal = next(r for r in reasons if r["code"] == Employee.ResignationReason.VOLUNTARY_PERSONAL)
        self.assertEqual(voluntary_personal["count"], 7)
        self.assertAlmostEqual(float(voluntary_personal["percentage"]), 23.33, places=2)

        # Check contract_expired (3)
        contract_expired = next(r for r in reasons if r["code"] == Employee.ResignationReason.CONTRACT_EXPIRED)
        self.assertEqual(contract_expired["count"], 3)
        self.assertEqual(float(contract_expired["percentage"]), 10.0)

        # Verify sorting (descending by count)
        counts = [r["count"] for r in reasons]
        self.assertEqual(counts, sorted(counts, reverse=True))

    def test_filter_by_branch(self):
        """Test filtering by branch"""
        # Arrange: Create another branch
        branch2 = Branch.objects.create(
            name="Saigon Branch",
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

        # Create reports for both branches
        EmployeeResignedReasonReport.objects.create(
            report_date=date(2025, 1, 15),
            branch=self.branch,
            block=self.block,
            department=self.department,
            count_resigned=10,
            voluntary_career_change=10,
        )

        EmployeeResignedReasonReport.objects.create(
            report_date=date(2025, 1, 15),
            branch=branch2,
            block=block2,
            department=dept2,
            count_resigned=5,
            probation_fail=5,
        )

        # Act: Call API with branch filter
        url = reverse("hrm:employee-reports-employee-resigned-reasons-summary")
        response = self.client.get(
            url,
            {
                "from_date": "2025-01-01",
                "to_date": "2025-01-31",
                "branch": self.branch.id,
            },
        )

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        self.assertEqual(data["total_resigned"], 10)  # Only Hanoi branch
        self.assertEqual(data["filters"]["branch"], "Hanoi Branch")
        self.assertEqual(len(data["reasons"]), 1)
        self.assertEqual(data["reasons"][0]["code"], Employee.ResignationReason.VOLUNTARY_CAREER_CHANGE)

    def test_filter_by_block_type(self):
        """Test filtering by block type"""
        # Arrange: Create support block
        support_block = Block.objects.create(
            name="Support Block",
            branch=self.branch,
            block_type=Block.BlockType.SUPPORT,
        )
        support_dept = Department.objects.create(
            name="HR Department",
            branch=self.branch,
            block=support_block,
            function=Department.DepartmentFunction.HR_ADMIN,
        )

        # Create reports for both block types
        EmployeeResignedReasonReport.objects.create(
            report_date=date(2025, 1, 15),
            branch=self.branch,
            block=self.block,  # Business
            department=self.department,
            count_resigned=10,
            voluntary_career_change=10,
        )

        EmployeeResignedReasonReport.objects.create(
            report_date=date(2025, 1, 15),
            branch=self.branch,
            block=support_block,  # Support
            department=support_dept,
            count_resigned=3,
            probation_fail=3,
        )

        # Act: Filter by support block type
        url = reverse("hrm:employee-reports-employee-resigned-reasons-summary")
        response = self.client.get(
            url,
            {
                "from_date": "2025-01-01",
                "to_date": "2025-01-31",
                "block_type": "support",
            },
        )

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        self.assertEqual(data["total_resigned"], 3)  # Only support block
        self.assertEqual(data["filters"]["block_type"], "support")
        self.assertEqual(len(data["reasons"]), 1)
        self.assertEqual(data["reasons"][0]["code"], Employee.ResignationReason.PROBATION_FAIL)

    def test_default_date_range_when_no_params(self):
        """Test that default date range is used when no date params provided"""
        # Act: Call API without date parameters
        url = reverse("hrm:employee-reports-employee-resigned-reasons-summary")
        response = self.client.get(url)

        # Assert: Should use default date range (1st of current month to today)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        # Verify response structure
        self.assertIn("from_date", data)
        self.assertIn("to_date", data)
        self.assertIn("total_resigned", data)
        self.assertIn("reasons", data)

    def test_empty_result_when_no_data(self):
        """Test response when no data matches the filter"""
        # Act: Call API with date range that has no data
        url = reverse("hrm:employee-reports-employee-resigned-reasons-summary")
        response = self.client.get(
            url,
            {
                "from_date": "2025-01-01",
                "to_date": "2025-01-31",
            },
        )

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        self.assertEqual(data["total_resigned"], 0)
        self.assertEqual(len(data["reasons"]), 0)

    def test_only_non_zero_reasons_included(self):
        """Test that only reasons with count > 0 are included in response"""
        # Arrange
        EmployeeResignedReasonReport.objects.create(
            report_date=date(2025, 1, 15),
            branch=self.branch,
            block=self.block,
            department=self.department,
            count_resigned=5,
            voluntary_career_change=3,
            voluntary_personal=2,
            # All other reasons are 0
        )

        # Act
        url = reverse("hrm:employee-reports-employee-resigned-reasons-summary")
        response = self.client.get(
            url,
            {
                "from_date": "2025-01-01",
                "to_date": "2025-01-31",
            },
        )

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        # Only 2 reasons should be present
        self.assertEqual(len(data["reasons"]), 2)
        reason_codes = {r["code"] for r in data["reasons"]}
        self.assertIn(Employee.ResignationReason.VOLUNTARY_CAREER_CHANGE, reason_codes)
        self.assertIn(Employee.ResignationReason.VOLUNTARY_PERSONAL, reason_codes)

    def test_percentage_calculation_accuracy(self):
        """Test percentage calculations are accurate to 2 decimal places"""
        # Arrange
        EmployeeResignedReasonReport.objects.create(
            report_date=date(2025, 1, 15),
            branch=self.branch,
            block=self.block,
            department=self.department,
            count_resigned=127,
            voluntary_career_change=45,
            voluntary_personal=32,
            probation_fail=20,
            contract_expired=15,
            voluntary_health=10,
            other=5,
        )

        # Act
        url = reverse("hrm:employee-reports-employee-resigned-reasons-summary")
        response = self.client.get(
            url,
            {
                "from_date": "2025-01-01",
                "to_date": "2025-01-31",
            },
        )

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        # Check percentages
        voluntary_career = next(
            r for r in data["reasons"] if r["code"] == Employee.ResignationReason.VOLUNTARY_CAREER_CHANGE
        )
        self.assertAlmostEqual(float(voluntary_career["percentage"]), 35.43, places=2)

        voluntary_personal = next(
            r for r in data["reasons"] if r["code"] == Employee.ResignationReason.VOLUNTARY_PERSONAL
        )
        self.assertAlmostEqual(float(voluntary_personal["percentage"]), 25.20, places=2)

    def test_inactive_org_units_excluded(self):
        """Test that inactive organizational units are excluded"""
        # Arrange: Create inactive branch
        inactive_branch = Branch.objects.create(
            name="Inactive Branch",
            province=self.province,
            administrative_unit=self.admin_unit,
            is_active=False,
        )
        inactive_block = Block.objects.create(
            name="Inactive Block",
            branch=inactive_branch,
            block_type=Block.BlockType.BUSINESS,
            is_active=False,
        )
        inactive_dept = Department.objects.create(
            name="Inactive Department",
            branch=inactive_branch,
            block=inactive_block,
            function=Department.DepartmentFunction.BUSINESS,
            is_active=False,
        )

        # Create reports for active and inactive units
        EmployeeResignedReasonReport.objects.create(
            report_date=date(2025, 1, 15),
            branch=self.branch,  # Active
            block=self.block,
            department=self.department,
            count_resigned=10,
            voluntary_career_change=10,
        )

        EmployeeResignedReasonReport.objects.create(
            report_date=date(2025, 1, 15),
            branch=inactive_branch,  # Inactive
            block=inactive_block,
            department=inactive_dept,
            count_resigned=5,
            probation_fail=5,
        )

        # Act
        url = reverse("hrm:employee-reports-employee-resigned-reasons-summary")
        response = self.client.get(
            url,
            {
                "from_date": "2025-01-01",
                "to_date": "2025-01-31",
            },
        )

        # Assert: Only active branch data should be included
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        self.assertEqual(data["total_resigned"], 10)  # Only active branch
        self.assertEqual(len(data["reasons"]), 1)
        self.assertEqual(data["reasons"][0]["code"], Employee.ResignationReason.VOLUNTARY_CAREER_CHANGE)
