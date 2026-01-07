"""Tests for payroll tasks."""

from datetime import date
from unittest.mock import patch

import pytest

from apps.payroll.models import PayrollSlip, SalaryPeriod
from apps.payroll.tasks import (
    auto_generate_salary_period,
    recalculate_payroll_slip_task,
    send_payroll_email_task,
)


@pytest.mark.django_db
class TestRecalculatePayrollSlipTask:
    """Test recalculate_payroll_slip_task."""

    def test_recalculate_slip(self, payroll_slip, contract, timesheet):
        """Test recalculating a payroll slip."""
        # Arrange
        old_net_salary = payroll_slip.net_salary
        month_str = payroll_slip.salary_period.month.isoformat()

        # Act
        result = recalculate_payroll_slip_task(str(payroll_slip.employee_id), month_str)

        # Assert
        assert "Recalculated payroll" in result
        payroll_slip.refresh_from_db()
        # Calculation should have run
        assert payroll_slip.calculated_at is not None

    def test_no_period(self, employee):
        """Test task with non-existent period."""
        # Act
        result = recalculate_payroll_slip_task(str(employee.id), "2099-01-01")

        # Assert
        assert "No salary period" in result

    def test_completed_period(self, salary_period, payroll_slip, user):
        """Test cannot recalculate completed period."""
        # Arrange
        salary_period.status = SalaryPeriod.Status.COMPLETED
        salary_period.save()
        month_str = salary_period.month.isoformat()

        # Act
        result = recalculate_payroll_slip_task(str(payroll_slip.employee_id), month_str)

        # Assert
        assert "completed" in result.lower()


@pytest.mark.django_db
class TestAutoGenerateSalaryPeriod:
    """Test auto_generate_salary_period task."""

    @patch("apps.payroll.tasks.date")
    def test_runs_on_first_day_of_month(self, mock_date, salary_config, employee):
        """Test task creates previous month period when run on 1st of month."""
        # Arrange - Run on February 1st
        mock_date.today.return_value = date(2024, 2, 1)
        mock_date.side_effect = lambda *args, **kw: date(*args, **kw)

        # Act
        result = auto_generate_salary_period()

        # Assert - Should create period for January (previous month)
        assert "Created salary period for 2024-01-01" in result
        assert SalaryPeriod.objects.filter(month=date(2024, 1, 1)).exists()

    @patch("apps.payroll.tasks.date")
    def test_creates_payroll_slips_and_calculates(self, mock_date, salary_config, employee, contract):
        """Test task creates and calculates payroll slips."""
        # Arrange - Run on February 1st
        mock_date.today.return_value = date(2024, 2, 1)
        mock_date.side_effect = lambda *args, **kw: date(*args, **kw)

        # Act
        result = auto_generate_salary_period()

        # Assert - Should create period for January
        period = SalaryPeriod.objects.get(month=date(2024, 1, 1))
        slip = PayrollSlip.objects.get(salary_period=period, employee=employee)
        assert slip.calculated_at is not None
        assert "calculated all payrolls" in result

    @patch("apps.payroll.tasks.date")
    def test_already_exists(self, mock_date, salary_config, employee):
        """Test task does nothing if period already exists."""
        # Arrange - Run on February 1st, but January period already exists
        mock_date.today.return_value = date(2024, 2, 1)
        mock_date.side_effect = lambda *args, **kw: date(*args, **kw)

        # Create January period first
        SalaryPeriod.objects.create(
            month=date(2024, 1, 1),
            salary_config_snapshot=salary_config.config,
        )

        # Act
        result = auto_generate_salary_period()

        # Assert
        assert "already exists" in result
        assert SalaryPeriod.objects.filter(month=date(2024, 1, 1)).count() == 1


@pytest.mark.django_db
class TestSendPayrollEmailTask:
    """Test send_payroll_email_task."""

    @patch("django.core.mail.send_mail")
    @patch("django.template.loader.render_to_string")
    def test_send_email_success(self, mock_render, mock_send_mail, payroll_slip_ready):
        """Test sending email successfully."""
        # Arrange
        mock_render.return_value = "<html>Test email</html>"
        mock_send_mail.return_value = 1

        # Act
        result = send_payroll_email_task(payroll_slip_ready.id)

        # Assert
        assert "Email sent" in result
        assert mock_send_mail.called
        payroll_slip_ready.refresh_from_db()
        assert payroll_slip_ready.email_sent_at is not None
        assert payroll_slip_ready.need_resend_email is False

    def test_no_employee_email(self, payroll_slip_ready):
        """Test task when employee has no email."""
        # Arrange
        payroll_slip_ready.employee.email = ""
        payroll_slip_ready.employee.save()

        # Act
        result = send_payroll_email_task(payroll_slip_ready.id)

        # Assert
        assert "has no email" in result

    def test_slip_not_found(self):
        """Test task with non-existent slip."""
        # Act
        result = send_payroll_email_task(999999)

        # Assert
        assert "not found" in result

    @patch("django.core.mail.send_mail")
    @patch("django.template.loader.render_to_string")
    def test_email_contains_payroll_data(self, mock_render, mock_send_mail, payroll_slip_ready):
        """Test email contains payroll slip data."""
        # Arrange
        mock_render.return_value = "<html>Test email</html>"
        mock_send_mail.return_value = 1
        payroll_slip_ready.net_salary = 10000000
        payroll_slip_ready.gross_income = 15000000
        payroll_slip_ready.save()

        # Act
        send_payroll_email_task(payroll_slip_ready.id)

        # Assert
        # Check that render_to_string was called with correct context
        assert mock_render.called
        call_args = mock_render.call_args
        context = call_args[0][1]
        assert context["payroll_slip"] == payroll_slip_ready
        assert context["employee"] == payroll_slip_ready.employee
