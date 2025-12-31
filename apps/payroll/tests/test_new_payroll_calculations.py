"""Tests for new payroll calculation formulas."""

from decimal import Decimal

import pytest

from apps.hrm.constants import EmployeeType
from apps.payroll.services.payroll_calculation import PayrollCalculationService


@pytest.mark.django_db
class TestTotalPositionIncome:
    """Test total position income calculation."""

    def test_total_position_income_includes_all_components(self, payroll_slip, contract, timesheet):
        """Test that total position income includes all salary components."""
        # Arrange
        contract.base_salary = Decimal("20000000")
        contract.lunch_allowance = Decimal("1000000")
        contract.phone_allowance = Decimal("500000")
        contract.other_allowance = Decimal("500000")
        contract.kpi_salary = Decimal("2000000")
        contract.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        expected_total = (
            Decimal("20000000")
            + Decimal("1000000")
            + Decimal("500000")
            + Decimal("500000")
            + Decimal("2000000")
            + payroll_slip.kpi_bonus
            + payroll_slip.business_progressive_salary
        )
        assert payroll_slip.total_position_income == expected_total

    def test_total_position_income_includes_kpi_bonus(self, payroll_slip, contract, timesheet, kpi_assessment):
        """Test that total position income includes calculated KPI bonus."""
        # Arrange
        kpi_assessment.grade_manager = "A"
        kpi_assessment.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        # KPI bonus should be 10% of base salary for grade A
        expected_kpi_bonus = contract.base_salary * Decimal("0.1")
        assert payroll_slip.kpi_bonus == expected_kpi_bonus
        assert payroll_slip.total_position_income > contract.base_salary


@pytest.mark.django_db
class TestActualWorkingDaysIncome:
    """Test actual working days income calculation."""

    def test_sales_staff_income_calculation(self, payroll_slip, contract, timesheet, employee, position):
        """Test income calculation for sales staff (NVKD position)."""
        # Arrange - Set position as sales staff
        position.name = "Nhân viên Kinh doanh (NVKD)"
        position.save()
        employee.position = position
        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.save()

        timesheet.total_working_days = Decimal("20.00")
        timesheet.save()

        payroll_slip.salary_period.standard_working_days = Decimal("22.00")
        payroll_slip.salary_period.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        # For sales staff: (total_working_days / standard_working_days) * total_position_income
        expected_income = (Decimal("20.00") / Decimal("22.00")) * payroll_slip.total_position_income
        assert payroll_slip.actual_working_days_income == expected_income.quantize(Decimal("1"))

    def test_non_sales_official_days_only(self, payroll_slip, contract, timesheet, employee):
        """Test income for non-sales staff with only official working days."""
        # Arrange - Non-sales position
        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
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
        # For non-sales with only official days: (official_days * income) / standard_days
        expected_income = (Decimal("22.00") * payroll_slip.total_position_income) / Decimal("22.00")
        assert payroll_slip.actual_working_days_income == expected_income.quantize(Decimal("1"))

    def test_non_sales_mixed_official_and_probation_days(self, payroll_slip, contract, timesheet, employee):
        """Test income for non-sales staff with mixed official and probation days."""
        # Arrange
        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.save()

        timesheet.official_working_days = Decimal("15.00")
        timesheet.probation_working_days = Decimal("7.00")
        timesheet.save()

        payroll_slip.salary_period.standard_working_days = Decimal("22.00")
        payroll_slip.salary_period.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        # Formula: ((official_days * income) + (probation_days * income * 0.85)) / standard_days
        total_position_income = payroll_slip.total_position_income
        official_income = Decimal("15.00") * total_position_income
        probation_income = Decimal("7.00") * total_position_income * Decimal("0.85")
        expected_income = (official_income + probation_income) / Decimal("22.00")
        assert payroll_slip.actual_working_days_income == expected_income.quantize(Decimal("1"))


@pytest.mark.django_db
class TestHourlyRateCalculation:
    """Test hourly rate calculation based on employee status."""

    def test_hourly_rate_for_probation_employee(self, payroll_slip, contract, timesheet, employee):
        """Test hourly rate calculation for probation employee (85% of normal)."""
        # Arrange
        employee.employee_type = EmployeeType.PROBATION
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.save()

        payroll_slip.salary_period.standard_working_days = Decimal("22.00")
        payroll_slip.salary_period.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        # For probation: (total_position_income * 0.85) / (standard_days * 8)
        expected_rate = (payroll_slip.total_position_income * Decimal("0.85")) / (Decimal("22.00") * Decimal("8"))
        assert payroll_slip.hourly_rate == expected_rate.quantize(Decimal("0.01"))

    def test_hourly_rate_for_official_employee(self, payroll_slip, contract, timesheet, employee):
        """Test hourly rate calculation for official employee (100%)."""
        # Arrange
        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.save()

        payroll_slip.salary_period.standard_working_days = Decimal("22.00")
        payroll_slip.salary_period.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        # For official: total_position_income / (standard_days * 8)
        expected_rate = payroll_slip.total_position_income / (Decimal("22.00") * Decimal("8"))
        assert payroll_slip.hourly_rate == expected_rate.quantize(Decimal("0.01"))


@pytest.mark.django_db
class TestOvertimeCalculations:
    """Test overtime salary calculations."""

    def test_taxable_overtime_salary(self, payroll_slip, contract, timesheet, employee):
        """Test taxable overtime salary calculation."""
        # Arrange
        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.save()

        timesheet.tc1_overtime_hours = Decimal("10.00")
        timesheet.tc2_overtime_hours = Decimal("8.00")
        timesheet.tc3_overtime_hours = Decimal("4.00")
        timesheet.save()

        payroll_slip.salary_period.standard_working_days = Decimal("22.00")
        payroll_slip.salary_period.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        total_ot_hours = Decimal("10.00") + Decimal("8.00") + Decimal("4.00")
        expected_taxable = total_ot_hours * payroll_slip.hourly_rate
        assert payroll_slip.total_overtime_hours == total_ot_hours
        assert payroll_slip.taxable_overtime_salary == expected_taxable.quantize(Decimal("1"))

    def test_overtime_progress_allowance(self, payroll_slip, contract, timesheet, employee):
        """Test overtime progress allowance calculation."""
        # Arrange
        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.save()

        timesheet.tc1_overtime_hours = Decimal("10.00")
        timesheet.tc2_overtime_hours = Decimal("8.00")
        timesheet.save()

        payroll_slip.salary_period.standard_working_days = Decimal("22.00")
        payroll_slip.salary_period.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        expected_allowance = payroll_slip.overtime_pay - payroll_slip.taxable_overtime_salary
        assert payroll_slip.overtime_progress_allowance == expected_allowance.quantize(Decimal("1"))

    def test_non_taxable_overtime_capped_at_2x(self, payroll_slip, contract, timesheet, employee):
        """Test that non-taxable overtime is capped at 2x taxable overtime."""
        # Arrange - Set up scenario where progress allowance > 2x taxable
        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.save()

        # High multiplier overtime (holiday at 3x)
        timesheet.tc3_overtime_hours = Decimal("20.00")
        timesheet.save()

        payroll_slip.salary_period.standard_working_days = Decimal("22.00")
        payroll_slip.salary_period.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        # If progress allowance > 2x taxable, cap at 2x
        max_non_taxable = payroll_slip.taxable_overtime_salary * Decimal("2")
        if payroll_slip.overtime_progress_allowance > max_non_taxable:
            assert payroll_slip.non_taxable_overtime_salary == max_non_taxable.quantize(Decimal("1"))
        else:
            assert payroll_slip.non_taxable_overtime_salary == (
                payroll_slip.overtime_pay - payroll_slip.taxable_overtime_salary
            ).quantize(Decimal("1"))

    def test_non_taxable_overtime_not_capped_when_under_2x(self, payroll_slip, contract, timesheet, employee):
        """Test non-taxable overtime when progress allowance <= 2x taxable."""
        # Arrange - Lower overtime hours
        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.save()

        timesheet.tc1_overtime_hours = Decimal("5.00")
        timesheet.save()

        payroll_slip.salary_period.standard_working_days = Decimal("22.00")
        payroll_slip.salary_period.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        expected_non_taxable = payroll_slip.overtime_pay - payroll_slip.taxable_overtime_salary
        assert payroll_slip.non_taxable_overtime_salary == expected_non_taxable.quantize(Decimal("1"))


@pytest.mark.django_db
class TestGrossIncomeCalculation:
    """Test gross income calculation with new formula."""

    def test_gross_income_formula(self, payroll_slip, contract, timesheet, employee):
        """Test that gross income uses new formula."""
        # Arrange
        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.save()

        timesheet.tc1_overtime_hours = Decimal("10.00")
        timesheet.save()

        payroll_slip.salary_period.standard_working_days = Decimal("22.00")
        payroll_slip.salary_period.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        # New formula: actual_working_days_income + taxable_overtime + non_taxable_overtime + travel
        expected_gross = (
            payroll_slip.actual_working_days_income
            + payroll_slip.taxable_overtime_salary
            + payroll_slip.non_taxable_overtime_salary
            + payroll_slip.total_travel_expense
        )
        assert payroll_slip.gross_income == expected_gross.quantize(Decimal("1"))


@pytest.mark.django_db
class TestSocialInsuranceBasedOnEmployeeType:
    """Test social insurance calculation based on employee type."""

    def test_official_employee_has_social_insurance(self, payroll_slip, contract, timesheet, employee):
        """Test that official employees have social insurance calculated."""
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
        assert payroll_slip.social_insurance_base > 0
        assert payroll_slip.employee_social_insurance > 0
        assert payroll_slip.employee_health_insurance > 0
        assert payroll_slip.employee_unemployment_insurance > 0

    def test_probation_employee_no_social_insurance(self, payroll_slip, contract, timesheet, employee):
        """Test that probation employees have zero social insurance."""
        # Arrange
        employee.employee_type = EmployeeType.PROBATION
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.social_insurance_base == 0
        assert payroll_slip.employee_social_insurance == 0
        assert payroll_slip.employee_health_insurance == 0
        assert payroll_slip.employee_unemployment_insurance == 0
        assert payroll_slip.employee_union_fee == 0

    def test_intern_employee_no_social_insurance(self, payroll_slip, contract, timesheet, employee):
        """Test that intern employees have zero social insurance."""
        # Arrange
        employee.employee_type = EmployeeType.INTERN
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.social_insurance_base == 0
        assert payroll_slip.employee_social_insurance == 0


@pytest.mark.django_db
class TestPersonalIncomeTaxBasedOnEmployeeType:
    """Test personal income tax calculation based on employee type."""

    def test_official_employee_progressive_tax(self, payroll_slip, contract, timesheet, employee):
        """Test that official employees use progressive tax calculation."""
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
        # Official employees: taxable_income_base excludes non_taxable_overtime_salary
        expected_base = (
            payroll_slip.gross_income
            - payroll_slip.non_taxable_travel_expense
            - payroll_slip.employee_social_insurance
            - payroll_slip.employee_health_insurance
            - payroll_slip.employee_unemployment_insurance
            - payroll_slip.non_taxable_overtime_salary
        )
        assert payroll_slip.taxable_income_base == expected_base.quantize(Decimal("1"))
        # Tax should be calculated progressively, not flat 10%
        if payroll_slip.taxable_income > 0:
            tax_rate = payroll_slip.personal_income_tax / payroll_slip.gross_income
            assert tax_rate != Decimal("0.10")

    def test_non_official_employee_flat_10_percent_tax(self, payroll_slip, contract, timesheet, employee):
        """Test that non-official employees pay 10% flat tax."""
        # Arrange
        employee.employee_type = EmployeeType.PROBATION
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        # Non-official: taxable_income_base = gross_income
        assert payroll_slip.taxable_income_base == payroll_slip.gross_income
        # Tax = gross_income * 10%
        expected_tax = (payroll_slip.gross_income * Decimal("0.10")).quantize(Decimal("1"))
        assert payroll_slip.personal_income_tax == expected_tax

    def test_intern_employee_flat_10_percent_tax(self, payroll_slip, contract, timesheet, employee):
        """Test that intern employees pay 10% flat tax."""
        # Arrange
        employee.employee_type = EmployeeType.INTERN
        employee.save()

        contract.base_salary = Decimal("15000000")
        contract.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        expected_tax = (payroll_slip.gross_income * Decimal("0.10")).quantize(Decimal("1"))
        assert payroll_slip.personal_income_tax == expected_tax


@pytest.mark.django_db
class TestEmploymentStatusCaching:
    """Test that employment_status field is correctly set."""

    def test_employment_status_reflects_employee_type(self, payroll_slip, contract, timesheet, employee):
        """Test that employment_status is set to employee_type, not contract status."""
        # Arrange
        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.employment_status == EmployeeType.OFFICIAL

    def test_employment_status_for_probation(self, payroll_slip, contract, timesheet, employee):
        """Test employment_status for probation employee."""
        # Arrange
        employee.employee_type = EmployeeType.PROBATION
        employee.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.employment_status == EmployeeType.PROBATION


@pytest.mark.django_db
class TestNewFieldsInSerializers:
    """Test that new fields are properly serialized."""

    def test_payroll_slip_serializer_includes_new_fields(self, payroll_slip, contract, timesheet, employee):
        """Test that PayrollSlipSerializer includes all new fields."""
        # Arrange
        from apps.payroll.api.serializers.payroll_slip import PayrollSlipSerializer

        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        calculator = PayrollCalculationService(payroll_slip)
        calculator.calculate()
        payroll_slip.refresh_from_db()

        # Act
        serializer = PayrollSlipSerializer(payroll_slip)
        data = serializer.data

        # Assert - Check new fields are present
        assert "total_position_income" in data
        assert "actual_working_days_income" in data
        assert "taxable_overtime_salary" in data
        assert "overtime_progress_allowance" in data
        assert "non_taxable_overtime_salary" in data

        # Verify values are serialized correctly
        assert data["total_position_income"] == str(payroll_slip.total_position_income)
        assert data["actual_working_days_income"] == str(payroll_slip.actual_working_days_income)
        assert data["taxable_overtime_salary"] == str(payroll_slip.taxable_overtime_salary)
