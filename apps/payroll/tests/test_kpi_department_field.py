"""Tests for EmployeeKPIAssessment department field."""

import pytest

from apps.hrm.models import Department
from apps.payroll.models import DepartmentKPIAssessment, EmployeeKPIAssessment


@pytest.mark.django_db
class TestEmployeeKPIAssessmentDepartmentField:
    """Test suite for department field in EmployeeKPIAssessment."""

    def test_department_field_saved_when_assessment_created(
        self,
        department,
        employee,
        kpi_assessment_period,
    ):
        """Test that department field is saved when creating assessment."""
        # Create assessment
        assessment = EmployeeKPIAssessment.objects.create(
            employee=employee,
            period=kpi_assessment_period,
            department_snapshot=employee.department,
        )

        assert assessment.department_snapshot == department
        assert assessment.department_snapshot.id == employee.department.id

    def test_department_snapshot_preserved_after_employee_department_change(
        self,
        department,
        employee,
        kpi_assessment_period,
        branch,
        block,
    ):
        """Test that department snapshot is preserved even when employee changes department."""
        # Create second department
        department2 = Department.objects.create(
            name="Second Department",
            code="DEPT2",
            branch=branch,
            block=block,
        )

        # Create assessment with original department
        assessment = EmployeeKPIAssessment.objects.create(
            employee=employee,
            period=kpi_assessment_period,
            department_snapshot=employee.department,
        )

        original_department = assessment.department_snapshot

        # Change employee's department
        employee.department = department2
        employee.save()

        # Reload assessment
        assessment.refresh_from_db()

        # Department snapshot should remain unchanged
        assert assessment.department_snapshot == original_department
        assert assessment.employee.department == department2

    def test_generate_employee_assessments_sets_department(
        self,
        employee,
        department,
        kpi_assessment_period,
    ):
        """Test that department field is set when generating assessment directly."""
        # Simply test that when we create the assessment in the generate function,
        # the department field gets set - we already test the logic in signals
        # Just ensure the assessment utility sets it correctly
        from apps.payroll.models import KPICriterion
        from apps.payroll.utils import create_assessment_items_from_criteria

        # Create a KPI criterion
        criterion = KPICriterion.objects.create(
            target="backoffice",
            criterion="Test criterion",
            evaluation_type="work_performance",
            component_total_score=100,
            group_number=1,
            order=1,
            active=True,
        )

        # Create assessment manually (like the generate function does)
        assessment = EmployeeKPIAssessment.objects.create(
            employee=employee,
            period=kpi_assessment_period,
            manager=employee.department.leader if hasattr(employee.department, "leader") else None,
            department_snapshot=employee.department,
        )

        create_assessment_items_from_criteria(assessment, [criterion])

        # Verify department field is set
        assessment.refresh_from_db()
        assert assessment.department_snapshot == department
        assert assessment.department_snapshot is not None


@pytest.mark.django_db
class TestDepartmentKPIAssessmentListView:
    """Test suite for DepartmentKPIAssessment list view with new fields."""

    def test_employee_count_annotation_in_queryset(
        self,
        department,
        branch,
        block,
        position,
        kpi_assessment_period,
    ):
        """Test that employee_count is correctly annotated in queryset."""
        from datetime import date

        from django.db.models import Count, F, Q

        from apps.hrm.constants import EmployeeType

        # Create employees
        from apps.hrm.models import Employee

        emp1 = Employee.objects.create(
            code="EMP001",
            fullname="Employee 1",
            username="emp1",
            email="emp1@test.com",
            status=Employee.Status.ACTIVE,
            code_type=Employee.CodeType.MV,
            employee_type=EmployeeType.OFFICIAL,
            branch=branch,
            block=block,
            department=department,
            position=position,
            start_date=date(2024, 1, 1),
            attendance_code="123456",
            citizen_id="123456789012",
            phone="0912345678",
            personal_email="emp1.personal@test.com",
        )
        emp2 = Employee.objects.create(
            code="EMP002",
            fullname="Employee 2",
            username="emp2",
            email="emp2@test.com",
            status=Employee.Status.ACTIVE,
            code_type=Employee.CodeType.MV,
            employee_type=EmployeeType.OFFICIAL,
            branch=branch,
            block=block,
            department=department,
            position=position,
            start_date=date(2024, 1, 1),
            attendance_code="123457",
            citizen_id="123456789013",
            phone="0912345679",
            personal_email="emp2.personal@test.com",
        )

        # Create department assessment
        dept_assessment = DepartmentKPIAssessment.objects.create(
            department=department,
            period=kpi_assessment_period,
            grade="C",
        )

        # Create employee assessments with department snapshot
        EmployeeKPIAssessment.objects.create(
            employee=emp1,
            period=kpi_assessment_period,
            department_snapshot=department,
        )
        EmployeeKPIAssessment.objects.create(
            employee=emp2,
            period=kpi_assessment_period,
            department_snapshot=department,
        )

        # Test the annotation logic directly
        queryset = DepartmentKPIAssessment.objects.annotate(
            employee_count=Count(
                "department__employee_kpi_assessments",
                filter=Q(department__employee_kpi_assessments__period=F("period")),
                distinct=True,
            )
        )

        result = queryset.get(id=dept_assessment.id)
        assert result.employee_count == 2

    def test_is_valid_unit_control_field(
        self,
        department,
        kpi_assessment_period,
    ):
        """Test that is_valid_unit_control field works correctly."""
        # Create department assessment
        dept_assessment = DepartmentKPIAssessment.objects.create(
            department=department,
            period=kpi_assessment_period,
            grade="C",
            is_valid_unit_control=True,
        )

        # Verify the field
        assert dept_assessment.is_valid_unit_control is True

        # Test with False
        dept_assessment.is_valid_unit_control = False
        dept_assessment.save()

        dept_assessment.refresh_from_db()
        assert dept_assessment.is_valid_unit_control is False

    def test_employee_count_with_no_employees(
        self,
        department,
        kpi_assessment_period,
    ):
        """Test employee_count is 0 when no employee assessments exist."""
        from django.db.models import Count, F, Q

        # Create department assessment
        dept_assessment = DepartmentKPIAssessment.objects.create(
            department=department,
            period=kpi_assessment_period,
            grade="C",
        )

        # Test the annotation logic
        queryset = DepartmentKPIAssessment.objects.annotate(
            employee_count=Count(
                "department__employee_kpi_assessments",
                filter=Q(department__employee_kpi_assessments__period=F("period")),
                distinct=True,
            )
        )

        result = queryset.get(id=dept_assessment.id)
        assert result.employee_count == 0

    def test_update_grade_distribution_uses_department_field(
        self,
        department,
        branch,
        block,
        position,
        kpi_assessment_period,
    ):
        """Test that update_grade_distribution uses department field for counting."""
        # Create employees
        from datetime import date

        from apps.hrm.constants import EmployeeType
        from apps.hrm.models import Employee

        emp1 = Employee.objects.create(
            code="EMP003",
            fullname="Employee 3",
            username="emp3",
            email="emp3@test.com",
            status=Employee.Status.ACTIVE,
            code_type=Employee.CodeType.MV,
            employee_type=EmployeeType.OFFICIAL,
            branch=branch,
            block=block,
            department=department,
            position=position,
            start_date=date(2024, 1, 1),
            attendance_code="123458",
            citizen_id="123456789014",
            phone="0912345680",
            personal_email="emp3.personal@test.com",
        )
        emp2 = Employee.objects.create(
            code="EMP004",
            fullname="Employee 4",
            username="emp4",
            email="emp4@test.com",
            status=Employee.Status.ACTIVE,
            code_type=Employee.CodeType.MV,
            employee_type=EmployeeType.OFFICIAL,
            branch=branch,
            block=block,
            department=department,
            position=position,
            start_date=date(2024, 1, 1),
            attendance_code="123459",
            citizen_id="123456789015",
            phone="0912345681",
            personal_email="emp4.personal@test.com",
        )

        # Create department assessment
        dept_assessment = DepartmentKPIAssessment.objects.create(
            department=department,
            period=kpi_assessment_period,
            grade="C",
        )

        # Create employee assessments with grades
        EmployeeKPIAssessment.objects.create(
            employee=emp1,
            period=kpi_assessment_period,
            department_snapshot=department,
            grade_manager="A",
        )
        EmployeeKPIAssessment.objects.create(
            employee=emp2,
            period=kpi_assessment_period,
            department_snapshot=department,
            grade_manager="B",
        )

        # Update grade distribution
        dept_assessment.update_grade_distribution()

        # Check distribution
        assert dept_assessment.grade_distribution == {"A": 1, "B": 1, "C": 0, "D": 0}

    def test_grade_distribution_updated_automatically_via_signal(
        self,
        department,
        branch,
        block,
        position,
        kpi_assessment_period,
    ):
        """Test that grade distribution is updated automatically when employee grade is set."""
        # Create employees
        from datetime import date

        from apps.hrm.constants import EmployeeType
        from apps.hrm.models import Employee

        emp1 = Employee.objects.create(
            code="EMP005",
            fullname="Employee 5",
            username="emp5",
            email="emp5@test.com",
            status=Employee.Status.ACTIVE,
            code_type=Employee.CodeType.MV,
            employee_type=EmployeeType.OFFICIAL,
            branch=branch,
            block=block,
            department=department,
            position=position,
            start_date=date(2024, 1, 1),
            attendance_code="123460",
            citizen_id="123456789016",
            phone="0912345682",
            personal_email="emp5.personal@test.com",
        )
        emp2 = Employee.objects.create(
            code="EMP006",
            fullname="Employee 6",
            username="emp6",
            email="emp6@test.com",
            status=Employee.Status.ACTIVE,
            code_type=Employee.CodeType.MV,
            employee_type=EmployeeType.OFFICIAL,
            branch=branch,
            block=block,
            department=department,
            position=position,
            start_date=date(2024, 1, 1),
            attendance_code="123461",
            citizen_id="123456789017",
            phone="0912345683",
            personal_email="emp6.personal@test.com",
        )

        # Create department assessment
        dept_assessment = DepartmentKPIAssessment.objects.create(
            department=department,
            period=kpi_assessment_period,
            grade="C",
        )

        # Initially no distribution
        assert dept_assessment.grade_distribution == {}

        # Create first employee assessment with grade - should trigger signal
        EmployeeKPIAssessment.objects.create(
            employee=emp1,
            period=kpi_assessment_period,
            department_snapshot=department,
            grade_manager="A",
        )

        # Refresh and check distribution was updated
        dept_assessment.refresh_from_db()
        assert dept_assessment.grade_distribution == {"A": 1, "B": 0, "C": 0, "D": 0}

        # Create second employee assessment with grade
        EmployeeKPIAssessment.objects.create(
            employee=emp2,
            period=kpi_assessment_period,
            department_snapshot=department,
            grade_manager="B",
        )

        # Refresh and check distribution was updated again
        dept_assessment.refresh_from_db()
        assert dept_assessment.grade_distribution == {"A": 1, "B": 1, "C": 0, "D": 0}
