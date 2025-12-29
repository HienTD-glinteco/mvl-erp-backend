"""Tests for new salary period features - deadlines, statistics, async operations."""

from datetime import date
from decimal import Decimal

import pytest

from apps.payroll.models import (
    PayrollSlip,
    PenaltyTicket,
    RecoveryVoucher,
    SalaryPeriod,
    TravelExpense,
)


@pytest.mark.django_db
class TestSalaryPeriodDeadlines:
    """Test salary period deadline fields."""

    def test_default_deadlines_set_on_creation(self, salary_config):
        """Test that default deadlines are set when creating a period."""
        # Arrange
        month = date(2024, 1, 1)

        # Act
        period = SalaryPeriod.objects.create(
            month=month,
            salary_config_snapshot=salary_config.config,
        )

        # Assert
        assert period.proposal_deadline == date(2024, 2, 2)  # 2nd of next month
        assert period.kpi_assessment_deadline == date(2024, 2, 5)  # 5th of next month

    def test_custom_deadlines(self, salary_config):
        """Test creating period with custom deadlines."""
        # Arrange
        month = date(2024, 1, 1)
        custom_proposal_deadline = date(2024, 2, 3)
        custom_kpi_deadline = date(2024, 2, 7)

        # Act
        period = SalaryPeriod.objects.create(
            month=month,
            salary_config_snapshot=salary_config.config,
            proposal_deadline=custom_proposal_deadline,
            kpi_assessment_deadline=custom_kpi_deadline,
        )

        # Assert
        assert period.proposal_deadline == custom_proposal_deadline
        assert period.kpi_assessment_deadline == custom_kpi_deadline


@pytest.mark.django_db
class TestSalaryPeriodStatistics:
    """Test salary period statistics auto-update."""

    def test_update_statistics_recovery(self, salary_period, employee):
        """Test statistics update for recovery vouchers."""
        # Arrange - Create recovery voucher
        RecoveryVoucher.objects.create(
            employee=employee,
            month=salary_period.month,
            voucher_type=RecoveryVoucher.VoucherType.RECOVERY,
            amount=1000000,
        )

        # Act
        salary_period.update_statistics()

        # Assert
        assert salary_period.employees_need_recovery == 1

    def test_update_statistics_penalties(self, salary_period, employee):
        """Test statistics update for penalty tickets."""
        # Arrange - Create penalty tickets
        PenaltyTicket.objects.create(
            employee=employee,
            month=salary_period.month,
            amount=100000,
            employee_code=employee.code,
            employee_name=employee.fullname,
            status=PenaltyTicket.Status.PAID,
        )

        # Act
        salary_period.update_statistics()

        # Assert
        assert salary_period.employees_with_penalties == 1
        assert salary_period.employees_paid_penalties == 1

    def test_update_statistics_travel(self, salary_period, employee):
        """Test statistics update for travel expenses."""
        # Arrange
        TravelExpense.objects.create(
            employee=employee,
            month=salary_period.month,
            amount=500000,
            expense_type=TravelExpense.ExpenseType.TAXABLE,
        )

        # Act
        salary_period.update_statistics()

        # Assert
        assert salary_period.employees_with_travel == 1

    def test_update_statistics_email(self, salary_period, payroll_slip):
        """Test statistics update for email needs."""
        # Arrange
        payroll_slip.need_resend_email = True
        payroll_slip.save()

        # Act
        salary_period.update_statistics()

        # Assert
        assert salary_period.employees_need_email == 1

    def test_update_statistics_payroll_aggregates(self, salary_period, employee, employee_ready):
        """Test statistics update for payroll slip aggregates."""
        # Arrange - Create payroll slips with different statuses
        from apps.payroll.models import PayrollSlip

        # Create first slip
        slip1 = PayrollSlip.objects.create(
            salary_period=salary_period,
            employee=employee,
        )
        slip1.status = PayrollSlip.Status.PENDING
        slip1.gross_income = Decimal("10000000")
        slip1.net_salary = Decimal("8000000")
        slip1.save(update_fields=["status", "gross_income", "net_salary"])

        # Create second slip with different employee
        slip2 = PayrollSlip.objects.create(
            salary_period=salary_period,
            employee=employee_ready,
        )
        slip2.status = PayrollSlip.Status.READY
        slip2.gross_income = Decimal("15000000")
        slip2.net_salary = Decimal("12000000")
        slip2.save(update_fields=["status", "gross_income", "net_salary"])

        # Act
        salary_period.update_statistics()

        # Assert
        assert salary_period.pending_count == 1
        assert salary_period.ready_count == 1
        assert salary_period.hold_count == 0
        assert salary_period.delivered_count == 0
        assert salary_period.total_gross_income == Decimal("25000000")
        assert salary_period.total_net_salary == Decimal("20000000")


@pytest.mark.django_db
class TestSalaryPeriodComplete:
    """Test salary period complete action."""

    def test_complete_without_check(self, salary_period, payroll_slip_ready, payroll_slip_pending, user):
        """Test period can complete even with pending slips."""
        # Act - Should not raise error even with pending slips
        salary_period.complete(user=user)

        # Assert
        assert salary_period.status == SalaryPeriod.Status.COMPLETED
        assert salary_period.completed_by == user
        assert salary_period.completed_at is not None

        # Only READY slips become DELIVERED
        payroll_slip_ready.refresh_from_db()
        assert payroll_slip_ready.status == PayrollSlip.Status.DELIVERED

        # PENDING slips remain PENDING
        payroll_slip_pending.refresh_from_db()
        assert payroll_slip_pending.status == PayrollSlip.Status.PENDING


@pytest.mark.django_db
class TestStatisticsSignals:
    """Test that statistics auto-update on model changes."""

    def test_penalty_change_updates_stats(self, salary_period, employee):
        """Test penalty ticket change triggers statistics update."""
        # Arrange - Get initial stats
        salary_period.update_statistics()
        initial_penalty_count = salary_period.employees_with_penalties

        # Act - Create penalty
        PenaltyTicket.objects.create(
            employee=employee,
            month=salary_period.month,
            amount=100000,
            employee_code=employee.code,
            employee_name=employee.fullname,
        )

        # Assert - Stats should auto-update via signal
        salary_period.refresh_from_db()
        assert salary_period.employees_with_penalties == initial_penalty_count + 1

    def test_recovery_change_updates_stats(self, salary_period, employee):
        """Test recovery voucher change triggers statistics update."""
        # Act
        RecoveryVoucher.objects.create(
            employee=employee,
            month=salary_period.month,
            voucher_type=RecoveryVoucher.VoucherType.RECOVERY,
            amount=1000000,
        )

        # Assert
        salary_period.refresh_from_db()
        assert salary_period.employees_need_recovery == 1

    def test_payroll_slip_change_updates_aggregates(self, salary_period, employee):
        """Test payroll slip changes trigger aggregate statistics update."""
        from apps.payroll.models import PayrollSlip

        # Arrange - Create initial slip
        slip = PayrollSlip.objects.create(
            salary_period=salary_period,
            employee=employee,
        )
        slip.status = PayrollSlip.Status.PENDING
        slip.gross_income = Decimal("10000000")
        slip.net_salary = Decimal("8000000")
        slip.save(update_fields=["status", "gross_income", "net_salary"])

        # Assert - Stats should auto-update
        salary_period.refresh_from_db()
        assert salary_period.pending_count == 1
        assert salary_period.total_gross_income == Decimal("10000000")
        assert salary_period.total_net_salary == Decimal("8000000")

        # Act - Update status
        slip.status = PayrollSlip.Status.READY
        slip.save(update_fields=["status"])

        # Assert - Stats should auto-update on status change
        salary_period.refresh_from_db()
        assert salary_period.pending_count == 0
        assert salary_period.ready_count == 1

        # Act - Update salary amounts
        slip.gross_income = Decimal("12000000")
        slip.net_salary = Decimal("9000000")
        slip.save(update_fields=["gross_income", "net_salary"])

        # Assert - Stats should auto-update on salary change
        salary_period.refresh_from_db()
        assert salary_period.total_gross_income == Decimal("12000000")
        assert salary_period.total_net_salary == Decimal("9000000")

    def test_payroll_slip_delete_updates_aggregates(self, salary_period, employee):
        """Test payroll slip deletion triggers aggregate statistics update."""
        from apps.payroll.models import PayrollSlip

        # Arrange - Create slip
        slip = PayrollSlip.objects.create(
            salary_period=salary_period,
            employee=employee,
        )
        slip.status = PayrollSlip.Status.READY
        slip.gross_income = Decimal("10000000")
        slip.net_salary = Decimal("8000000")
        slip.save(update_fields=["status", "gross_income", "net_salary"])

        # Verify initial state
        salary_period.refresh_from_db()
        assert salary_period.ready_count == 1
        assert salary_period.total_gross_income == Decimal("10000000")

        # Act - Delete slip
        slip.delete()

        # Assert - Stats should auto-update on deletion
        salary_period.refresh_from_db()
        assert salary_period.ready_count == 0
        assert salary_period.total_gross_income == Decimal("0")
        assert salary_period.total_net_salary == Decimal("0")


@pytest.mark.django_db
class TestProposalDeadlineValidation:
    """Test proposal deadline validation.

    Note: Full tests are in test_deadline_validation_signals.py
    which test the actual signal behavior.
    """

    def test_proposal_deadline_exists(self, salary_period):
        """Test that proposal deadline field exists and has default value."""
        # Assert
        assert salary_period.proposal_deadline is not None
        assert salary_period.proposal_deadline.day == 2  # Default: 2nd of next month


@pytest.mark.django_db
class TestKPIAssessmentDeadlineValidation:
    """Test KPI assessment deadline validation."""

    def test_kpi_after_deadline_rejected(self, salary_period, kpi_assessment_period):
        """Test KPI assessment after deadline is rejected."""
        # This is tested in test_deadline_validation_signals.py
        # which has the proper signal tests
        pass
