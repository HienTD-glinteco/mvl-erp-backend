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
        # Official employees: taxable_income_base excludes non_taxable_overtime_salary and non_taxable_allowance
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
class TestTravelExpenseCalculations:
    """Test travel expense calculations with three expense types."""

    def test_taxable_travel_expense_only(self, payroll_slip, contract, timesheet, employee, travel_expense_factory):
        """Test calculation with only taxable travel expenses."""
        # Arrange
        from apps.payroll.models import TravelExpense

        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.save()

        travel_expense_factory(
            employee=employee,
            month=payroll_slip.salary_period.month,
            expense_type=TravelExpense.ExpenseType.TAXABLE,
            amount=1000000,
        )
        travel_expense_factory(
            employee=employee,
            month=payroll_slip.salary_period.month,
            expense_type=TravelExpense.ExpenseType.TAXABLE,
            amount=500000,
        )

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.taxable_travel_expense == Decimal("1500000")
        assert payroll_slip.non_taxable_travel_expense == Decimal("0")
        assert payroll_slip.travel_expense_by_working_days == Decimal("0")
        assert payroll_slip.total_travel_expense == Decimal("1500000")

    def test_non_taxable_travel_expense_only(
        self, payroll_slip, contract, timesheet, employee, travel_expense_factory
    ):
        """Test calculation with only non-taxable travel expenses."""
        # Arrange
        from apps.payroll.models import TravelExpense

        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.save()

        travel_expense_factory(
            employee=employee,
            month=payroll_slip.salary_period.month,
            expense_type=TravelExpense.ExpenseType.NON_TAXABLE,
            amount=2000000,
        )

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.taxable_travel_expense == Decimal("0")
        assert payroll_slip.non_taxable_travel_expense == Decimal("2000000")
        assert payroll_slip.travel_expense_by_working_days == Decimal("0")
        assert payroll_slip.total_travel_expense == Decimal("2000000")

    def test_by_working_days_travel_expense_only(
        self, payroll_slip, contract, timesheet, employee, travel_expense_factory
    ):
        """Test calculation with only by working days travel expenses."""
        # Arrange
        from apps.payroll.models import TravelExpense

        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.save()

        travel_expense_factory(
            employee=employee,
            month=payroll_slip.salary_period.month,
            expense_type=TravelExpense.ExpenseType.BY_WORKING_DAYS,
            amount=3000000,
        )

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.taxable_travel_expense == Decimal("0")
        assert payroll_slip.non_taxable_travel_expense == Decimal("0")
        assert payroll_slip.travel_expense_by_working_days == Decimal("3000000")
        assert payroll_slip.total_travel_expense == Decimal("3000000")

    def test_mixed_travel_expenses(self, payroll_slip, contract, timesheet, employee, travel_expense_factory):
        """Test calculation with all three types of travel expenses."""
        # Arrange
        from apps.payroll.models import TravelExpense

        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.save()

        travel_expense_factory(
            employee=employee,
            month=payroll_slip.salary_period.month,
            expense_type=TravelExpense.ExpenseType.TAXABLE,
            amount=1000000,
        )
        travel_expense_factory(
            employee=employee,
            month=payroll_slip.salary_period.month,
            expense_type=TravelExpense.ExpenseType.NON_TAXABLE,
            amount=2000000,
        )
        travel_expense_factory(
            employee=employee,
            month=payroll_slip.salary_period.month,
            expense_type=TravelExpense.ExpenseType.BY_WORKING_DAYS,
            amount=3000000,
        )

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.taxable_travel_expense == Decimal("1000000")
        assert payroll_slip.non_taxable_travel_expense == Decimal("2000000")
        assert payroll_slip.travel_expense_by_working_days == Decimal("3000000")
        assert payroll_slip.total_travel_expense == Decimal("6000000")

    def test_by_working_days_expense_in_total_position_income(
        self, payroll_slip, contract, timesheet, employee, travel_expense_factory
    ):
        """Test that by working days expense is included in total position income."""
        # Arrange
        from apps.payroll.models import TravelExpense

        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.kpi_salary = Decimal("2000000")
        contract.lunch_allowance = Decimal("1000000")
        contract.phone_allowance = Decimal("500000")
        contract.other_allowance = Decimal("500000")
        contract.save()

        travel_expense_factory(
            employee=employee,
            month=payroll_slip.salary_period.month,
            expense_type=TravelExpense.ExpenseType.BY_WORKING_DAYS,
            amount=3000000,
        )

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        # total_position_income should include by_working_days expense
        expected = (
            Decimal("20000000")  # base_salary
            + Decimal("1000000")  # lunch_allowance
            + Decimal("500000")  # phone_allowance
            + Decimal("500000")  # other_allowance
            + Decimal("2000000")  # kpi_salary
            + payroll_slip.kpi_bonus
            + payroll_slip.business_progressive_salary
            + Decimal("3000000")  # travel_expense_by_working_days
        )
        assert payroll_slip.total_position_income == expected

    def test_by_working_days_expense_in_business_progressive_calculation(
        self, payroll_slip, contract, timesheet, employee, travel_expense_factory, sales_revenue_factory
    ):
        """Test that by working days expense is deducted in business progressive salary calculation."""
        # Arrange
        from apps.payroll.models import TravelExpense

        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("10000000")
        contract.kpi_salary = Decimal("1000000")
        contract.lunch_allowance = Decimal("500000")
        contract.other_allowance = Decimal("500000")
        contract.save()

        travel_expense_factory(
            employee=employee,
            month=payroll_slip.salary_period.month,
            expense_type=TravelExpense.ExpenseType.BY_WORKING_DAYS,
            amount=2000000,
        )

        # Add sales revenue to trigger business progressive salary
        sales_revenue_factory(
            employee=employee, month=payroll_slip.salary_period.month, revenue=1000000000, transaction_count=10
        )

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        # business_progressive_salary should be:
        # (tier amount) - base_salary - kpi_salary - lunch_allowance - other_allowance - travel_expense_by_working_days
        # tier M3 is 20,000,000 for revenue >= 1B and transactions >= 10
        expected = (
            Decimal("20000000")
            - Decimal("10000000")
            - Decimal("1000000")
            - Decimal("500000")
            - Decimal("500000")
            - Decimal("2000000")
        )
        expected = max(Decimal("0"), expected)
        assert payroll_slip.business_progressive_salary == expected

    def test_gross_income_excludes_by_working_days_expense(
        self, payroll_slip, contract, timesheet, employee, travel_expense_factory
    ):
        """Test that gross income only includes taxable and non-taxable travel expenses."""
        # Arrange
        from apps.payroll.models import TravelExpense

        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.save()

        timesheet.tc1_overtime_hours = Decimal("10.00")
        timesheet.save()

        travel_expense_factory(
            employee=employee,
            month=payroll_slip.salary_period.month,
            expense_type=TravelExpense.ExpenseType.TAXABLE,
            amount=1000000,
        )
        travel_expense_factory(
            employee=employee,
            month=payroll_slip.salary_period.month,
            expense_type=TravelExpense.ExpenseType.NON_TAXABLE,
            amount=2000000,
        )
        travel_expense_factory(
            employee=employee,
            month=payroll_slip.salary_period.month,
            expense_type=TravelExpense.ExpenseType.BY_WORKING_DAYS,
            amount=3000000,
        )

        payroll_slip.salary_period.standard_working_days = Decimal("22.00")
        payroll_slip.salary_period.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        # gross_income = actual_working_days_income + taxable_overtime + non_taxable_overtime
        #                + taxable_travel + non_taxable_travel (NOT by_working_days)
        expected_gross = (
            payroll_slip.actual_working_days_income
            + payroll_slip.taxable_overtime_salary
            + payroll_slip.non_taxable_overtime_salary
            + Decimal("1000000")  # taxable_travel_expense
            + Decimal("2000000")  # non_taxable_travel_expense
        )
        assert payroll_slip.gross_income == expected_gross.quantize(Decimal("1"))


@pytest.mark.django_db
class TestBusinessProgressiveSalaryCalculation:
    """Test business progressive salary calculation logic."""

    def test_no_sales_revenue_returns_m0_grade(self, payroll_slip, contract, timesheet, employee):
        """Test that no sales revenue results in M0 grade and zero progressive salary."""
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
        assert payroll_slip.business_grade == "M0"
        assert payroll_slip.business_progressive_salary == Decimal("0")
        assert payroll_slip.sales_revenue == 0
        assert payroll_slip.sales_transaction_count == 0

    def test_sales_revenue_below_threshold(self, payroll_slip, contract, timesheet, employee, sales_revenue_factory):
        """Test sales revenue below tier threshold."""
        # Arrange
        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.save()

        # M1 requires >= 500M, set to 400M
        sales_revenue_factory(employee=employee, month=payroll_slip.salary_period.month, revenue=400000000)

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.business_grade == "M0"
        assert payroll_slip.business_progressive_salary == Decimal("0")

    def test_sales_revenue_meets_tier_m1(self, payroll_slip, contract, timesheet, employee, sales_revenue_factory):
        """Test sales revenue that meets M1 tier criteria."""
        # Arrange
        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("10000000")
        contract.kpi_salary = Decimal("1000000")
        contract.lunch_allowance = Decimal("500000")
        contract.other_allowance = Decimal("500000")
        contract.save()

        # M1: revenue >= 500M, transactions >= 5, amount = 15M
        sales_revenue_factory(
            employee=employee, month=payroll_slip.salary_period.month, revenue=500000000, transaction_count=5
        )

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.business_grade == "M1"
        # 15M - 10M (base) - 1M (kpi) - 0.5M (lunch) - 0.5M (other) = 3M
        expected = (
            Decimal("15000000") - Decimal("10000000") - Decimal("1000000") - Decimal("500000") - Decimal("500000")
        )
        assert payroll_slip.business_progressive_salary == max(Decimal("0"), expected)

    def test_sales_revenue_meets_highest_tier_m3(
        self, payroll_slip, contract, timesheet, employee, sales_revenue_factory
    ):
        """Test sales revenue that meets M3 tier criteria."""
        # Arrange
        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("10000000")
        contract.kpi_salary = Decimal("1000000")
        contract.lunch_allowance = Decimal("500000")
        contract.other_allowance = Decimal("500000")
        contract.save()

        # M3: revenue >= 1B, transactions >= 10, amount = 20M
        sales_revenue_factory(
            employee=employee, month=payroll_slip.salary_period.month, revenue=1000000000, transaction_count=10
        )

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.business_grade == "M3"
        expected = (
            Decimal("20000000") - Decimal("10000000") - Decimal("1000000") - Decimal("500000") - Decimal("500000")
        )
        assert payroll_slip.business_progressive_salary == max(Decimal("0"), expected)

    def test_business_progressive_negative_becomes_zero(
        self, payroll_slip, contract, timesheet, employee, sales_revenue_factory
    ):
        """Test that negative business progressive salary is capped at zero."""
        # Arrange
        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        # Set very high base salary so progressive would be negative
        contract.base_salary = Decimal("50000000")
        contract.kpi_salary = Decimal("5000000")
        contract.lunch_allowance = Decimal("2000000")
        contract.other_allowance = Decimal("2000000")
        contract.save()

        # M1 tier = 15M, but deductions exceed this
        sales_revenue_factory(
            employee=employee, month=payroll_slip.salary_period.month, revenue=500000000, transaction_count=5
        )

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.business_progressive_salary == Decimal("0")


@pytest.mark.django_db
class TestRecoveryVouchersAndPenalties:
    """Test recovery vouchers and penalty calculations."""

    def test_back_pay_amount_calculation(self, payroll_slip, contract, timesheet, employee, recovery_voucher_factory):
        """Test that back pay amounts are correctly summed."""
        # Arrange
        from apps.payroll.models import RecoveryVoucher

        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.save()

        recovery_voucher_factory(
            employee=employee,
            month=payroll_slip.salary_period.month,
            voucher_type=RecoveryVoucher.VoucherType.BACK_PAY,
            amount=1000000,
        )
        recovery_voucher_factory(
            employee=employee,
            month=payroll_slip.salary_period.month,
            voucher_type=RecoveryVoucher.VoucherType.BACK_PAY,
            amount=500000,
        )

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.back_pay_amount == Decimal("1500000")

    def test_recovery_amount_calculation(self, payroll_slip, contract, timesheet, employee, recovery_voucher_factory):
        """Test that recovery amounts are correctly summed."""
        # Arrange
        from apps.payroll.models import RecoveryVoucher

        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.save()

        recovery_voucher_factory(
            employee=employee,
            month=payroll_slip.salary_period.month,
            voucher_type=RecoveryVoucher.VoucherType.RECOVERY,
            amount=2000000,
        )
        recovery_voucher_factory(
            employee=employee,
            month=payroll_slip.salary_period.month,
            voucher_type=RecoveryVoucher.VoucherType.RECOVERY,
            amount=1000000,
        )

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.recovery_amount == Decimal("3000000")

    def test_unpaid_penalty_detection(self, payroll_slip, contract, timesheet, employee, penalty_ticket_factory):
        """Test that unpaid penalties are detected and flagged."""
        # Arrange
        from apps.payroll.models import PenaltyTicket

        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.save()

        penalty_ticket_factory(
            employee=employee, month=payroll_slip.salary_period.month, status=PenaltyTicket.Status.UNPAID
        )
        penalty_ticket_factory(
            employee=employee, month=payroll_slip.salary_period.month, status=PenaltyTicket.Status.UNPAID
        )

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.has_unpaid_penalty is True
        assert payroll_slip.unpaid_penalty_count == 2
        assert payroll_slip.status == payroll_slip.Status.PENDING

    def test_paid_penalties_do_not_affect_status(
        self, payroll_slip, contract, timesheet, employee, penalty_ticket_factory
    ):
        """Test that paid penalties do not affect payroll slip status."""
        # Arrange
        from apps.payroll.models import PenaltyTicket

        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.save()

        penalty_ticket_factory(
            employee=employee, month=payroll_slip.salary_period.month, status=PenaltyTicket.Status.PAID
        )

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.has_unpaid_penalty is False
        assert payroll_slip.unpaid_penalty_count == 0
        assert payroll_slip.status == payroll_slip.Status.READY


@pytest.mark.django_db
class TestNetSalaryCalculation:
    """Test net salary calculation formula."""

    def test_net_salary_formula(self, payroll_slip, contract, timesheet, employee):
        """Test net salary calculation formula."""
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
        expected_net = (
            payroll_slip.gross_income
            - payroll_slip.employee_social_insurance
            - payroll_slip.employee_health_insurance
            - payroll_slip.employee_unemployment_insurance
            - payroll_slip.employee_union_fee
            - payroll_slip.personal_income_tax
            + payroll_slip.back_pay_amount
            - payroll_slip.recovery_amount
        )
        assert payroll_slip.net_salary == expected_net.quantize(Decimal("1"))

    def test_net_salary_with_recovery_vouchers(
        self, payroll_slip, contract, timesheet, employee, recovery_voucher_factory
    ):
        """Test net salary calculation with recovery vouchers."""
        # Arrange
        from apps.payroll.models import RecoveryVoucher

        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.save()

        recovery_voucher_factory(
            employee=employee,
            month=payroll_slip.salary_period.month,
            voucher_type=RecoveryVoucher.VoucherType.BACK_PAY,
            amount=1000000,
        )
        recovery_voucher_factory(
            employee=employee,
            month=payroll_slip.salary_period.month,
            voucher_type=RecoveryVoucher.VoucherType.RECOVERY,
            amount=500000,
        )

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        expected_net = (
            payroll_slip.gross_income
            - payroll_slip.employee_social_insurance
            - payroll_slip.employee_health_insurance
            - payroll_slip.employee_unemployment_insurance
            - payroll_slip.employee_union_fee
            - payroll_slip.personal_income_tax
            + Decimal("1000000")  # back_pay
            - Decimal("500000")  # recovery
        )
        assert payroll_slip.net_salary == expected_net.quantize(Decimal("1"))


@pytest.mark.django_db
class TestPayrollSlipStatusDetermination:
    """Test payroll slip status determination logic."""

    def test_status_ready_when_all_data_complete(self, payroll_slip, contract, timesheet, employee):
        """Test that status is READY when all required data is present."""
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
        assert payroll_slip.status == payroll_slip.Status.READY
        assert payroll_slip.status_note == ""

    def test_status_pending_when_no_contract(self, payroll_slip, timesheet, employee):
        """Test that status is PENDING when contract is missing."""
        # Arrange - No contract
        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.status == payroll_slip.Status.PENDING
        assert "contract" in payroll_slip.status_note.lower()

    def test_status_pending_when_no_timesheet(self, payroll_slip, contract, employee):
        """Test that status is PENDING when timesheet is missing."""
        # Arrange - No timesheet
        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.status == payroll_slip.Status.PENDING
        assert "timesheet" in payroll_slip.status_note.lower()

    def test_status_pending_when_unpaid_penalties_exist(
        self, payroll_slip, contract, timesheet, employee, penalty_ticket_factory
    ):
        """Test that status is PENDING when unpaid penalties exist."""
        # Arrange
        from apps.payroll.models import PenaltyTicket

        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.save()

        penalty_ticket_factory(
            employee=employee, month=payroll_slip.salary_period.month, status=PenaltyTicket.Status.UNPAID
        )

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.status == payroll_slip.Status.PENDING
        assert "penalties" in payroll_slip.status_note.lower()

    def test_status_preserved_when_hold(self, payroll_slip, contract, timesheet, employee):
        """Test that HOLD status is preserved during recalculation."""
        # Arrange
        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.save()

        payroll_slip.status = payroll_slip.Status.HOLD
        payroll_slip.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.status == payroll_slip.Status.HOLD

    def test_status_skip_calculation_when_delivered(self, payroll_slip, contract, timesheet, employee):
        """Test that calculation is skipped when status is DELIVERED."""
        # Arrange
        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.save()

        # First calculate to get some values
        calculator = PayrollCalculationService(payroll_slip)
        calculator.calculate()

        # Change to DELIVERED
        payroll_slip.status = payroll_slip.Status.DELIVERED
        payroll_slip.save()

        original_net_salary = payroll_slip.net_salary

        # Change contract (should not affect delivered slip)
        contract.base_salary = Decimal("30000000")
        contract.save()

        # Act - Try to recalculate
        calculator = PayrollCalculationService(payroll_slip)
        calculator.calculate()

        # Assert - Values should remain unchanged
        payroll_slip.refresh_from_db()
        assert payroll_slip.net_salary == original_net_salary
        assert payroll_slip.status == payroll_slip.Status.DELIVERED


@pytest.mark.django_db
class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_working_days(self, payroll_slip, contract, timesheet, employee):
        """Test calculation when employee has zero working days."""
        # Arrange
        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.save()

        timesheet.total_working_days = Decimal("0.00")
        timesheet.official_working_days = Decimal("0.00")
        timesheet.probation_working_days = Decimal("0.00")
        timesheet.save()

        payroll_slip.salary_period.standard_working_days = Decimal("22.00")
        payroll_slip.salary_period.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.actual_working_days_income == Decimal("0")
        assert payroll_slip.gross_income >= Decimal("0")

    def test_zero_standard_working_days(self, payroll_slip, contract, timesheet, employee):
        """Test calculation when standard working days is zero."""
        # Arrange
        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.save()

        payroll_slip.salary_period.standard_working_days = Decimal("0.00")
        payroll_slip.salary_period.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.hourly_rate == Decimal("0.00")
        assert payroll_slip.actual_working_days_income == Decimal("0")

    def test_very_high_overtime_hours(self, payroll_slip, contract, timesheet, employee):
        """Test calculation with very high overtime hours."""
        # Arrange
        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.save()

        timesheet.tc3_overtime_hours = Decimal("100.00")
        timesheet.save()

        payroll_slip.salary_period.standard_working_days = Decimal("22.00")
        payroll_slip.salary_period.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.overtime_pay > Decimal("0")
        assert payroll_slip.total_overtime_hours == Decimal("100.00")

    def test_employee_without_position(self, payroll_slip, contract, timesheet, employee):
        """Test calculation when employee has no position assigned."""
        # Arrange
        employee.position = None
        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.position_name == ""
        assert payroll_slip.status == payroll_slip.Status.READY

    def test_employee_without_department(self, payroll_slip, contract, timesheet, employee, department):
        """Test calculation when employee has no department assigned."""
        # Arrange
        # Note: department is required field, so we just verify it's cached correctly
        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        contract.base_salary = Decimal("20000000")
        contract.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.department_name == department.name
        assert payroll_slip.status == payroll_slip.Status.READY


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
        assert "travel_expense_by_working_days" in data

        # Verify values are serialized correctly
        assert data["total_position_income"] == str(payroll_slip.total_position_income)
        assert data["actual_working_days_income"] == str(payroll_slip.actual_working_days_income)
        assert data["taxable_overtime_salary"] == str(payroll_slip.taxable_overtime_salary)
        assert data["travel_expense_by_working_days"] == str(payroll_slip.travel_expense_by_working_days)
