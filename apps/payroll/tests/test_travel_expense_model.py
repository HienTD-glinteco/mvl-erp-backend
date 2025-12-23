"""Tests for TravelExpense model."""

import json
from datetime import date
from pathlib import Path

import pytest
from django.core.exceptions import ValidationError

from apps.payroll.models import TravelExpense


@pytest.fixture
def travel_expense_samples():
    """Load travel expense sample data from JSON fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "travel_expense_samples.json"
    with open(fixture_path) as f:
        return json.load(f)


@pytest.fixture
def travel_expense(db, employee, user):
    """Create a test travel expense."""
    return TravelExpense.objects.create(
        name="Test travel expense",
        expense_type=TravelExpense.ExpenseType.TAXABLE,
        employee=employee,
        amount=2000000,
        month=date(2025, 11, 1),
        note="Test note",
        created_by=user,
    )


@pytest.mark.django_db
class TestTravelExpenseModel:
    """Test TravelExpense model."""

    def test_create_travel_expense(self, employee, user):
        """Test creating a travel expense."""
        expense = TravelExpense.objects.create(
            name="Client visit",
            expense_type=TravelExpense.ExpenseType.TAXABLE,
            employee=employee,
            amount=2500000,
            month=date(2025, 11, 1),
            note="Taxi and meals",
            created_by=user,
        )

        assert expense.id is not None
        assert expense.code.startswith("TE-202511-")
        assert expense.name == "Client visit"
        assert expense.expense_type == TravelExpense.ExpenseType.TAXABLE
        assert expense.employee == employee
        assert expense.amount == 2500000
        assert expense.month == date(2025, 11, 1)
        assert expense.status == TravelExpense.TravelExpenseStatus.NOT_CALCULATED
        assert expense.note == "Taxi and meals"
        assert expense.created_by == user

    def test_code_auto_generation(self, employee, user):
        """Test that code is auto-generated in format TE-{YYYYMM}-{seq}."""
        expense1 = TravelExpense.objects.create(
            name="Expense 1",
            expense_type=TravelExpense.ExpenseType.TAXABLE,
            employee=employee,
            amount=1000000,
            month=date(2025, 11, 1),
            created_by=user,
        )

        expense2 = TravelExpense.objects.create(
            name="Expense 2",
            expense_type=TravelExpense.ExpenseType.NON_TAXABLE,
            employee=employee,
            amount=2000000,
            month=date(2025, 11, 1),
            created_by=user,
        )

        # Both should have TE-202511- prefix
        assert expense1.code.startswith("TE-202511-")
        assert expense2.code.startswith("TE-202511-")

        # Codes should be different
        assert expense1.code != expense2.code

        # Extract sequence numbers and verify they're incremental
        seq1 = int(expense1.code.split("-")[-1])
        seq2 = int(expense2.code.split("-")[-1])
        assert seq2 == seq1 + 1

    def test_code_generation_different_months(self, employee, user):
        """Test that codes are generated with different prefixes for different months."""
        expense1 = TravelExpense.objects.create(
            name="Nov expense",
            expense_type=TravelExpense.ExpenseType.TAXABLE,
            employee=employee,
            amount=1000000,
            month=date(2025, 11, 1),
            created_by=user,
        )

        expense2 = TravelExpense.objects.create(
            name="Dec expense",
            expense_type=TravelExpense.ExpenseType.TAXABLE,
            employee=employee,
            amount=1000000,
            month=date(2025, 12, 1),
            created_by=user,
        )

        assert expense1.code.startswith("TE-202511-")
        assert expense2.code.startswith("TE-202512-")

    def test_month_normalized_to_first_day(self, employee, user):
        """Test that month is always normalized to first day of month."""
        expense = TravelExpense.objects.create(
            name="Test expense",
            expense_type=TravelExpense.ExpenseType.TAXABLE,
            employee=employee,
            amount=1000000,
            month=date(2025, 11, 15),  # Mid-month date
            created_by=user,
        )

        # Should be normalized to first day
        assert expense.month == date(2025, 11, 1)

    def test_default_status_not_calculated(self, employee, user):
        """Test that status defaults to NOT_CALCULATED."""
        expense = TravelExpense.objects.create(
            name="Test expense",
            expense_type=TravelExpense.ExpenseType.TAXABLE,
            employee=employee,
            amount=1000000,
            month=date(2025, 11, 1),
            created_by=user,
        )

        assert expense.status == TravelExpense.TravelExpenseStatus.NOT_CALCULATED

    def test_reset_status_to_not_calculated(self, travel_expense):
        """Test resetting status to NOT_CALCULATED."""
        # Manually set status to CALCULATED
        travel_expense.status = TravelExpense.TravelExpenseStatus.CALCULATED
        travel_expense.save(update_fields=["status"])

        assert travel_expense.status == TravelExpense.TravelExpenseStatus.CALCULATED

        # Reset status
        travel_expense.reset_status_to_not_calculated()

        assert travel_expense.status == TravelExpense.TravelExpenseStatus.NOT_CALCULATED

    def test_amount_positive_validation(self, employee, user):
        """Test that amount must be positive."""
        expense = TravelExpense(
            name="Test expense",
            expense_type=TravelExpense.ExpenseType.TAXABLE,
            employee=employee,
            amount=0,
            month=date(2025, 11, 1),
            created_by=user,
        )

        with pytest.raises(ValidationError):
            expense.full_clean()

    def test_str_representation(self, travel_expense):
        """Test string representation."""
        expected = f"{travel_expense.code} - {travel_expense.name}"
        assert str(travel_expense) == expected

    def test_ordering(self, employee, user):
        """Test that expenses are ordered by -created_at."""
        expense1 = TravelExpense.objects.create(
            name="First expense",
            expense_type=TravelExpense.ExpenseType.TAXABLE,
            employee=employee,
            amount=1000000,
            month=date(2025, 11, 1),
            created_by=user,
        )

        expense2 = TravelExpense.objects.create(
            name="Second expense",
            expense_type=TravelExpense.ExpenseType.TAXABLE,
            employee=employee,
            amount=2000000,
            month=date(2025, 11, 1),
            created_by=user,
        )

        expenses = list(TravelExpense.objects.all())
        # Should be ordered by newest first
        assert expenses[0] == expense2
        assert expenses[1] == expense1
