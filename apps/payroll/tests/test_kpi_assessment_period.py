"""Tests for KPIAssessmentPeriod model and API."""

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.hrm.models import Department, Employee
from apps.payroll.models import (
    DepartmentKPIAssessment,
    EmployeeKPIAssessment,
    KPIAssessmentPeriod,
    KPIConfig,
)

User = get_user_model()


@pytest.mark.django_db
class KPIAssessmentPeriodModelTest(TestCase):
    """Test cases for KPIAssessmentPeriod model."""

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
                    {"min": 60, "max": 80, "possible_codes": ["C"]},
                    {"min": 80, "max": 100, "possible_codes": ["B"]},
                ],
            }
        )

    def test_create_period(self):
        """Test creating a KPI assessment period."""
        period = KPIAssessmentPeriod.objects.create(
            month=date(2025, 12, 1),
            kpi_config_snapshot=self.kpi_config.config,
            created_by=self.user,
        )

        self.assertIsNotNone(period.id)
        self.assertEqual(period.month, date(2025, 12, 1))
        self.assertEqual(period.kpi_config_snapshot, self.kpi_config.config)
        self.assertFalse(period.finalized)

    def test_unique_month(self):
        """Test that month must be unique."""
        KPIAssessmentPeriod.objects.create(
            month=date(2025, 12, 1),
            kpi_config_snapshot=self.kpi_config.config,
        )

        with self.assertRaises(Exception):
            KPIAssessmentPeriod.objects.create(
                month=date(2025, 12, 1),
                kpi_config_snapshot=self.kpi_config.config,
            )

    def test_str_representation(self):
        """Test string representation."""
        period = KPIAssessmentPeriod.objects.create(
            month=date(2025, 12, 1),
            kpi_config_snapshot=self.kpi_config.config,
        )

        expected = "KPI Period 2025-12 - Open"
        self.assertEqual(str(period), expected)

    def test_str_representation_finalized(self):
        """Test string representation for finalized period."""
        period = KPIAssessmentPeriod.objects.create(
            month=date(2025, 12, 1),
            kpi_config_snapshot=self.kpi_config.config,
            finalized=True,
        )

        expected = "KPI Period 2025-12 - Finalized"
        self.assertEqual(str(period), expected)


@pytest.mark.django_db
class KPIAssessmentPeriodAPITest(TestCase):
    """Test cases for KPIAssessmentPeriod API."""

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

    def test_list_periods(self):
        """Test listing KPI assessment periods."""
        response = self.client.get("/api/payroll/kpi-periods/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.get_response_data(response)["success"], True)
        self.assertGreater(self.get_response_data(response)["data"]["count"], 0)

    def test_retrieve_period(self):
        """Test retrieving a specific period."""
        response = self.client.get(f"/api/payroll/kpi-periods/{self.period.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.get_response_data(response)["success"], True)
        self.assertEqual(self.get_response_data(response)["data"]["id"], self.period.id)

    def test_generate_period(self):
        """Test generating assessments for a new period."""
        # Use a past month that's definitely not in the future
        data = {"month": "2024-01"}

        response = self.client.post("/api/payroll/kpi-periods/generate/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.get_response_data(response)["success"], True)
        self.assertIn("period_id", self.get_response_data(response)["data"])

    def test_generate_period_future_month_rejected(self):
        """Test that future months are rejected."""
        from datetime import date

        today = date.today()
        # Calculate a future month (2 months from now)
        future_year = today.year if today.month < 11 else today.year + 1
        future_month = (today.month + 2) if today.month < 11 else (today.month + 2 - 12)
        future_month_str = f"{future_year}-{future_month:02d}"

        data = {"month": future_month_str}

        response = self.client.post("/api/payroll/kpi-periods/generate/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["success"], False)
        # Error can be in response_data["error"] or response_data["error"]["detail"]
        error_message = (
            response_data["error"]["detail"] if isinstance(response_data["error"], dict) else response_data["error"]
        )
        self.assertIn("Cannot create assessment period for future months", error_message)

    def test_generate_period_current_month_allowed(self):
        """Test that current month is allowed."""
        from datetime import date

        today = date.today()
        current_month_str = f"{today.year}-{today.month:02d}"

        data = {"month": current_month_str}

        response = self.client.post("/api/payroll/kpi-periods/generate/", data, format="json")

        # Should succeed (201) or fail because period already exists (400)
        # Either is acceptable for this test
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])

        if response.status_code == status.HTTP_400_BAD_REQUEST:
            # If it fails, it should be because period exists, not because it's future
            response_data = self.get_response_data(response)
            error_message = (
                response_data["error"]["detail"]
                if isinstance(response_data["error"], dict)
                else response_data["error"]
            )
            self.assertNotIn("future", error_message.lower())

    def test_generate_period_past_month_allowed(self):
        """Test that past months are allowed."""
        data = {"month": "2023-06"}

        response = self.client.post("/api/payroll/kpi-periods/generate/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.get_response_data(response)["success"], True)
        self.assertIn("period_id", self.get_response_data(response)["data"])

    def test_finalize_period(self):
        """Test finalizing a period."""
        response = self.client.post(f"/api/payroll/kpi-periods/{self.period.id}/finalize/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify period is finalized
        self.period.refresh_from_db()
        self.assertTrue(self.period.finalized)


@pytest.mark.django_db
class KPIAssessmentPeriodStatisticsTest(TestCase):
    """Test cases for KPI assessment period statistics fields."""

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

        # Create KPI config
        self.kpi_config = KPIConfig.objects.create(
            config={
                "grade_thresholds": [
                    {"min": 0, "max": 60, "possible_codes": ["D"]},
                    {"min": 60, "max": 80, "possible_codes": ["C"]},
                    {"min": 80, "max": 100, "possible_codes": ["B", "A"]},
                ],
            }
        )

        # Create assessment period
        self.period = KPIAssessmentPeriod.objects.create(
            month=date(2025, 12, 1),
            kpi_config_snapshot=self.kpi_config.config,
        )

        # Create organizational structure
        from apps.core.models import AdministrativeUnit, Province

        self.province = Province.objects.create(name="Test Province", code="TP")
        self.admin_unit = AdministrativeUnit.objects.create(
            parent_province=self.province,
            name="Test District",
            code="TD",
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )
        from apps.hrm.models import Block, Branch

        self.branch = Branch.objects.create(
            name="Test Branch",
            code="TB",
            province=self.province,
            administrative_unit=self.admin_unit,
        )
        self.block = Block.objects.create(
            name="Test Block",
            code="TBL",
            branch=self.branch,
            block_type=Block.BlockType.BUSINESS,
        )

        # Create departments
        self.dept1 = Department.objects.create(
            name="Sales Department", code="SALES", branch=self.branch, block=self.block
        )
        self.dept2 = Department.objects.create(name="IT Department", code="IT", branch=self.branch, block=self.block)

        # Create employees
        self.emp1 = Employee.objects.create(
            username="emp1",
            email="emp1@example.com",
            phone="0901234561",
            citizen_id="001234567891",
            code="EMP001",
            branch=self.branch,
            block=self.block,
            department=self.dept1,
            start_date=date(2025, 1, 1),
        )
        self.emp2 = Employee.objects.create(
            username="emp2",
            email="emp2@example.com",
            phone="0901234562",
            citizen_id="001234567892",
            code="EMP002",
            branch=self.branch,
            block=self.block,
            department=self.dept1,
            start_date=date(2025, 1, 1),
        )
        self.emp3 = Employee.objects.create(
            username="emp3",
            email="emp3@example.com",
            phone="0901234563",
            citizen_id="001234567893",
            code="EMP003",
            branch=self.branch,
            block=self.block,
            department=self.dept2,
            start_date=date(2025, 1, 1),
        )
        self.emp4 = Employee.objects.create(
            username="emp4",
            email="emp4@example.com",
            phone="0901234564",
            citizen_id="001234567894",
            code="EMP004",
            branch=self.branch,
            block=self.block,
            department=self.dept2,
            start_date=date(2025, 1, 1),
        )

        # Create department assessments
        DepartmentKPIAssessment.objects.create(
            period=self.period,
            department=self.dept1,
            grade="B",
        )
        DepartmentKPIAssessment.objects.create(
            period=self.period,
            department=self.dept2,
            grade="A",
        )

    def test_employee_count_statistic(self):
        """Test employee_count field shows total employee assessments."""
        # Create employee assessments
        EmployeeKPIAssessment.objects.create(
            period=self.period,
            employee=self.emp1,
            total_possible_score=Decimal("100.00"),
        )
        EmployeeKPIAssessment.objects.create(
            period=self.period,
            employee=self.emp2,
            total_possible_score=Decimal("100.00"),
        )
        EmployeeKPIAssessment.objects.create(
            period=self.period,
            employee=self.emp3,
            total_possible_score=Decimal("100.00"),
        )

        response = self.client.get("/api/payroll/kpi-periods/")
        data = self.get_response_data(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = data["data"]["results"][0]
        self.assertEqual(result["employee_count"], 3)

    def test_department_count_statistic(self):
        """Test department_count field shows total department assessments."""
        response = self.client.get("/api/payroll/kpi-periods/")
        data = self.get_response_data(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = data["data"]["results"][0]
        self.assertEqual(result["department_count"], 2)

    def test_employee_self_assessed_count(self):
        """Test employee_self_assessed_count shows employees who completed self-evaluation."""
        # Create 4 employee assessments, only 2 with self-evaluation
        EmployeeKPIAssessment.objects.create(
            period=self.period,
            employee=self.emp1,
            total_possible_score=Decimal("100.00"),
            total_employee_score=Decimal("85.00"),  # Self-evaluated
        )
        EmployeeKPIAssessment.objects.create(
            period=self.period,
            employee=self.emp2,
            total_possible_score=Decimal("100.00"),
            total_employee_score=Decimal("90.00"),  # Self-evaluated
        )
        EmployeeKPIAssessment.objects.create(
            period=self.period,
            employee=self.emp3,
            total_possible_score=Decimal("100.00"),
            # No self-evaluation
        )
        EmployeeKPIAssessment.objects.create(
            period=self.period,
            employee=self.emp4,
            total_possible_score=Decimal("100.00"),
            # No self-evaluation
        )

        response = self.client.get("/api/payroll/kpi-periods/")
        data = self.get_response_data(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = data["data"]["results"][0]
        self.assertEqual(result["employee_count"], 4)
        self.assertEqual(result["employee_self_assessed_count"], 2)

    def test_manager_assessed_count_with_score(self):
        """Test manager_assessed_count counts assessments with manager score."""
        # Create assessments with different manager evaluation states
        EmployeeKPIAssessment.objects.create(
            period=self.period,
            employee=self.emp1,
            total_possible_score=Decimal("100.00"),
            total_manager_score=Decimal("80.00"),  # Manager evaluated with score
        )
        EmployeeKPIAssessment.objects.create(
            period=self.period,
            employee=self.emp2,
            total_possible_score=Decimal("100.00"),
            # No manager evaluation
        )
        EmployeeKPIAssessment.objects.create(
            period=self.period,
            employee=self.emp3,
            total_possible_score=Decimal("100.00"),
            grade_manager="B",  # Manager evaluated with grade
        )
        EmployeeKPIAssessment.objects.create(
            period=self.period,
            employee=self.emp4,
            total_possible_score=Decimal("100.00"),
            # No manager evaluation
        )

        response = self.client.get("/api/payroll/kpi-periods/")
        data = self.get_response_data(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = data["data"]["results"][0]
        self.assertEqual(result["employee_count"], 4)
        self.assertEqual(result["manager_assessed_count"], 2)

    def test_manager_assessed_count_with_grade(self):
        """Test manager_assessed_count counts assessments with manager grade."""
        # Create assessments with grade_manager only
        EmployeeKPIAssessment.objects.create(
            period=self.period,
            employee=self.emp1,
            total_possible_score=Decimal("100.00"),
            grade_manager="A",
        )
        EmployeeKPIAssessment.objects.create(
            period=self.period,
            employee=self.emp2,
            total_possible_score=Decimal("100.00"),
            grade_manager="B",
        )

        response = self.client.get("/api/payroll/kpi-periods/")
        data = self.get_response_data(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = data["data"]["results"][0]
        self.assertEqual(result["manager_assessed_count"], 2)

    def test_all_statistics_together(self):
        """Test all statistics fields together in a realistic scenario."""
        # Create 6 employee assessments with different states
        # Employee 1: Both self and manager evaluated
        EmployeeKPIAssessment.objects.create(
            period=self.period,
            employee=self.emp1,
            total_possible_score=Decimal("100.00"),
            total_employee_score=Decimal("85.00"),
            total_manager_score=Decimal("80.00"),
        )
        # Employee 2: Only self evaluated
        EmployeeKPIAssessment.objects.create(
            period=self.period,
            employee=self.emp2,
            total_possible_score=Decimal("100.00"),
            total_employee_score=Decimal("90.00"),
        )
        # Employee 3: Only manager evaluated
        EmployeeKPIAssessment.objects.create(
            period=self.period,
            employee=self.emp3,
            total_possible_score=Decimal("100.00"),
            grade_manager="B",
        )
        # Employee 4: Not evaluated
        EmployeeKPIAssessment.objects.create(
            period=self.period,
            employee=self.emp4,
            total_possible_score=Decimal("100.00"),
        )

        response = self.client.get("/api/payroll/kpi-periods/")
        data = self.get_response_data(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = data["data"]["results"][0]

        # Verify all statistics
        self.assertEqual(result["employee_count"], 4)
        self.assertEqual(result["department_count"], 2)
        self.assertEqual(result["employee_self_assessed_count"], 2)  # emp1, emp2
        self.assertEqual(result["manager_assessed_count"], 2)  # emp1, emp3

    def test_statistics_with_empty_period(self):
        """Test statistics return 0 for period with no assessments."""
        # Create a new empty period
        empty_period = KPIAssessmentPeriod.objects.create(
            month=date(2026, 1, 1),
            kpi_config_snapshot=self.kpi_config.config,
        )

        response = self.client.get("/api/payroll/kpi-periods/")
        data = self.get_response_data(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Find the empty period in results
        empty_result = None
        for result in data["data"]["results"]:
            if result["id"] == empty_period.id:
                empty_result = result
                break

        self.assertIsNotNone(empty_result)
        self.assertEqual(empty_result["employee_count"], 0)
        self.assertEqual(empty_result["department_count"], 0)
        self.assertEqual(empty_result["employee_self_assessed_count"], 0)
        self.assertEqual(empty_result["manager_assessed_count"], 0)

    def test_statistics_fields_present_in_response(self):
        """Test that all new statistics fields are present in API response."""
        response = self.client.get("/api/payroll/kpi-periods/")
        data = self.get_response_data(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = data["data"]["results"][0]

        # Verify all expected fields are present
        expected_fields = [
            "id",
            "month",
            "kpi_config_snapshot",
            "finalized",
            "employee_count",
            "department_count",
            "employee_self_assessed_count",
            "manager_assessed_count",
            "note",
            "created_at",
            "updated_at",
        ]

        for field in expected_fields:
            self.assertIn(field, result, f"Field '{field}' should be in response")
