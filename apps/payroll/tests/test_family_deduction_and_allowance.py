"""Tests for new payroll calculation fields: total_family_deduction and non_taxable_allowance."""

from decimal import Decimal

import pytest

from apps.hrm.constants import EmployeeType
from apps.hrm.models import EmployeeDependent
from apps.payroll.services.payroll_calculation import PayrollCalculationService


@pytest.mark.django_db
class TestTotalFamilyDeduction:
    """Test total family deduction calculation."""

    def test_total_family_deduction_with_no_dependents(self, payroll_slip, contract, timesheet, employee):
        """Test total family deduction equals personal deduction when no dependents."""
        # Arrange
        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        expected_total = payroll_slip.personal_deduction + payroll_slip.dependent_deduction
        assert payroll_slip.total_family_deduction == expected_total
        assert payroll_slip.dependent_count == 0
        assert payroll_slip.dependent_deduction == Decimal("0")

    def test_total_family_deduction_with_dependents(self, payroll_slip, contract, timesheet, employee, salary_period):
        """Test total family deduction includes personal and dependent deductions."""
        # Arrange
        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.save()

        # Create 3 active dependents
        for i in range(3):
            EmployeeDependent.objects.create(
                employee=employee,
                dependent_name=f"Dependent {i}",
                relationship="CHILD",
                date_of_birth="2015-01-01",
                effective_date="2015-01-01",
                is_active=True,
            )

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.dependent_count == 3
        expected_total = payroll_slip.personal_deduction + payroll_slip.dependent_deduction
        assert payroll_slip.total_family_deduction == expected_total
        assert payroll_slip.total_family_deduction > payroll_slip.personal_deduction


@pytest.mark.django_db
class TestNonTaxableAllowance:
    """Test non-taxable allowance calculation."""

    def test_non_taxable_allowance_for_official_employee_full_month(self, payroll_slip, contract, timesheet, employee):
        """Test non-taxable allowance for official employee working full month."""
        # Arrange
        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.lunch_allowance = Decimal("1000000")
        contract.phone_allowance = Decimal("500000")
        contract.save()

        timesheet.official_working_days = Decimal("22.00")
        timesheet.probation_working_days = Decimal("0.00")
        timesheet.save()

        payroll_slip.salary_period.standard_working_days = Decimal("22.00")
        payroll_slip.salary_period.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        # Formula: (lunch + phone) / standard_days * (probation_days * 0.85 + official_days)
        # = (1000000 + 500000) / 22 * (0 * 0.85 + 22)
        # = 1500000 / 22 * 22 = 1500000
        expected_allowance = (
            (Decimal("1000000") + Decimal("500000"))
            / Decimal("22.00")
            * (Decimal("0.00") * Decimal("0.85") + Decimal("22.00"))
        )
        assert payroll_slip.non_taxable_allowance == expected_allowance.quantize(Decimal("1"))

    def test_non_taxable_allowance_for_official_employee_partial_month(
        self, payroll_slip, contract, timesheet, employee
    ):
        """Test non-taxable allowance for official employee working partial month."""
        # Arrange
        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.lunch_allowance = Decimal("1000000")
        contract.phone_allowance = Decimal("500000")
        contract.save()

        timesheet.official_working_days = Decimal("15.00")
        timesheet.probation_working_days = Decimal("0.00")
        timesheet.save()

        payroll_slip.salary_period.standard_working_days = Decimal("22.00")
        payroll_slip.salary_period.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        # Formula: (1000000 + 500000) / 22 * (0 * 0.85 + 15)
        # = 1500000 / 22 * 15 = 1022727.27 -> 1022727
        expected_allowance = (
            (Decimal("1000000") + Decimal("500000"))
            / Decimal("22.00")
            * (Decimal("0.00") * Decimal("0.85") + Decimal("15.00"))
        )
        assert payroll_slip.non_taxable_allowance == expected_allowance.quantize(Decimal("1"))

    def test_non_taxable_allowance_with_mixed_working_days(self, payroll_slip, contract, timesheet, employee):
        """Test non-taxable allowance with both probation and official working days."""
        # Arrange
        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.lunch_allowance = Decimal("1000000")
        contract.phone_allowance = Decimal("500000")
        contract.save()

        timesheet.official_working_days = Decimal("10.00")
        timesheet.probation_working_days = Decimal("12.00")
        timesheet.save()

        payroll_slip.salary_period.standard_working_days = Decimal("22.00")
        payroll_slip.salary_period.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        # Formula: (1000000 + 500000) / 22 * (12 * 0.85 + 10)
        # = 1500000 / 22 * (10.2 + 10) = 1500000 / 22 * 20.2
        allowance_base = Decimal("1000000") + Decimal("500000")
        working_days_factor = Decimal("12.00") * Decimal("0.85") + Decimal("10.00")
        expected_allowance = (allowance_base / Decimal("22.00") * working_days_factor).quantize(Decimal("1"))
        assert payroll_slip.non_taxable_allowance == expected_allowance

    def test_non_taxable_allowance_for_probation_employee_is_zero(self, payroll_slip, contract, timesheet, employee):
        """Test non-taxable allowance is zero for probation employees."""
        # Arrange
        employee.employee_type = EmployeeType.PROBATION
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.lunch_allowance = Decimal("1000000")
        contract.phone_allowance = Decimal("500000")
        contract.save()

        timesheet.probation_working_days = Decimal("22.00")
        timesheet.save()

        payroll_slip.salary_period.standard_working_days = Decimal("22.00")
        payroll_slip.salary_period.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.non_taxable_allowance == Decimal("0")

    def test_non_taxable_allowance_for_intern_is_zero(self, payroll_slip, contract, timesheet, employee):
        """Test non-taxable allowance is zero for intern employees."""
        # Arrange
        employee.employee_type = EmployeeType.INTERN
        employee.save()

        contract.base_salary = Decimal("15000000")
        contract.lunch_allowance = Decimal("1000000")
        contract.phone_allowance = Decimal("500000")
        contract.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.non_taxable_allowance == Decimal("0")

    def test_non_taxable_allowance_with_zero_allowances(self, payroll_slip, contract, timesheet, employee):
        """Test non-taxable allowance is zero when lunch and phone allowances are zero."""
        # Arrange
        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.lunch_allowance = Decimal("0")
        contract.phone_allowance = Decimal("0")
        contract.save()

        timesheet.official_working_days = Decimal("22.00")
        timesheet.save()

        payroll_slip.salary_period.standard_working_days = Decimal("22.00")
        payroll_slip.salary_period.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.non_taxable_allowance == Decimal("0")


@pytest.mark.django_db
class TestTaxableIncomeWithNonTaxableAllowance:
    """Test taxable income calculation includes non-taxable allowance deduction."""

    def test_official_employee_taxable_income_base_deducts_non_taxable_allowance(
        self, payroll_slip, contract, timesheet, employee
    ):
        """Test taxable income base deducts non-taxable allowance for official employees."""
        # Arrange
        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.lunch_allowance = Decimal("1000000")
        contract.phone_allowance = Decimal("500000")
        contract.save()

        timesheet.official_working_days = Decimal("22.00")
        timesheet.probation_working_days = Decimal("0.00")
        timesheet.save()

        payroll_slip.salary_period.standard_working_days = Decimal("22.00")
        payroll_slip.salary_period.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        # Verify non_taxable_allowance is calculated
        assert payroll_slip.non_taxable_allowance > 0

        # Verify taxable_income_base includes the deduction
        expected_base = (
            payroll_slip.gross_income
            - payroll_slip.non_taxable_travel_expense
            - payroll_slip.employee_social_insurance
            - payroll_slip.employee_health_insurance
            - payroll_slip.employee_unemployment_insurance
            - payroll_slip.non_taxable_overtime_salary
            - payroll_slip.non_taxable_allowance
        )
        assert payroll_slip.taxable_income_base == expected_base.quantize(Decimal("1"))

    def test_probation_employee_taxable_income_base_no_non_taxable_allowance(
        self, payroll_slip, contract, timesheet, employee
    ):
        """Test taxable income base for probation employees doesn't include non-taxable allowance."""
        # Arrange
        employee.employee_type = EmployeeType.PROBATION
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.lunch_allowance = Decimal("1000000")
        contract.phone_allowance = Decimal("500000")
        contract.save()

        timesheet.probation_working_days = Decimal("22.00")
        timesheet.save()

        payroll_slip.salary_period.standard_working_days = Decimal("22.00")
        payroll_slip.salary_period.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        # Verify non_taxable_allowance is zero
        assert payroll_slip.non_taxable_allowance == Decimal("0")

        # For probation: taxable_income_base = gross_income (flat 10% tax)
        assert payroll_slip.taxable_income_base == payroll_slip.gross_income

    def test_official_employee_lower_tax_with_non_taxable_allowance(self, payroll_slip, contract, timesheet, employee):
        """Test that non-taxable allowance reduces tax burden for official employees."""
        # Arrange
        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.lunch_allowance = Decimal("1000000")
        contract.phone_allowance = Decimal("500000")
        contract.save()

        timesheet.official_working_days = Decimal("22.00")
        timesheet.save()

        payroll_slip.salary_period.standard_working_days = Decimal("22.00")
        payroll_slip.salary_period.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        # The non-taxable allowance should reduce taxable income base
        # which in turn should reduce the personal income tax
        assert payroll_slip.non_taxable_allowance > 0
        assert payroll_slip.taxable_income_base < payroll_slip.gross_income
