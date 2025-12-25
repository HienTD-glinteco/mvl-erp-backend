"""Tests for penalty management models."""

from datetime import date

import pytest

from apps.payroll.models import PenaltyTicket


@pytest.mark.django_db
class TestPenaltyTicket:
    """Test cases for PenaltyTicket model."""

    def test_create_penalty_ticket(self, employee, user):
        """Test creating a penalty ticket."""
        month = date(2025, 11, 1)

        ticket = PenaltyTicket.objects.create(
            employee=employee,
            employee_code=employee.code,
            employee_name=employee.fullname,
            month=month,
            violation_count=2,
            amount=100000,
            note="Test violation",
            created_by=user,
        )

        assert ticket.id is not None
        assert ticket.employee == employee
        assert ticket.month == month
        assert ticket.violation_count == 2
        assert ticket.amount == 100000
        # Code should be auto-generated after save
        assert ticket.code.startswith("RVF-202511-")
        assert ticket.payment_status == "UNPAID"
        assert ticket.payroll_status == "NOT_CALCULATED"

    def test_penalty_ticket_code_generation(self, employee, user):
        """Test automatic code generation."""
        month = date(2025, 11, 1)

        ticket = PenaltyTicket.objects.create(
            employee=employee,
            employee_code=employee.code,
            employee_name=employee.fullname,
            month=month,
            amount=100000,
            created_by=user,
        )

        # Code should follow RVF-{YYYYMM}-{seq} format
        assert ticket.code.startswith("RVF-202511-")
        assert len(ticket.code) == 15  # RVF-202511-0001

    def test_penalty_ticket_code_uniqueness(self, employee, user):
        """Test that penalty ticket codes are unique."""
        month = date(2025, 11, 1)

        ticket1 = PenaltyTicket.objects.create(
            employee=employee,
            employee_code=employee.code,
            employee_name=employee.fullname,
            month=month,
            amount=100000,
            created_by=user,
        )

        ticket2 = PenaltyTicket.objects.create(
            employee=employee,
            employee_code=employee.code,
            employee_name=employee.fullname,
            month=month,
            amount=50000,
            created_by=user,
        )

        assert ticket1.code != ticket2.code

    def test_penalty_ticket_str(self, penalty_ticket):
        """Test string representation."""
        assert str(penalty_ticket) == f"{penalty_ticket.code} - {penalty_ticket.employee_code}"
