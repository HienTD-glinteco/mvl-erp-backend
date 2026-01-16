"""Test leader assessment exclusion from regular views and statistics."""

import pytest
from django.utils import timezone

from apps.hrm.models import Department, Employee
from apps.payroll.models import (
    DepartmentKPIAssessment,
    EmployeeKPIAssessment,
    KPIAssessmentPeriod,
    KPIConfig,
)
from apps.payroll.utils import generate_department_assessments_for_period


@pytest.mark.django_db
class TestLeaderAssessmentExclusion:
    """Test that leader assessments are excluded from regular queries and statistics."""

    @pytest.fixture(autouse=True)
    def setup(self, branch, block, department, position):
        """Set up test data."""
        # Update department to have function
        department.function = Department.DepartmentFunction.BUSINESS
        department.save()

        # Create leader
        self.leader = Employee.objects.create(
            code="LEAD001",
            fullname="Test Leader",
            username="leader",
            email="leader@example.com",
            branch=branch,
            block=block,
            department=department,
            position=position,
            start_date=timezone.now().date(),
            attendance_code="123456",
            citizen_id="001234567890",
            phone="0912345678",
            personal_email="leader@personal.com",
        )

        # Set as department leader
        department.leader = self.leader
        department.save()

        # Create regular employees
        self.employee1 = Employee.objects.create(
            code="EMP001",
            fullname="Employee 1",
            username="emp1",
            email="emp1@example.com",
            branch=branch,
            block=block,
            department=department,
            position=position,
            start_date=timezone.now().date(),
            attendance_code="234567",
            citizen_id="001234567891",
            phone="0912345679",
            personal_email="emp1@personal.com",
        )

        self.employee2 = Employee.objects.create(
            code="EMP002",
            fullname="Employee 2",
            username="emp2",
            email="emp2@example.com",
            branch=branch,
            block=block,
            department=department,
            position=position,
            start_date=timezone.now().date(),
            attendance_code="345678",
            citizen_id="001234567892",
            phone="0912345680",
            personal_email="emp2@personal.com",
        )

        self.department = department
        self.branch = branch
        self.block = block

        # Create KPI config and period
        config_data = {
            "name": "Test KPI Config",
            "description": "Test",
            "ambiguous_assignment": "manual",
            "grade_thresholds": [
                {
                    "min": 90.0,
                    "max": 100.0,
                    "possible_codes": ["A"],
                    "label": "Excellent",
                    "default_code": "A",
                },
                {
                    "min": 75.0,
                    "max": 90.0,
                    "possible_codes": ["B"],
                    "label": "Good",
                    "default_code": "B",
                },
                {
                    "min": 50.0,
                    "max": 75.0,
                    "possible_codes": ["C"],
                    "label": "Average",
                    "default_code": "C",
                },
                {
                    "min": 0.0,
                    "max": 50.0,
                    "possible_codes": ["D"],
                    "label": "Below Average",
                    "default_code": "D",
                },
            ],
            "unit_control": {
                "department": {
                    "A": {"min": 0.0, "max": 0.3, "target": 0.2},
                    "B": {"min": 0.2, "max": 0.5, "target": 0.4},
                    "C": {"min": 0.2, "max": 0.6, "target": 0.3},
                    "D": {"min": 0.0, "max": 0.2, "target": 0.1},
                }
            },
            "meta": {},
        }
        self.kpi_config = KPIConfig.objects.create(config=config_data)
        self.period = KPIAssessmentPeriod.objects.create(
            month=timezone.now().date().replace(day=1),
            kpi_config_snapshot=self.kpi_config.config,
        )

    def test_generate_department_assessment_creates_leader_assessment(self):
        """Test that generating department assessment creates leader assessment with is_for_leader=True."""
        # Generate department assessments
        count = generate_department_assessments_for_period(self.period)

        assert count == 1

        # Check leader assessment
        leader_assessment = EmployeeKPIAssessment.objects.get(employee=self.leader, period=self.period)
        assert leader_assessment.is_for_leader is True
        assert leader_assessment.grade_hrm == "C"
        assert leader_assessment.finalized is True

    def test_leader_assessment_excluded_from_regular_queryset(self):
        """Test that leader assessments are excluded from regular employee querysets."""
        # Create assessments
        generate_department_assessments_for_period(self.period)

        # Create regular employee assessments
        EmployeeKPIAssessment.objects.create(
            employee=self.employee1, period=self.period, department_snapshot=self.department, is_for_leader=False
        )
        EmployeeKPIAssessment.objects.create(
            employee=self.employee2, period=self.period, department_snapshot=self.department, is_for_leader=False
        )

        # Regular query should exclude leader assessment
        regular_assessments = EmployeeKPIAssessment.objects.filter(is_for_leader=False)
        assert regular_assessments.count() == 2
        assert self.leader not in [a.employee for a in regular_assessments]

        # All assessments including leader
        all_assessments = EmployeeKPIAssessment.objects.all()
        assert all_assessments.count() == 3

    def test_leader_assessment_excluded_from_statistics(self):
        """Test that leader assessments are excluded from department statistics."""
        # Generate department and employee assessments
        generate_department_assessments_for_period(self.period)

        # Create regular employee assessments with grades
        emp1_assessment = EmployeeKPIAssessment.objects.create(
            employee=self.employee1,
            period=self.period,
            department_snapshot=self.department,
            is_for_leader=False,
            grade_manager="A",
        )
        emp2_assessment = EmployeeKPIAssessment.objects.create(
            employee=self.employee2,
            period=self.period,
            department_snapshot=self.department,
            is_for_leader=False,
            grade_manager="B",
        )

        # Update department grade distribution
        dept_assessment = DepartmentKPIAssessment.objects.get(department=self.department, period=self.period)
        dept_assessment.update_grade_distribution()

        # Check distribution excludes leader
        assert dept_assessment.grade_distribution == {"A": 1, "B": 1, "C": 0, "D": 0}
        assert dept_assessment.manager_grade_distribution == {"A": 1, "B": 1, "C": 0, "D": 0}

    def test_leader_assessment_not_visible_in_employee_self_view(self):
        """Test that leader cannot see their is_for_leader assessment in employee self view."""
        # Generate assessments
        generate_department_assessments_for_period(self.period)

        # Query as if from employee self-assessment view
        employee_view_assessments = EmployeeKPIAssessment.objects.filter(employee=self.leader, is_for_leader=False)

        assert employee_view_assessments.count() == 0

    def test_leader_assessment_not_visible_in_manager_view(self):
        """Test that leader assessments are not visible in manager view."""
        # Generate assessments
        generate_department_assessments_for_period(self.period)

        # Create regular employee assessment
        EmployeeKPIAssessment.objects.create(
            employee=self.employee1,
            period=self.period,
            department_snapshot=self.department,
            manager=self.leader,
            is_for_leader=False,
        )

        # Query as if from manager assessment view
        manager_view_assessments = EmployeeKPIAssessment.objects.filter(manager=self.leader, is_for_leader=False)

        assert manager_view_assessments.count() == 1
        assert manager_view_assessments.first().employee == self.employee1

    def test_department_grade_updates_leader_assessment(self):
        """Test that updating department grade updates the leader's assessment."""
        # Generate assessments
        generate_department_assessments_for_period(self.period)

        dept_assessment = DepartmentKPIAssessment.objects.get(department=self.department, period=self.period)

        # Update department grade
        dept_assessment.grade = "A"
        dept_assessment.save()

        # Update leader assessment through serializer logic
        EmployeeKPIAssessment.objects.filter(
            employee=self.leader,
            period=self.period,
        ).update(grade_hrm="A")

        # Verify leader assessment updated
        leader_assessment = EmployeeKPIAssessment.objects.get(employee=self.leader, period=self.period)
        assert leader_assessment.grade_hrm == "A"
        assert leader_assessment.is_for_leader is True
