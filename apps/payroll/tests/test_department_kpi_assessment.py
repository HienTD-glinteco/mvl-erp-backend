"""Tests for DepartmentKPIAssessment model and API."""

from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.hrm.models import Department
from apps.payroll.models import (
    DepartmentKPIAssessment,
    KPIAssessmentPeriod,
    KPIConfig,
)

User = get_user_model()


@pytest.mark.django_db
class DepartmentKPIAssessmentModelTest(TestCase):
    """Test cases for DepartmentKPIAssessment model."""

    @pytest.fixture(autouse=True)
    def setup_fixtures(self, department):
        self.department = department

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        self.kpi_config = KPIConfig.objects.create(
            config={
                "grade_thresholds": [
                    {"min": 0, "max": 60, "possible_codes": ["D"]},
                ],
                "unit_control": {
                    "A": {"A": {"max": 0.20}, "B": {"max": 0.30}, "C": {"max": 0.50}, "D": {}},
                    "B": {"A": {"max": 0.10}, "B": {"max": 0.30}, "C": {"max": 0.50}, "D": {"min": 0.10}},
                    "C": {"A": {"max": 0.05}, "B": {"max": 0.20}, "C": {"max": 0.60}, "D": {"min": 0.15}},
                    "D": {"A": {"max": 0.05}, "B": {"max": 0.10}, "C": {"max": 0.65}, "D": {"min": 0.20}},
                },
            }
        )

        self.period = KPIAssessmentPeriod.objects.create(
            month=date(2025, 12, 1),
            kpi_config_snapshot=self.kpi_config.config,
        )

    def test_create_department_assessment(self):
        """Test creating a department KPI assessment."""
        assessment = DepartmentKPIAssessment.objects.create(
            period=self.period,
            department=self.department,
            grade="B",
            created_by=self.user,
        )

        self.assertIsNotNone(assessment.id)
        self.assertEqual(assessment.period, self.period)
        self.assertEqual(assessment.department, self.department)
        self.assertEqual(assessment.grade, "B")
        self.assertEqual(assessment.default_grade, "C")
        self.assertFalse(assessment.finalized)

    def test_unique_department_period(self):
        """Test that department+period combination is unique."""
        DepartmentKPIAssessment.objects.create(
            period=self.period,
            department=self.department,
            grade="B",
        )

        with self.assertRaises(Exception):
            DepartmentKPIAssessment.objects.create(
                period=self.period,
                department=self.department,
                grade="C",
            )

    def test_str_representation(self):
        """Test string representation."""
        assessment = DepartmentKPIAssessment.objects.create(
            period=self.period,
            department=self.department,
            grade="A",
        )

        # String format: "{department.name} - {period.month:%Y-%m} - Grade: {grade}"
        expected = f"{self.department.name} - 2025-12 - Grade: A"
        self.assertEqual(str(assessment), expected)


@pytest.mark.django_db
class DepartmentKPIAssessmentAPITest(TestCase):
    """Test cases for DepartmentKPIAssessment API."""

    @pytest.fixture(autouse=True)
    def setup_fixtures(self, department):
        self.department = department

    def get_response_data(self, response):
        """Extract data from wrapped API response."""
        import json

        content = json.loads(response.content.decode())
        return content

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_authenticate(user=self.user)

        kpi_config = KPIConfig.objects.create(
            config={
                "grade_thresholds": [
                    {"min": 0, "max": 60, "possible_codes": ["D"]},
                ],
                "unit_control": {
                    "A": {"A": {"max": 0.20}, "B": {"max": 0.30}, "C": {"max": 0.50}, "D": {}},
                    "B": {"A": {"max": 0.10}, "B": {"max": 0.30}, "C": {"max": 0.50}, "D": {"min": 0.10}},
                    "C": {"A": {"max": 0.05}, "B": {"max": 0.20}, "C": {"max": 0.60}, "D": {"min": 0.15}},
                    "D": {"A": {"max": 0.05}, "B": {"max": 0.10}, "C": {"max": 0.65}, "D": {"min": 0.20}},
                },
            }
        )

        self.period = KPIAssessmentPeriod.objects.create(
            month=date(2025, 12, 1),
            kpi_config_snapshot=kpi_config.config,
        )

        self.assessment = DepartmentKPIAssessment.objects.create(
            period=self.period,
            department=self.department,
            grade="C",
        )

    def test_list_assessments(self):
        """Test listing department KPI assessments."""
        response = self.client.get("/api/payroll/kpi-assessments/departments/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.get_response_data(response)["success"], True)
        self.assertGreater(self.get_response_data(response)["data"]["count"], 0)

    def test_retrieve_assessment(self):
        """Test retrieving a specific assessment."""
        response = self.client.get(f"/api/payroll/kpi-assessments/departments/{self.assessment.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.get_response_data(response)["success"], True)
        self.assertEqual(self.get_response_data(response)["data"]["id"], self.assessment.id)

    def test_update_assessment(self):
        """Test updating an assessment."""
        data = {
            "grade": "A",
            "note": "Excellent performance",
        }

        response = self.client.patch(
            f"/api/payroll/kpi-assessments/departments/{self.assessment.id}/", data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.get_response_data(response)["success"], True)

        self.assessment.refresh_from_db()
        self.assertEqual(self.assessment.grade, "A")
        self.assertEqual(self.assessment.note, "Excellent performance")

    def test_generate_assessments(self):
        """Test generating department assessments through period generation."""
        # Create another department using same branch and block
        dept2 = Department.objects.create(
            name="HR Department",
            code="HRDEPT",
            branch=self.department.branch,
            block=self.department.block,
            is_active=True,
        )

        # Department assessments are generated when generating a period
        response = self.client.post(
            "/api/payroll/kpi-periods/generate/",
            {"month": "2024-01"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)
        self.assertIn("department_assessments_created", response_data["data"])
        self.assertGreater(response_data["data"]["department_assessments_created"], 0)

    def test_finalize_assessment(self):
        """Test that department assessments are finalized through period finalization."""
        # Department assessments don't have individual finalize action
        # They are finalized when the period is finalized
        response = self.client.post(f"/api/payroll/kpi-periods/{self.period.id}/finalize/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify the period and its assessments are finalized
        self.assessment.refresh_from_db()
        self.period.refresh_from_db()
        self.assertTrue(self.period.finalized)


@pytest.mark.django_db
class DepartmentKPIAssessmentFilterTest(TestCase):
    """Test cases for DepartmentKPIAssessment filters."""

    def get_response_data(self, response):
        """Extract data from wrapped API response."""
        import json

        content = json.loads(response.content.decode())
        return content

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_authenticate(user=self.user)

        # Create organizational structure
        from apps.core.models import AdministrativeUnit, Province
        from apps.hrm.models import Block, Branch

        # Province and admin unit
        self.province = Province.objects.create(name="Test Province", code="TP")
        self.admin_unit = AdministrativeUnit.objects.create(
            parent_province=self.province,
            name="Test District",
            code="TD",
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )

        # Two branches
        self.branch1 = Branch.objects.create(
            name="Branch 1",
            code="BR1",
            province=self.province,
            administrative_unit=self.admin_unit,
        )
        self.branch2 = Branch.objects.create(
            name="Branch 2",
            code="BR2",
            province=self.province,
            administrative_unit=self.admin_unit,
        )

        # Two blocks per branch
        self.block1_br1 = Block.objects.create(
            name="Block 1 - Branch 1",
            code="BL1BR1",
            branch=self.branch1,
            block_type=Block.BlockType.BUSINESS,
        )
        self.block2_br1 = Block.objects.create(
            name="Block 2 - Branch 1",
            code="BL2BR1",
            branch=self.branch1,
            block_type=Block.BlockType.SUPPORT,
        )
        self.block1_br2 = Block.objects.create(
            name="Block 1 - Branch 2",
            code="BL1BR2",
            branch=self.branch2,
            block_type=Block.BlockType.BUSINESS,
        )

        # Departments in different branches/blocks
        self.dept1_bl1_br1 = Department.objects.create(
            name="Sales Dept - Block 1 - Branch 1",
            code="SALES1",
            branch=self.branch1,
            block=self.block1_br1,
        )
        self.dept2_bl2_br1 = Department.objects.create(
            name="HR Dept - Block 2 - Branch 1",
            code="HR1",
            branch=self.branch1,
            block=self.block2_br1,
        )
        self.dept3_bl1_br2 = Department.objects.create(
            name="IT Dept - Block 1 - Branch 2",
            code="IT2",
            branch=self.branch2,
            block=self.block1_br2,
        )

        # KPI config and period
        self.kpi_config = KPIConfig.objects.create(
            config={
                "grade_thresholds": [
                    {"min": 0, "max": 60, "possible_codes": ["D"]},
                ],
            }
        )

        self.period = KPIAssessmentPeriod.objects.create(
            month=date(2025, 12, 1),
            kpi_config_snapshot=self.kpi_config.config,
        )

        # Create assessments for all departments
        self.assessment1 = DepartmentKPIAssessment.objects.create(
            period=self.period,
            department=self.dept1_bl1_br1,
            grade="A",
        )
        self.assessment2 = DepartmentKPIAssessment.objects.create(
            period=self.period,
            department=self.dept2_bl2_br1,
            grade="B",
        )
        self.assessment3 = DepartmentKPIAssessment.objects.create(
            period=self.period,
            department=self.dept3_bl1_br2,
            grade="C",
        )

    def test_filter_by_branch(self):
        """Test filtering by branch ID."""
        # Filter by branch 1 - should return 2 assessments
        response = self.client.get(f"/api/payroll/kpi-assessments/departments/?branch={self.branch1.id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(data["data"]["count"], 2)

        # Verify both are from branch 1
        for result in data["data"]["results"]:
            dept_id = result["department"]["id"]
            self.assertIn(dept_id, [self.dept1_bl1_br1.id, self.dept2_bl2_br1.id])

    def test_filter_by_branch2(self):
        """Test filtering by branch 2 ID."""
        # Filter by branch 2 - should return 1 assessment
        response = self.client.get(f"/api/payroll/kpi-assessments/departments/?branch={self.branch2.id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(data["data"]["count"], 1)
        self.assertEqual(data["data"]["results"][0]["department"]["id"], self.dept3_bl1_br2.id)

    def test_filter_by_block(self):
        """Test filtering by block ID."""
        # Filter by block 1 in branch 1 - should return 1 assessment
        response = self.client.get(f"/api/payroll/kpi-assessments/departments/?block={self.block1_br1.id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(data["data"]["count"], 1)
        self.assertEqual(data["data"]["results"][0]["department"]["id"], self.dept1_bl1_br1.id)

    def test_filter_by_branch_and_block(self):
        """Test filtering by both branch and block."""
        # Filter by branch 1 and block 2 - should return 1 assessment
        response = self.client.get(
            f"/api/payroll/kpi-assessments/departments/?branch={self.branch1.id}&block={self.block2_br1.id}"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(data["data"]["count"], 1)
        self.assertEqual(data["data"]["results"][0]["department"]["id"], self.dept2_bl2_br1.id)

    def test_filter_by_branch_and_grade(self):
        """Test combining branch filter with grade filter."""
        # Filter by branch 1 and grade A
        response = self.client.get(f"/api/payroll/kpi-assessments/departments/?branch={self.branch1.id}&grade=A")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(data["data"]["count"], 1)
        self.assertEqual(data["data"]["results"][0]["department"]["id"], self.dept1_bl1_br1.id)
        self.assertEqual(data["data"]["results"][0]["grade"], "A")

    def test_filter_by_nonexistent_branch(self):
        """Test filtering by non-existent branch returns empty."""
        response = self.client.get("/api/payroll/kpi-assessments/departments/?branch=99999")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(data["data"]["count"], 0)

    def test_filter_by_nonexistent_block(self):
        """Test filtering by non-existent block returns empty."""
        response = self.client.get("/api/payroll/kpi-assessments/departments/?block=99999")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(data["data"]["count"], 0)
