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
        slip.refresh_from_db()

        # Assert - After signal, code should be generated in format PS_YYYYMM_NNNN
        assert slip.code.startswith("PS_")
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

    def test_calculation_with_full_data(self, payroll_slip, contract, timesheet, kpi_assessment, employee):
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

    def test_calculation_without_contract(self, payroll_slip, employee):
        """Test payroll calculation without contract calculates with 0 salary fields."""
        # Arrange
        # Ensure no contract exists for this employee
        from apps.hrm.models import Contract

        Contract.objects.filter(employee=employee).delete()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        # Should calculate normally but with 0 salary fields
        assert payroll_slip.base_salary == 0
        assert payroll_slip.kpi_salary == 0
        assert payroll_slip.lunch_allowance == 0
        assert payroll_slip.phone_allowance == 0
        assert payroll_slip.other_allowance == 0
        # Gross income might still have travel expenses or other components
        # Net salary calculation should still work
        # Employee info should still be cached
        assert payroll_slip.employee_code
        assert payroll_slip.employee_name
        # Should be marked as PENDING due to missing contract
        assert payroll_slip.status == PayrollSlip.Status.PENDING
        assert "contract" in payroll_slip.status_note.lower()

    def test_calculation_with_unpaid_penalty(self, payroll_slip, contract, timesheet, employee, salary_period):
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

    def test_calculation_with_paid_penalty(self, payroll_slip, contract, timesheet, employee, salary_period):
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
        timesheet.tc1_overtime_hours = Decimal("10.00")
        timesheet.tc2_overtime_hours = Decimal("8.00")
        timesheet.tc3_overtime_hours = Decimal("4.00")
        timesheet.save()

        calculator = PayrollCalculationService(payroll_slip)

        # Act
        calculator.calculate()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.tc1_overtime_hours == Decimal("10.00")
        assert payroll_slip.tc2_overtime_hours == Decimal("8.00")
        assert payroll_slip.tc3_overtime_hours == Decimal("4.00")
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
        original_si_rate = salary_period.salary_config_snapshot["insurance_contributions"]["social_insurance"][
            "employee_rate"
        ]

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


@pytest.mark.django_db
class TestPayrollSlipCodeGeneration:
    """Test payroll slip code generation."""

    def test_code_format(self, salary_period, employee):
        """Test code is generated in format PS_YYYYMM_ID."""
        # Act
        slip = PayrollSlip.objects.create(salary_period=salary_period, employee=employee)

        # Assert
        assert slip.code.startswith("PS_")
        # Format should be PS_YYYYMM_NNNN
        parts = slip.code.split("_")
        assert len(parts) == 3
        assert parts[0] == "PS"
        assert len(parts[1]) == 6  # YYYYMM
        assert len(parts[2]) == 4  # ID with padding

    def test_code_includes_month(self, salary_period, employee):
        """Test code includes the salary period month."""
        # Act
        slip = PayrollSlip.objects.create(salary_period=salary_period, employee=employee)

        # Assert
        month_str = salary_period.month.strftime("%Y%m")
        assert month_str in slip.code


@pytest.mark.django_db
class TestPayrollSlipColoredValue:
    """Test colored value for payroll slip status."""

    def test_colored_status_pending(self, payroll_slip_pending):
        """Test colored status for PENDING status."""
        # Act
        colored_status = payroll_slip_pending.get_colored_value("status")

        # Assert
        assert colored_status["value"] == PayrollSlip.Status.PENDING
        assert colored_status["variant"] is not None

    def test_colored_status_ready(self, payroll_slip_ready):
        """Test colored status for READY status."""
        # Act
        colored_status = payroll_slip_ready.get_colored_value("status")

        # Assert
        assert colored_status["value"] == PayrollSlip.Status.READY
        assert colored_status["variant"] is not None

    def test_colored_status_hold(self, payroll_slip):
        """Test colored status for HOLD status."""
        # Arrange
        payroll_slip.status = PayrollSlip.Status.HOLD
        payroll_slip.status_note = "Test hold"
        payroll_slip.save()

        # Act
        colored_status = payroll_slip.get_colored_value("status")

        # Assert
        assert colored_status["value"] == PayrollSlip.Status.HOLD
        assert colored_status["variant"] is not None

    def test_colored_status_delivered(self, payroll_slip_ready, user):
        """Test colored status for DELIVERED status."""
        # Arrange
        payroll_slip_ready.status = PayrollSlip.Status.DELIVERED
        payroll_slip_ready.delivered_by = user
        payroll_slip_ready.save()

        # Act
        colored_status = payroll_slip_ready.get_colored_value("status")

        # Assert
        assert colored_status["value"] == PayrollSlip.Status.DELIVERED
        assert colored_status["variant"] is not None
