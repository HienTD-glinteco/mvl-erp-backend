"""Tests for generate_salary_period management command."""

from datetime import date
from io import StringIO

import pytest
from django.core.management import call_command

from apps.payroll.models import PayrollSlip, SalaryPeriod


@pytest.mark.django_db
class TestGenerateSalaryPeriodCommand:
    """Test generate_salary_period management command."""

    def test_generate_for_next_month(self, salary_config, employee):
        """Test generating salary period for next month."""
        # Arrange
        out = StringIO()

        # Act
        call_command("generate_salary_period", stdout=out)

        # Assert
        output = out.getvalue()
        assert "Successfully generated salary period" in output
        assert SalaryPeriod.objects.exists()

    def test_generate_for_specific_month(self, salary_config, employee):
        """Test generating salary period for specific month."""
        # Arrange
        out = StringIO()

        # Act
        call_command("generate_salary_period", "--month=2024-01", stdout=out)

        # Assert
        period = SalaryPeriod.objects.get(month=date(2024, 1, 1))
        assert period.code == "SP_202401"
        assert period.total_employees > 0

    def test_override_existing_period(self, salary_config, employee, salary_period):
        """Test override flag deletes and recreates period."""
        # Arrange
        old_period_id = salary_period.id
        month_str = salary_period.month.strftime("%Y-%m")
        out = StringIO()

        # Act
        call_command("generate_salary_period", f"--month={month_str}", "--override", stdout=out)

        # Assert
        assert not SalaryPeriod.objects.filter(id=old_period_id).exists()
        new_period = SalaryPeriod.objects.get(month=salary_period.month)
        assert new_period.id != old_period_id

    def test_fail_without_override(self, salary_config, employee, salary_period):
        """Test command fails if period exists without override flag."""
        # Arrange
        month_str = salary_period.month.strftime("%Y-%m")

        # Act & Assert
        with pytest.raises(Exception):
            call_command("generate_salary_period", f"--month={month_str}")

    def test_creates_payroll_slips(self, salary_config, employee):
        """Test command creates payroll slips for employees."""
        # Arrange
        out = StringIO()

        # Act
        call_command("generate_salary_period", "--month=2024-01", stdout=out)

        # Assert
        period = SalaryPeriod.objects.get(month=date(2024, 1, 1))
        assert PayrollSlip.objects.filter(salary_period=period).exists()
        assert PayrollSlip.objects.filter(salary_period=period, employee=employee).exists()

    def test_calculates_payroll_slips(self, salary_config, employee, contract, timesheet):
        """Test command calculates all payroll slips."""
        # Arrange
        out = StringIO()

        # Delete any existing periods for this month
        from datetime import date

        SalaryPeriod.objects.filter(month=date(2024, 1, 1)).delete()

        # Act
        call_command("generate_salary_period", "--month=2024-01", stdout=out)

        # Assert
        period = SalaryPeriod.objects.get(month=date(2024, 1, 1))
        slip = PayrollSlip.objects.get(salary_period=period, employee=employee)
        assert slip.calculated_at is not None
        assert slip.net_salary > 0  # Should have calculated values
