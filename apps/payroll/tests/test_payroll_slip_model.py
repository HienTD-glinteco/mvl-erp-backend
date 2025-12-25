"""Tests for PayrollSlip model and calculation."""

from decimal import Decimal

import pytest

from apps.payroll.models import PayrollSlip, PenaltyTicket
from apps.payroll.services.payroll_calculation import PayrollCalculationService


@pytest.mark.django_db
class TestPayrollSlipModel:
    """Test PayrollSlip model."""

    def test_create_payroll_slip(self, salary_period, employee):
        """Test creating a payroll slip."""
        # Act
        slip = PayrollSlip.objects.create(salary_period=salary_period, employee=employee)

        # Assert
        assert slip.code.startswith("PS-")
        assert slip.salary_period == salary_period
        assert slip.employee == employee
        assert slip.status == PayrollSlip.Status.PENDING

    def test_unique_constraint(self, salary_period, employee):
        """Test unique constraint on salary_period + employee."""
        # Arrange
        PayrollSlip.objects.create(salary_period=salary_period, employee=employee)

        # Act & Assert
        with pytest.raises(Exception):  # Unique constraint violation
            PayrollSlip.objects.create(salary_period=salary_period, employee=employee)


@pytest.mark.django_db
class TestPayrollCalculation:
    """Test payroll calculation logic."""

    def test_calculation_with_full_data(
        self, payroll_slip, contract, timesheet, kpi_assessment, employee
    ):
        """Test payroll calculation with all required data."""
        # Arrange
        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.base_salary == contract.base_salary
        assert payroll_slip.status == PayrollSlip.Status.READY
        assert payroll_slip.gross_income > 0
        assert payroll_slip.net_salary > 0

    def test_calculation_without_contract(self, payroll_slip):
        """Test payroll calculation without contract sets PENDING status."""
        # Arrange
        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.status == PayrollSlip.Status.PENDING
        assert "contract" in payroll_slip.status_note.lower()

    def test_calculation_with_unpaid_penalty(
        self, payroll_slip, contract, timesheet, employee, salary_period
    ):
        """Test that unpaid penalties block payroll (PENDING status)."""
        # Arrange
        PenaltyTicket.objects.create(
            employee=employee,
            month=salary_period.month,
            amount=100000,
            status=PenaltyTicket.Status.UNPAID,
            violation_type=PenaltyTicket.ViolationType.OTHER,
            employee_code=employee.code,
            employee_name=employee.fullname,
        )

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.status == PayrollSlip.Status.PENDING
        assert payroll_slip.has_unpaid_penalty is True
        assert payroll_slip.unpaid_penalty_count == 1
        assert "penalties" in payroll_slip.status_note.lower()

    def test_calculation_with_paid_penalty(
        self, payroll_slip, contract, timesheet, employee, salary_period
    ):
        """Test that paid penalties don't block payroll."""
        # Arrange
        PenaltyTicket.objects.create(
            employee=employee,
            month=salary_period.month,
            amount=100000,
            status=PenaltyTicket.Status.PAID,
            violation_type=PenaltyTicket.ViolationType.OTHER,
            employee_code=employee.code,
            employee_name=employee.fullname,
        )

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.status == PayrollSlip.Status.READY
        assert payroll_slip.has_unpaid_penalty is False
        assert payroll_slip.unpaid_penalty_count == 0

    def test_kpi_bonus_calculation(self, payroll_slip, contract, timesheet, kpi_assessment):
        """Test KPI bonus calculation for different grades."""
        # Arrange
        kpi_assessment.grade_manager = "A"
        kpi_assessment.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.kpi_grade == "A"
        assert payroll_slip.kpi_percentage == Decimal("0.1")
        assert payroll_slip.kpi_bonus == contract.base_salary * Decimal("0.1")

    def test_overtime_calculation(self, payroll_slip, contract, timesheet):
        """Test overtime pay calculation."""
        # Arrange
        timesheet.saturday_in_week_overtime_hours = Decimal("10.00")
        timesheet.sunday_overtime_hours = Decimal("8.00")
        timesheet.holiday_overtime_hours = Decimal("4.00")
        timesheet.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.saturday_inweek_overtime_hours == Decimal("10.00")
        assert payroll_slip.sunday_overtime_hours == Decimal("8.00")
        assert payroll_slip.holiday_overtime_hours == Decimal("4.00")
        assert payroll_slip.total_overtime_hours == Decimal("22.00")
        assert payroll_slip.overtime_pay > 0

    def test_travel_expense_taxable(self, payroll_slip, contract, timesheet, employee, salary_period):
        """Test taxable travel expenses included in gross income."""
        # Arrange
        from apps.payroll.models import TravelExpense

        TravelExpense.objects.create(
            employee=employee,
            month=salary_period.month,
            amount=1000000,
            expense_type=TravelExpense.ExpenseType.TAXABLE,
            name="Business trip",
        )

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.taxable_travel_expense == 1000000
        assert payroll_slip.total_travel_expense == 1000000
        assert payroll_slip.gross_income > contract.base_salary

    def test_uses_period_config_snapshot(self, payroll_slip, contract, timesheet, salary_period):
        """Test that calculation uses period's config snapshot, not latest."""
        # Arrange
        original_si_rate = salary_period.salary_config_snapshot["insurance_contributions"][
            "social_insurance"
        ]["employee_rate"]

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        # Verify it used the snapshot rate
        expected_si = contract.base_salary * Decimal(str(original_si_rate))
        assert payroll_slip.employee_social_insurance == expected_si.quantize(Decimal("1"))


@pytest.mark.django_db
class TestPayrollStatusTransitions:
    """Test payroll slip status transitions."""

    def test_pending_to_ready_when_data_complete(self, payroll_slip_pending, contract, timesheet):
        """Test status changes from PENDING to READY when data is complete."""
        # Arrange
        calculator = PayrollCalculationService(payroll_slip_pending)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip_pending.refresh_from_db()
        assert payroll_slip_pending.status == PayrollSlip.Status.READY

    def test_cannot_move_to_ready_with_unpaid_penalties(
        self, payroll_slip_pending, contract, timesheet, employee, salary_period
    ):
        """Test cannot move to READY with unpaid penalties."""
        # Arrange
        PenaltyTicket.objects.create(
            employee=employee,
            month=salary_period.month,
            amount=100000,
            status=PenaltyTicket.Status.UNPAID,
            violation_type=PenaltyTicket.ViolationType.OTHER,
            employee_code=employee.code,
            employee_name=employee.fullname,
        )

        calculator = PayrollCalculationService(payroll_slip_pending)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip_pending.refresh_from_db()
        assert payroll_slip_pending.status == PayrollSlip.Status.PENDING
