"""Tests for Department KPI Assessment leader synchronization."""

from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.payroll.models import (
    DepartmentKPIAssessment,
    EmployeeKPIAssessment,
    KPIAssessmentPeriod,
    KPIConfig,
)
from apps.payroll.utils import generate_department_assessments_for_period

User = get_user_model()


@pytest.mark.django_db
class TestDepartmentKPILeaderSync(TestCase):
    """Test cases for syncing leader's grade with department grade."""

    @pytest.fixture(autouse=True)
    def setup_fixtures(self, department, employee):
        self.department = department
        self.leader = employee

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            is_staff=True,
            is_superuser=True,
        )

        self.kpi_config = KPIConfig.objects.create(
            config={
                "grade_thresholds": [
                    {"min": 0, "max": 60, "possible_codes": ["D"]},
                ],
                "unit_control": {
                    "A": {"A": {"max": 0.20}, "B": {"max": 0.30}, "C": {"max": 0.50}, "D": {}},
                },
            }
        )

        self.period = KPIAssessmentPeriod.objects.create(
            month=date(2025, 12, 1),
            kpi_config_snapshot=self.kpi_config.config,
        )

        # Set leader for department
        self.department.leader = self.leader
        self.department.save()

    def test_generate_creates_leader_assessment(self):
        """Test that generating department assessment creates leader's employee assessment."""
        # Generate department assessments
        count = generate_department_assessments_for_period(
            period=self.period,
            department_ids=[self.department.id],
            skip_existing=False,
        )

        self.assertEqual(count, 1)

        # Verify department assessment exists with grade C
        dept_assessment = DepartmentKPIAssessment.objects.get(
            department=self.department,
            period=self.period,
        )
        self.assertEqual(dept_assessment.grade, "C")

        # Verify leader's employee assessment was created with grade_hrm=C and finalized=True
        leader_assessment = EmployeeKPIAssessment.objects.get(
            employee=self.leader,
            period=self.period,
        )
        self.assertEqual(leader_assessment.grade_hrm, "C")
        self.assertTrue(leader_assessment.finalized)

    def test_generate_updates_existing_leader_assessment(self):
        """Test that generating department assessment updates existing leader assessment."""
        # Create existing employee assessment
        existing_assessment = EmployeeKPIAssessment.objects.create(
            employee=self.leader,
            period=self.period,
            grade_hrm="B",
            finalized=False,
        )

        # Generate department assessments
        count = generate_department_assessments_for_period(
            period=self.period,
            department_ids=[self.department.id],
            skip_existing=False,
        )

        self.assertEqual(count, 1)

        # Verify leader's assessment was updated
        existing_assessment.refresh_from_db()
        self.assertEqual(existing_assessment.grade_hrm, "C")
        self.assertTrue(existing_assessment.finalized)

    def test_generate_without_leader_no_error(self):
        """Test that generating department assessment without leader doesn't cause error."""
        # Remove leader
        self.department.leader = None
        self.department.save()

        # Generate department assessments - should not raise error
        count = generate_department_assessments_for_period(
            period=self.period,
            department_ids=[self.department.id],
            skip_existing=False,
        )

        self.assertEqual(count, 1)

        # Verify no employee assessment was created
        self.assertFalse(
            EmployeeKPIAssessment.objects.filter(
                employee=self.leader,
                period=self.period,
            ).exists()
        )


@pytest.mark.django_db
class TestDepartmentKPIGradeUpdateSync(TestCase):
    """Test cases for syncing leader's grade when department grade is updated via API."""

    @pytest.fixture(autouse=True)
    def setup_fixtures(self, department, employee):
        self.department = department
        self.leader = employee

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
            }
        )

        self.period = KPIAssessmentPeriod.objects.create(
            month=date(2025, 12, 1),
            kpi_config_snapshot=kpi_config.config,
        )

        # Set leader for department
        self.department.leader = self.leader
        self.department.save()

        # Create department assessment
        self.dept_assessment = DepartmentKPIAssessment.objects.create(
            period=self.period,
            department=self.department,
            grade="C",
        )

        # Create leader's employee assessment
        self.leader_assessment = EmployeeKPIAssessment.objects.create(
            employee=self.leader,
            period=self.period,
            grade_hrm="C",
            finalized=True,
        )

    def test_update_department_grade_syncs_leader_grade(self):
        """Test that updating department grade updates leader's grade_hrm."""
        data = {"grade": "A"}

        response = self.client.patch(
            f"/api/payroll/kpi-assessments/departments/{self.dept_assessment.id}/",
            data,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify department grade updated
        self.dept_assessment.refresh_from_db()
        self.assertEqual(self.dept_assessment.grade, "A")

        # Verify leader's grade_hrm was synced
        self.leader_assessment.refresh_from_db()
        self.assertEqual(self.leader_assessment.grade_hrm, "A")

    def test_update_department_note_doesnt_affect_leader(self):
        """Test that updating only note doesn't change leader's grade."""
        original_grade = self.leader_assessment.grade_hrm
        data = {"note": "Updated note"}

        response = self.client.patch(
            f"/api/payroll/kpi-assessments/departments/{self.dept_assessment.id}/",
            data,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify leader's grade unchanged
        self.leader_assessment.refresh_from_db()
        self.assertEqual(self.leader_assessment.grade_hrm, original_grade)

    def test_update_without_leader_no_error(self):
        """Test that updating department without leader doesn't cause error."""
        # Remove leader
        self.department.leader = None
        self.department.save()

        data = {"grade": "B"}

        response = self.client.patch(
            f"/api/payroll/kpi-assessments/departments/{self.dept_assessment.id}/",
            data,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify department grade updated
        self.dept_assessment.refresh_from_db()
        self.assertEqual(self.dept_assessment.grade, "B")

    def test_update_leader_without_assessment_no_error(self):
        """Test that updating department when leader has no assessment doesn't cause error."""
        # Delete leader's assessment
        self.leader_assessment.delete()

        data = {"grade": "B"}

        response = self.client.patch(
            f"/api/payroll/kpi-assessments/departments/{self.dept_assessment.id}/",
            data,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify department grade updated
        self.dept_assessment.refresh_from_db()
        self.assertEqual(self.dept_assessment.grade, "B")
