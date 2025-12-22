"""Tests for new KPI assessment features.

This module tests:
- Employee self-assessment batch update
- Manager field in EmployeeKPIAssessment
- Manager assessment views and batch update
- HRM update restrictions (only grade_hrm and note)
"""

import random
import string
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status

from apps.hrm.models import Employee
from apps.payroll.models import (
    EmployeeKPIAssessment,
    KPIAssessmentPeriod,
    KPIConfig,
    KPICriterion,
)

User = get_user_model()


def random_code(prefix="", length=6):
    """Generate a random code."""
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=length))
    return f"{prefix}{suffix}"


@pytest.fixture
def kpi_config():
    """Create KPI config."""
    return KPIConfig.objects.create(
        config={
            "grade_thresholds": [
                {"min": 0, "max": 60, "possible_codes": ["D"], "label": "Poor"},
                {"min": 60, "max": 70, "possible_codes": ["C"], "label": "Average"},
                {"min": 70, "max": 90, "possible_codes": ["B"], "label": "Good"},
                {"min": 90, "max": 110, "possible_codes": ["A"], "label": "Excellent"},
            ],
            "ambiguous_assignment": "manual",
        }
    )


@pytest.fixture
def assessment_period(kpi_config):
    """Create assessment period."""
    return KPIAssessmentPeriod.objects.create(
        month=date(2025, 12, 1),
        kpi_config_snapshot=kpi_config.config,
    )


@pytest.fixture
def kpi_criteria():
    """Create test KPI criteria."""
    criterion1 = KPICriterion.objects.create(
        target="sales",
        evaluation_type="work_performance",
        criterion="Revenue Achievement",
        component_total_score=Decimal("70.00"),
        group_number=1,
        order=1,
        active=True,
    )
    criterion2 = KPICriterion.objects.create(
        target="sales",
        evaluation_type="discipline",
        criterion="Attendance",
        component_total_score=Decimal("30.00"),
        group_number=2,
        order=2,
        active=True,
    )
    return [criterion1, criterion2]


@pytest.fixture
def manager_employee(department):
    """Create manager employee."""
    code = random_code()
    manager = Employee.objects.create(
        username=f"manager{code}",
        email=f"manager{code}@example.com",
        phone=f"091{random_code(length=7)}",
        citizen_id=random_code(length=12),
        department=department,
        branch=department.branch,
        block=department.block,
        status=Employee.Status.ACTIVE,
        start_date=date.today(),
    )
    return manager


@pytest.fixture
def employee_with_manager(department, manager_employee):
    """Create employee with manager."""
    code = random_code()

    # Set manager as department leader
    department.leader = manager_employee
    department.save()

    employee = Employee.objects.create(
        username=f"employee{code}",
        email=f"employee{code}@example.com",
        phone=f"092{random_code(length=7)}",
        citizen_id=random_code(length=12),
        department=department,
        branch=department.branch,
        block=department.block,
        status=Employee.Status.ACTIVE,
        start_date=date.today(),
    )
    return employee


@pytest.mark.django_db
class TestEmployeeKPIAssessmentManagerField:
    """Test manager field in EmployeeKPIAssessment."""

    def test_manager_field_set_on_generation(
        self, assessment_period, employee_with_manager, manager_employee, kpi_criteria
    ):
        """Test that manager field is set from department leader when assessment is generated."""
        from apps.payroll.utils import generate_employee_assessments_for_period

        generate_employee_assessments_for_period(
            period=assessment_period,
            targets=["sales"],
            skip_existing=False,
        )

        assessment = EmployeeKPIAssessment.objects.get(
            employee=employee_with_manager,
            period=assessment_period,
        )

        assert assessment.manager == manager_employee
        assert assessment.manager == employee_with_manager.department.leader

    def test_manager_assessment_field_exists(self, assessment_period, employee_with_manager, manager_employee):
        """Test that manager_assessment field exists and can be set."""
        assessment = EmployeeKPIAssessment.objects.create(
            employee=employee_with_manager,
            period=assessment_period,
            manager=manager_employee,
            manager_assessment="Good performance, needs improvement in communication",
        )

        assert assessment.manager_assessment == "Good performance, needs improvement in communication"


@pytest.mark.django_db
class TestEmployeeSelfAssessmentBatchUpdate:
    """Test employee self-assessment batch update feature."""

    def test_batch_update_employee_scores(self, api_client, assessment_period, employee_with_manager, kpi_criteria):
        """Test batch updating employee scores via items parameter."""
        from apps.payroll.utils import create_assessment_items_from_criteria

        # Create assessment with items
        assessment = EmployeeKPIAssessment.objects.create(
            employee=employee_with_manager,
            period=assessment_period,
        )
        items = create_assessment_items_from_criteria(assessment, kpi_criteria)

        # Authenticate as employee
        user = User.objects.get(username=employee_with_manager.username)
        api_client.force_authenticate(user=user)

        # Batch update scores
        update_data = {
            "plan_tasks": "Completed all quarterly targets",
            "extra_tasks": "Helped train new team members",
            "proposal": "Suggest implementing new CRM system",
            "items": [
                {"item_id": items[0].id, "score": "65.00"},
                {"item_id": items[1].id, "score": "28.50"},
            ],
        }

        response = api_client.patch(f"/api/payroll/kpi-assessments/mine/{assessment.id}/", update_data, format="json")

        # Debug: print response if not 200
        if response.status_code != status.HTTP_200_OK:
            print(f"Response status: {response.status_code}")
            print(f"Response content: {response.json() if hasattr(response, 'json') else response.content}")

        assert response.status_code == status.HTTP_200_OK

        # Verify items were updated
        assessment.refresh_from_db()
        items[0].refresh_from_db()
        items[1].refresh_from_db()

        assert items[0].employee_score == Decimal("65.00")
        assert items[1].employee_score == Decimal("28.50")
        assert assessment.plan_tasks == "Completed all quarterly targets"
        assert assessment.extra_tasks == "Helped train new team members"
        assert assessment.proposal == "Suggest implementing new CRM system"
        assert assessment.total_employee_score == Decimal("93.50")

    def test_cannot_update_finalized_assessment(
        self, api_client, assessment_period, employee_with_manager, kpi_criteria
    ):
        """Test that finalized assessments cannot be updated."""
        from apps.payroll.utils import create_assessment_items_from_criteria

        assessment = EmployeeKPIAssessment.objects.create(
            employee=employee_with_manager,
            period=assessment_period,
            finalized=True,
        )
        items = create_assessment_items_from_criteria(assessment, kpi_criteria)

        user = User.objects.get(username=employee_with_manager.username)
        api_client.force_authenticate(user=user)

        update_data = {"items": {str(items[0].id): "65.00"}}

        response = api_client.patch(f"/api/payroll/kpi-assessments/mine/{assessment.id}/", update_data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestManagerAssessmentViews:
    """Test manager assessment views and functionality."""

    def test_manager_can_list_employee_assessments(
        self, api_client, assessment_period, employee_with_manager, manager_employee, kpi_criteria
    ):
        """Test manager can list assessments for their employees."""
        from apps.payroll.utils import create_assessment_items_from_criteria

        # Create assessment
        assessment = EmployeeKPIAssessment.objects.create(
            employee=employee_with_manager,
            period=assessment_period,
            manager=manager_employee,
        )
        create_assessment_items_from_criteria(assessment, kpi_criteria)

        # Authenticate as manager
        manager_user = User.objects.get(username=manager_employee.username)
        api_client.force_authenticate(user=manager_user)

        response = api_client.get("/api/payroll/kpi-assessments/manager/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["count"] == 1
        assert data["data"]["results"][0]["id"] == assessment.id

    def test_manager_batch_update_scores(
        self, api_client, assessment_period, employee_with_manager, manager_employee, kpi_criteria
    ):
        """Test manager can batch update manager scores."""
        from apps.payroll.utils import create_assessment_items_from_criteria

        assessment = EmployeeKPIAssessment.objects.create(
            employee=employee_with_manager,
            period=assessment_period,
            manager=manager_employee,
        )
        items = create_assessment_items_from_criteria(assessment, kpi_criteria)

        # Authenticate as manager
        manager_user = User.objects.get(username=manager_employee.username)
        api_client.force_authenticate(user=manager_user)

        # Batch update manager scores
        update_data = {
            "manager_assessment": "Good performance overall, needs improvement in time management",
            "items": [
                {"item_id": items[0].id, "score": "62.00"},
                {"item_id": items[1].id, "score": "27.00"},
            ],
        }

        response = api_client.patch(
            f"/api/payroll/kpi-assessments/manager/{assessment.id}/", update_data, format="json"
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify updates
        assessment.refresh_from_db()
        items[0].refresh_from_db()
        items[1].refresh_from_db()

        assert items[0].manager_score == Decimal("62.00")
        assert items[1].manager_score == Decimal("27.00")
        assert assessment.manager_assessment == "Good performance overall, needs improvement in time management"
        assert assessment.total_manager_score == Decimal("89.00")
        assert assessment.grade_manager == "B"

    def test_manager_cannot_see_other_managers_assessments(
        self, api_client, assessment_period, employee_with_manager, manager_employee, kpi_criteria, department
    ):
        """Test manager can only see their own employees' assessments."""
        from apps.payroll.utils import create_assessment_items_from_criteria

        # Create another manager
        code = random_code()
        other_manager = Employee.objects.create(
            username=f"othermgr{code}",
            email=f"othermgr{code}@example.com",
            phone=f"093{random_code(length=7)}",
            citizen_id=random_code(length=12),
            department=department,
            branch=department.branch,
            block=department.block,
            status=Employee.Status.ACTIVE,
            start_date=date.today(),
        )

        # Create assessment with different manager
        assessment = EmployeeKPIAssessment.objects.create(
            employee=employee_with_manager,
            period=assessment_period,
            manager=other_manager,
        )
        create_assessment_items_from_criteria(assessment, kpi_criteria)

        # Authenticate as first manager (from fixture)
        manager_user = User.objects.get(username=manager_employee.username)
        api_client.force_authenticate(user=manager_user)

        response = api_client.get("/api/payroll/kpi-assessments/manager/")

        # Should not see the assessment
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["count"] == 0


@pytest.mark.django_db
class TestEmployeeKPIAssessmentHRMUpdate:
    """Test HRM update restrictions for EmployeeKPIAssessment."""

    def test_hrm_can_only_update_grade_and_note(
        self, api_client, assessment_period, employee_with_manager, manager_employee, kpi_criteria
    ):
        """Test that HRM can only update grade_hrm and note fields."""
        from apps.payroll.utils import create_assessment_items_from_criteria

        assessment = EmployeeKPIAssessment.objects.create(
            employee=employee_with_manager,
            period=assessment_period,
            manager=manager_employee,
            plan_tasks="Original tasks",
            total_manager_score=Decimal("85.00"),
        )
        create_assessment_items_from_criteria(assessment, kpi_criteria)

        # Create HRM user with superuser privileges
        hrm_user = User.objects.create_superuser(
            username="hrm_staff",
            email="hrm@example.com",
            password="testpass123",
        )
        api_client.force_authenticate(user=hrm_user)

        # Try to update multiple fields
        update_data = {
            "grade_hrm": "A",
            "note": "Final review completed",
            "plan_tasks": "This should not update",
            "total_manager_score": "100.00",
        }

        response = api_client.patch(
            f"/api/payroll/kpi-assessments/employees/{assessment.id}/", update_data, format="json"
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify only grade_hrm and note were updated
        assessment.refresh_from_db()
        assert assessment.grade_hrm == "A"
        assert assessment.note == "Final review completed"
        assert assessment.plan_tasks == "Original tasks"  # Should not change
        assert assessment.total_manager_score == Decimal("85.00")  # Should not change

    def test_update_serializer_only_exposes_allowed_fields(self):
        """Test that EmployeeKPIAssessmentUpdateSerializer only exposes grade_hrm and note."""
        from apps.payroll.api.serializers import EmployeeKPIAssessmentUpdateSerializer

        serializer = EmployeeKPIAssessmentUpdateSerializer()
        fields = set(serializer.Meta.fields)

        assert fields == {"grade_hrm", "note"}
        assert "plan_tasks" not in fields
        assert "extra_tasks" not in fields
        assert "proposal" not in fields
        assert "total_manager_score" not in fields
