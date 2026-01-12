"""Comprehensive tests for Salary Period Management features.

Tests covering:
1. Complete/Uncomplete flow for SalaryPeriod
2. Hold/Unhold flow for PayrollSlip
3. Payment Table (Table 1) and Deferred Table (Table 2) logic
4. Penalty payment in completed periods
5. Carry-over scenarios
6. CRUD protection for completed periods

Following AAA pattern: Arrange, Act, Assert
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError

from apps.payroll.models import PayrollSlip, PenaltyTicket, SalaryPeriod


@pytest.fixture
def salary_config(db):
    """Create a salary config for testing."""
    from apps.payroll.models import SalaryConfig

    config = {
        "insurance_contributions": {
            "employee": {
                "social": "0.08",
                "health": "0.015",
                "unemployment": "0.01",
            },
            "employer": {
                "social": "0.175",
                "health": "0.03",
                "unemployment": "0.01",
                "accident": "0.005",
            },
        },
        "personal_income_tax": {
            "personal_deduction": 11000000,
            "dependent_deduction": 4400000,
        },
        "kpi_salary": {"A": "1.2", "B": "1.0", "C": "0.8", "D": "0.0"},
        "overtime_multipliers": {"weekday": "1.5", "sunday": "2.0", "holiday": "3.0"},
        "business_progressive_salary": {},
    }
    return SalaryConfig.objects.create(config=config)


@pytest.fixture
def salary_period(db, salary_config):
    """Create a test salary period."""
    month = date.today().replace(day=1)
    return SalaryPeriod.objects.create(
        code=f"SP_{month.strftime('%Y%m')}",
        month=month,
        salary_config_snapshot=salary_config.config,
        status=SalaryPeriod.Status.ONGOING,
        standard_working_days=Decimal("22.00"),
    )


@pytest.fixture
def payroll_slip(db, salary_period, employee):
    """Create a test payroll slip."""
    return PayrollSlip.objects.create(
        code=f"PS_{salary_period.month.strftime('%Y%m')}_0001",
        salary_period=salary_period,
        employee=employee,
        employee_code=employee.code,
        employee_name=employee.fullname,
        department_name="Test Department",
        position_name="Test Position",
        status=PayrollSlip.Status.READY,
        net_salary=Decimal("10000000"),
    )


@pytest.fixture
def employee2(db, branch, block, department, position):
    """Create a second test employee."""
    from apps.hrm.constants import EmployeeType
    from apps.hrm.models import Employee
    from apps.payroll.tests.conftest import random_code, random_digits

    suffix = random_code(length=6)
    return Employee.objects.create(
        code=f"E2{suffix}",
        fullname="Jane Smith",
        username=f"emp2{suffix}",
        email=f"emp2{suffix}@example.com",
        status=Employee.Status.ACTIVE,
        code_type=Employee.CodeType.MV,
        employee_type=EmployeeType.OFFICIAL,
        branch=branch,
        block=block,
        department=department,
        position=position,
        start_date=date(2024, 1, 1),
        attendance_code=random_digits(6),
        citizen_id=random_digits(12),
        phone=f"09{random_digits(8)}",
        personal_email=f"emp2{suffix}.personal@example.com",
    )


@pytest.fixture
def pending_slip(db, salary_period, employee2):
    """Create a PENDING payroll slip (different employee from payroll_slip)."""
    return PayrollSlip.objects.create(
        code=f"PS_{salary_period.month.strftime('%Y%m')}_PEND",
        salary_period=salary_period,
        employee=employee2,
        employee_code=employee2.code,
        employee_name=employee2.fullname,
        department_name="Test Department",
        position_name="Test Position",
        status=PayrollSlip.Status.PENDING,
        status_note="Missing contract",
        net_salary=Decimal("5000000"),
    )


class TestSalaryPeriodComplete:
    """Tests for SalaryPeriod.complete() method."""

    @pytest.mark.django_db
    def test_complete_marks_ready_slips_as_delivered(self, salary_period, payroll_slip):
        """READY slips should become DELIVERED when period is completed."""
        # Arrange
        assert payroll_slip.status == PayrollSlip.Status.READY

        # Act
        salary_period.complete()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.status == PayrollSlip.Status.DELIVERED
        assert payroll_slip.delivered_at is not None
        assert payroll_slip.payment_period == salary_period

    @pytest.mark.django_db
    def test_complete_sets_period_status(self, salary_period, payroll_slip):
        """Period status should be COMPLETED."""
        # Arrange & Act
        salary_period.complete()

        # Assert
        salary_period.refresh_from_db()
        assert salary_period.status == SalaryPeriod.Status.COMPLETED
        assert salary_period.completed_at is not None

    @pytest.mark.django_db
    def test_complete_preserves_pending_slips(self, salary_period, pending_slip):
        """PENDING slips should remain PENDING (deferred to Table 2)."""
        # Arrange
        assert pending_slip.status == PayrollSlip.Status.PENDING

        # Act
        salary_period.complete()

        # Assert
        pending_slip.refresh_from_db()
        assert pending_slip.status == PayrollSlip.Status.PENDING

    @pytest.mark.django_db
    def test_complete_updates_statistics(self, salary_period, payroll_slip, pending_slip):
        """Statistics should be updated after complete."""
        # Arrange & Act
        salary_period.complete()

        # Assert
        salary_period.refresh_from_db()
        assert salary_period.delivered_count == 1
        assert salary_period.pending_count == 1
        assert salary_period.deferred_count == 1  # pending slip is deferred


class TestSalaryPeriodUncomplete:
    """Tests for SalaryPeriod.uncomplete() method."""

    @pytest.mark.django_db
    def test_can_uncomplete_returns_true_for_latest_completed_period(self, salary_period):
        """Latest completed period should be uncompletable."""
        # Arrange
        salary_period.complete()

        # Act
        can, reason = salary_period.can_uncomplete()

        # Assert
        assert can is True
        assert reason == ""

    @pytest.mark.django_db
    def test_can_uncomplete_returns_false_if_newer_periods_exist(self, db, salary_config, salary_period):
        """Cannot uncomplete if newer periods exist."""
        # Arrange
        salary_period.complete()

        # Create a newer period
        next_month = salary_period.month.replace(day=1) + timedelta(days=32)
        next_month = next_month.replace(day=1)
        SalaryPeriod.objects.create(
            code=f"SP_{next_month.strftime('%Y%m')}",
            month=next_month,
            salary_config_snapshot=salary_config.config,
            status=SalaryPeriod.Status.ONGOING,
            standard_working_days=Decimal("22.00"),
        )

        # Act
        can, reason = salary_period.can_uncomplete()

        # Assert
        assert can is False
        assert "newer salary periods exist" in reason

    @pytest.mark.django_db
    def test_uncomplete_changes_status_to_ongoing(self, salary_period, payroll_slip):
        """Uncomplete should change status to ONGOING."""
        # Arrange
        salary_period.complete()
        assert salary_period.status == SalaryPeriod.Status.COMPLETED

        # Act
        salary_period.uncomplete()

        # Assert
        salary_period.refresh_from_db()
        assert salary_period.status == SalaryPeriod.Status.ONGOING
        assert salary_period.uncompleted_at is not None

    @pytest.mark.django_db
    def test_uncomplete_preserves_delivered_slips(self, salary_period, payroll_slip):
        """DELIVERED slips should remain DELIVERED after uncomplete."""
        # Arrange
        salary_period.complete()
        payroll_slip.refresh_from_db()
        assert payroll_slip.status == PayrollSlip.Status.DELIVERED

        # Act
        salary_period.uncomplete()

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.status == PayrollSlip.Status.DELIVERED

    @pytest.mark.django_db
    def test_uncomplete_raises_error_if_not_completable(self, db, salary_config, salary_period):
        """Should raise ValidationError if uncomplete is not allowed."""
        # Arrange
        salary_period.complete()

        # Create a newer period
        next_month = salary_period.month.replace(day=1) + timedelta(days=32)
        next_month = next_month.replace(day=1)
        SalaryPeriod.objects.create(
            code=f"SP_{next_month.strftime('%Y%m')}",
            month=next_month,
            salary_config_snapshot=salary_config.config,
            status=SalaryPeriod.Status.ONGOING,
            standard_working_days=Decimal("22.00"),
        )

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            salary_period.uncomplete()

        assert "newer salary periods exist" in str(exc_info.value)


class TestPayrollSlipHold:
    """Tests for PayrollSlip.hold() method."""

    @pytest.mark.django_db
    def test_hold_changes_ready_slip_to_hold(self, payroll_slip):
        """READY slip can be put on hold."""
        # Arrange
        assert payroll_slip.status == PayrollSlip.Status.READY

        # Act
        payroll_slip.hold(reason="Verification required", user=None)

        # Assert
        assert payroll_slip.status == PayrollSlip.Status.HOLD
        assert payroll_slip.hold_reason == "Verification required"
        assert payroll_slip.held_at is not None

    @pytest.mark.django_db
    def test_hold_changes_pending_slip_to_hold(self, pending_slip):
        """PENDING slip can be put on hold."""
        # Arrange
        assert pending_slip.status == PayrollSlip.Status.PENDING

        # Act
        pending_slip.hold(reason="Document check", user=None)

        # Assert
        assert pending_slip.status == PayrollSlip.Status.HOLD

    @pytest.mark.django_db
    def test_hold_requires_reason(self, payroll_slip):
        """Hold requires a reason."""
        # Arrange & Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            payroll_slip.hold(reason="", user=None)

        assert "Hold reason is required" in str(exc_info.value)

    @pytest.mark.django_db
    def test_can_hold_delivered_slip(self, salary_period, payroll_slip):
        """CAN hold a DELIVERED slip (any status except HOLD can be held)."""
        # Arrange
        salary_period.complete()
        payroll_slip.refresh_from_db()
        assert payroll_slip.status == PayrollSlip.Status.DELIVERED

        # Act
        payroll_slip.hold(reason="Need to hold for review", user=None)

        # Assert
        payroll_slip.refresh_from_db()
        assert payroll_slip.status == PayrollSlip.Status.HOLD
        assert payroll_slip.hold_reason == "Need to hold for review"

    @pytest.mark.django_db
    def test_cannot_hold_already_held_slip(self, salary_period, payroll_slip):
        """Cannot hold a slip that is already on HOLD."""
        # Arrange
        payroll_slip.hold(reason="First hold", user=None)
        assert payroll_slip.status == PayrollSlip.Status.HOLD

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            payroll_slip.hold(reason="Second hold", user=None)

        assert "already on HOLD" in str(exc_info.value)


class TestPayrollSlipUnhold:
    """Tests for PayrollSlip.unhold() method."""

    @pytest.mark.django_db
    def test_unhold_triggers_recalculation(self, salary_period, payroll_slip):
        """Unhold should trigger recalculation."""
        # Arrange
        payroll_slip.hold(reason="Test", user=None)
        assert payroll_slip.status == PayrollSlip.Status.HOLD

        # Act - mock recalculation since we don't have all data
        with patch.object(payroll_slip, "_recalculate_and_update_status"):
            payroll_slip.unhold(user=None)

        # Assert
        assert payroll_slip.hold_reason == ""
        assert payroll_slip.held_at is None

    @pytest.mark.django_db
    def test_cannot_unhold_non_hold_slip(self, payroll_slip):
        """Cannot unhold a slip that is not on hold."""
        # Arrange
        assert payroll_slip.status == PayrollSlip.Status.READY

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            payroll_slip.unhold(user=None)

        assert "Cannot unhold slip with status READY" in str(exc_info.value)


class TestIsCarriedOverProperty:
    """Tests for PayrollSlip.is_carried_over property."""

    @pytest.mark.django_db
    def test_is_carried_over_false_when_no_payment_period(self, payroll_slip):
        """is_carried_over should be False when payment_period is None."""
        # Arrange
        payroll_slip.payment_period = None

        # Act & Assert
        assert payroll_slip.is_carried_over is False

    @pytest.mark.django_db
    def test_is_carried_over_false_when_same_period(self, salary_period, payroll_slip):
        """is_carried_over should be False when payment_period == salary_period."""
        # Arrange
        payroll_slip.payment_period = salary_period

        # Act & Assert
        assert payroll_slip.is_carried_over is False

    @pytest.mark.django_db
    def test_is_carried_over_true_when_different_period(self, db, salary_config, salary_period, payroll_slip):
        """is_carried_over should be True when payment_period != salary_period."""
        # Arrange
        next_month = salary_period.month.replace(day=1) + timedelta(days=32)
        next_month = next_month.replace(day=1)
        new_period = SalaryPeriod.objects.create(
            code=f"SP_{next_month.strftime('%Y%m')}",
            month=next_month,
            salary_config_snapshot=salary_config.config,
            status=SalaryPeriod.Status.ONGOING,
            standard_working_days=Decimal("22.00"),
        )
        payroll_slip.payment_period = new_period
        payroll_slip.save()

        # Act & Assert
        assert payroll_slip.is_carried_over is True


class TestPaymentTableLogic:
    """Tests for Payment Table (Table 1) query logic."""

    @pytest.mark.django_db
    def test_payment_table_ongoing_returns_ready_slips(self, salary_period, payroll_slip, pending_slip):
        """For ONGOING period, Table 1 should return READY slips."""
        # Arrange
        from django.db.models import Q

        # Act
        queryset = PayrollSlip.objects.filter(
            Q(salary_period=salary_period, status=PayrollSlip.Status.READY)
            | Q(payment_period=salary_period, status=PayrollSlip.Status.READY)
        )

        # Assert
        assert payroll_slip in queryset
        assert pending_slip not in queryset

    @pytest.mark.django_db
    def test_payment_table_completed_returns_delivered_slips(self, salary_period, payroll_slip):
        """For COMPLETED period, Table 1 should return DELIVERED slips with payment_period=this."""
        # Arrange
        salary_period.complete()
        payroll_slip.refresh_from_db()

        # Act
        queryset = PayrollSlip.objects.filter(payment_period=salary_period, status=PayrollSlip.Status.DELIVERED)

        # Assert
        assert payroll_slip in queryset


class TestDeferredTableLogic:
    """Tests for Deferred Table (Table 2) query logic."""

    @pytest.mark.django_db
    def test_deferred_table_ongoing_returns_pending_hold_slips(self, salary_period, payroll_slip, pending_slip):
        """For ONGOING period, Table 2 should return PENDING/HOLD slips."""
        # Arrange - put one slip on hold
        payroll_slip.hold(reason="Test", user=None)

        # Act
        queryset = PayrollSlip.objects.filter(
            salary_period=salary_period,
            status__in=[PayrollSlip.Status.PENDING, PayrollSlip.Status.HOLD],
        )

        # Assert
        assert payroll_slip in queryset
        assert pending_slip in queryset

    @pytest.mark.django_db
    def test_deferred_table_completed_includes_ready_slips(self, db, salary_config, salary_period, employee):
        """For COMPLETED period, Table 2 should include READY slips that became ready after completion."""
        # Arrange - create a slip that starts as PENDING
        slip = PayrollSlip.objects.create(
            code=f"PS_{salary_period.month.strftime('%Y%m')}_DEFER",
            salary_period=salary_period,
            employee=employee,
            employee_code=employee.code,
            employee_name=employee.fullname,
            department_name="Test Department",
            position_name="Test Position",
            status=PayrollSlip.Status.PENDING,
            net_salary=Decimal("5000000"),
        )

        # Complete the period
        salary_period.complete()

        # Simulate slip becoming READY after completion (e.g., after penalty payment)
        slip.status = PayrollSlip.Status.READY
        slip.save()

        # Act
        queryset = PayrollSlip.objects.filter(
            salary_period=salary_period,
            status__in=[PayrollSlip.Status.PENDING, PayrollSlip.Status.HOLD, PayrollSlip.Status.READY],
        )

        # Assert
        assert slip in queryset


class TestCRUDProtection:
    """Tests for CRUD protection on completed periods."""

    @pytest.mark.django_db
    def test_travel_expense_blocked_for_completed_period(self, db, salary_period, employee):
        """Cannot create TravelExpense for completed period."""
        from apps.payroll.models import TravelExpense

        # Arrange
        salary_period.complete()

        # Act & Assert - importing the signals triggers the protection
        from apps.payroll.signals import period_protection  # noqa: F401

        with pytest.raises(ValidationError) as exc_info:
            TravelExpense.objects.create(
                employee=employee,
                month=salary_period.month,
                name="Test expense",
                expense_type=TravelExpense.ExpenseType.TAXABLE,
                amount=100000,
            )

        assert "Cannot modify" in str(exc_info.value)
        assert "completed salary period" in str(exc_info.value)

    @pytest.mark.django_db
    def test_penalty_payment_allowed_for_completed_period(self, db, salary_period, employee, user):
        """Penalty status change from UNPAID to PAID is allowed for completed period."""
        # Arrange
        penalty = PenaltyTicket.objects.create(
            employee=employee,
            employee_code=employee.code,
            employee_name=employee.fullname,
            month=salary_period.month,
            violation_type=PenaltyTicket.ViolationType.UNDER_10_MINUTES,
            violation_count=1,
            amount=Decimal("50000"),
            status=PenaltyTicket.Status.UNPAID,
            created_by=user,
        )
        salary_period.complete()

        # Import signals
        from apps.payroll.signals import period_protection  # noqa: F401

        # Act - should NOT raise
        penalty.status = PenaltyTicket.Status.PAID
        penalty.save(update_fields=["status"])

        # Assert
        penalty.refresh_from_db()
        assert penalty.status == PenaltyTicket.Status.PAID


class TestStatisticsUpdate:
    """Tests for statistics update functionality."""

    @pytest.mark.django_db
    def test_update_statistics_calculates_payment_count(self, salary_period, payroll_slip):
        """update_statistics should calculate payment_count correctly."""
        # Arrange & Act
        salary_period.update_statistics()

        # Assert
        assert salary_period.payment_count == 1  # One READY slip

    @pytest.mark.django_db
    def test_update_statistics_calculates_deferred_count(self, salary_period, payroll_slip, pending_slip):
        """update_statistics should calculate deferred_count correctly."""
        # Arrange
        payroll_slip.hold(reason="Test", user=None)

        # Act
        salary_period.update_statistics()

        # Assert
        assert salary_period.deferred_count == 2  # One HOLD + one PENDING


class TestPayrollCalculationServiceUpdates:
    """Tests for PayrollCalculationService updates."""

    @pytest.mark.django_db
    def test_calculation_skipped_for_delivered_slips(self, salary_period, payroll_slip):
        """Calculation should be skipped for DELIVERED slips."""
        from apps.payroll.services.payroll_calculation import PayrollCalculationService

        # Arrange
        salary_period.complete()
        payroll_slip.refresh_from_db()
        assert payroll_slip.status == PayrollSlip.Status.DELIVERED
        original_net = payroll_slip.net_salary

        # Act
        calculator = PayrollCalculationService(payroll_slip)
        calculator.calculate()

        # Assert - nothing should change
        payroll_slip.refresh_from_db()
        assert payroll_slip.net_salary == original_net

    @pytest.mark.django_db
    def test_hold_status_preserved_during_recalculation(self, salary_period, payroll_slip):
        """HOLD status should be preserved during recalculation."""
        from apps.payroll.services.payroll_calculation import PayrollCalculationService

        # Arrange
        payroll_slip.hold(reason="Test", user=None)
        assert payroll_slip.status == PayrollSlip.Status.HOLD

        # Act - mock internal methods since we don't have full data
        with patch.object(PayrollCalculationService, "_cache_employee_data"):
            with patch.object(PayrollCalculationService, "_get_active_contract", return_value=None):
                with patch.object(PayrollCalculationService, "_set_zero_salary_fields"):
                    with patch.object(PayrollCalculationService, "_calculate_kpi_bonus"):
                        with patch.object(PayrollCalculationService, "_get_timesheet", return_value=None):
                            with patch.object(PayrollCalculationService, "_process_timesheet_data"):
                                with patch.object(PayrollCalculationService, "_calculate_travel_expenses"):
                                    with patch.object(
                                        PayrollCalculationService, "_calculate_business_progressive_salary"
                                    ):
                                        with patch.object(PayrollCalculationService, "_calculate_overtime_pay"):
                                            with patch.object(PayrollCalculationService, "_calculate_gross_income"):
                                                with patch.object(
                                                    PayrollCalculationService, "_calculate_insurance_contributions"
                                                ):
                                                    with patch.object(
                                                        PayrollCalculationService, "_calculate_personal_income_tax"
                                                    ):
                                                        with patch.object(
                                                            PayrollCalculationService, "_process_recovery_vouchers"
                                                        ):
                                                            with patch.object(
                                                                PayrollCalculationService, "_calculate_net_salary"
                                                            ):
                                                                with patch.object(
                                                                    PayrollCalculationService,
                                                                    "_check_unpaid_penalties",
                                                                ):
                                                                    with patch.object(
                                                                        PayrollCalculationService,
                                                                        "_update_related_models_status",
                                                                    ):
                                                                        calculator = PayrollCalculationService(
                                                                            payroll_slip
                                                                        )
                                                                        calculator.calculate()

        # Assert - status should still be HOLD
        assert payroll_slip.status == PayrollSlip.Status.HOLD
