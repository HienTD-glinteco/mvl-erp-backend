"""Tests for fix_employee_kpi_department management command."""

from io import StringIO

import pytest
from django.core.management import call_command

from apps.payroll.models import EmployeeKPIAssessment


@pytest.mark.django_db
class TestFixEmployeeKPIDepartmentCommand:
    """Test suite for fix_employee_kpi_department command."""

    def test_command_with_no_null_departments(
        self,
        employee,
        department,
        kpi_assessment_period,
    ):
        """Test command when all assessments already have department set."""
        # Create assessment with department already set
        EmployeeKPIAssessment.objects.create(
            employee=employee,
            period=kpi_assessment_period,
            department_snapshot=department,
        )

        out = StringIO()
        call_command("fix_employee_kpi_department", stdout=out)

        output = out.getvalue()
        assert "All EmployeeKPIAssessment records already have department set" in output

    def test_command_fixes_null_departments(
        self,
        employee,
        department,
        kpi_assessment_period,
    ):
        """Test command fixes records with NULL department."""
        # Create assessment WITHOUT department
        assessment = EmployeeKPIAssessment.objects.create(
            employee=employee,
            period=kpi_assessment_period,
            department_snapshot=None,
        )

        assert assessment.department_snapshot is None

        out = StringIO()
        call_command("fix_employee_kpi_department", stdout=out)

        output = out.getvalue()
        assert "Updated: 1" in output
        assert "Department field fixed successfully" in output

        # Verify department was set
        assessment.refresh_from_db()
        assert assessment.department_snapshot == department

    def test_command_dry_run_mode(
        self,
        employee,
        department,
        kpi_assessment_period,
    ):
        """Test command in dry-run mode doesn't save changes."""
        # Create assessment WITHOUT department
        assessment = EmployeeKPIAssessment.objects.create(
            employee=employee,
            period=kpi_assessment_period,
            department_snapshot=None,
        )

        out = StringIO()
        call_command("fix_employee_kpi_department", "--dry-run", stdout=out)

        output = out.getvalue()
        assert "DRY RUN MODE" in output
        assert "No changes were saved" in output

        # Verify department was NOT set
        assessment.refresh_from_db()
        assert assessment.department_snapshot is None

    def test_command_filter_by_period(
        self,
        employee,
        department,
        kpi_assessment_period,
        salary_period,
    ):
        """Test command with period filter."""
        from datetime import date

        from apps.payroll.models import KPIAssessmentPeriod

        # Create another period
        period2 = KPIAssessmentPeriod.objects.create(
            month=date(2025, 2, 1),
            kpi_config_snapshot={},
        )

        # Create assessments in both periods
        assessment1 = EmployeeKPIAssessment.objects.create(
            employee=employee,
            period=kpi_assessment_period,
            department_snapshot=None,
        )
        assessment2 = EmployeeKPIAssessment.objects.create(
            employee=employee,
            period=period2,
            department_snapshot=None,
        )

        out = StringIO()
        call_command("fix_employee_kpi_department", f"--period={kpi_assessment_period.id}", stdout=out)

        output = out.getvalue()
        assert f"Filtering by period ID: {kpi_assessment_period.id}" in output
        assert "Updated: 1" in output

        # Only assessment1 should be fixed
        assessment1.refresh_from_db()
        assessment2.refresh_from_db()
        assert assessment1.department_snapshot == department
        assert assessment2.department_snapshot is None

    def test_command_with_multiple_assessments(
        self,
        department,
        branch,
        block,
        position,
        kpi_assessment_period,
    ):
        """Test command handles multiple assessments correctly."""
        from datetime import date

        from apps.hrm.constants import EmployeeType
        from apps.hrm.models import Employee

        # Create multiple employees
        employees = []
        for i in range(5):
            emp = Employee.objects.create(
                code=f"EMP{i:03d}",
                fullname=f"Employee {i}",
                username=f"emp{i}",
                email=f"emp{i}@test.com",
                status=Employee.Status.ACTIVE,
                code_type=Employee.CodeType.MV,
                employee_type=EmployeeType.OFFICIAL,
                branch=branch,
                block=block,
                department=department,
                position=position,
                start_date=date(2024, 1, 1),
                attendance_code=f"{i:06d}",
                citizen_id=f"{i:012d}",
                phone=f"09{i:08d}",
            )
            employees.append(emp)

            # Create assessment without department
            EmployeeKPIAssessment.objects.create(
                employee=emp,
                period=kpi_assessment_period,
                department_snapshot=None,
            )

        out = StringIO()
        call_command("fix_employee_kpi_department", stdout=out)

        output = out.getvalue()
        assert "Found 5 employee KPI assessments with NULL department" in output
        assert "Updated: 5" in output

        # Verify all were fixed
        for emp in employees:
            assessment = EmployeeKPIAssessment.objects.get(employee=emp, period=kpi_assessment_period)
            assert assessment.department_snapshot == department
