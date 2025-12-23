"""Tests for TravelExpenseSerializer."""

import json
from datetime import date
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model

from apps.payroll.api.serializers import TravelExpenseSerializer
from apps.payroll.models import TravelExpense

User = get_user_model()


@pytest.fixture
def travel_expense_samples():
    """Load travel expense sample data from JSON fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "travel_expense_samples.json"
    with open(fixture_path) as f:
        return json.load(f)


@pytest.mark.django_db
class TestTravelExpenseSerializer:
    """Test TravelExpenseSerializer."""

    def test_serialize_travel_expense(self, employee, user):
        """Test serializing a travel expense."""
        expense = TravelExpense.objects.create(
            name="Client visit",
            expense_type=TravelExpense.ExpenseType.TAXABLE,
            employee=employee,
            amount=2500000,
            month=date(2025, 11, 1),
            note="Taxi and meals",
            created_by=user,
        )

        serializer = TravelExpenseSerializer(expense)
        data = serializer.data

        assert data["name"] == "Client visit"
        assert data["expense_type"] == "TAXABLE"
        assert data["amount"] == 2500000
        assert data["month"] == "11/2025"
        assert data["status"] == "NOT_CALCULATED"
        assert data["note"] == "Taxi and meals"

    def test_deserialize_and_create(self, employee, user, travel_expense_samples):
        """Test deserializing and creating a travel expense."""
        data = {
            "name": "Conference trip",
            "expense_type": "NON_TAXABLE",
            "employee_id": employee.id,
            "amount": 5000000,
            "month": "12/2025",
            "note": "Annual conference",
        }

        serializer = TravelExpenseSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

        expense = serializer.save(created_by=user)

        assert expense.name == "Conference trip"
        assert expense.expense_type == TravelExpense.ExpenseType.NON_TAXABLE
        assert expense.employee == employee
        assert expense.amount == 5000000
        assert expense.month == date(2025, 12, 1)
        assert expense.note == "Annual conference"
        assert expense.status == TravelExpense.TravelExpenseStatus.NOT_CALCULATED

    def test_month_validation_mm_yyyy_format(self, employee):
        """Test month validation for MM/YYYY format."""
        data = {
            "name": "Test expense",
            "expense_type": "TAXABLE",
            "employee_id": employee.id,
            "amount": 1000000,
            "month": "11/2025",
        }

        serializer = TravelExpenseSerializer(data=data)
        assert serializer.is_valid()

    def test_month_validation_invalid_format(self, employee):
        """Test month validation rejects invalid format."""
        data = {
            "name": "Test expense",
            "expense_type": "TAXABLE",
            "employee_id": employee.id,
            "amount": 1000000,
            "month": "2025-11",  # Invalid format
        }

        serializer = TravelExpenseSerializer(data=data)
        assert not serializer.is_valid()
        assert "month" in serializer.errors

    def test_month_validation_invalid_month(self, employee):
        """Test month validation rejects invalid month."""
        data = {
            "name": "Test expense",
            "expense_type": "TAXABLE",
            "employee_id": employee.id,
            "amount": 1000000,
            "month": "13/2025",  # Invalid month
        }

        serializer = TravelExpenseSerializer(data=data)
        assert not serializer.is_valid()
        assert "month" in serializer.errors

    def test_name_required(self, employee):
        """Test that name is required."""
        data = {
            "expense_type": "TAXABLE",
            "employee_id": employee.id,
            "amount": 1000000,
            "month": "11/2025",
        }

        serializer = TravelExpenseSerializer(data=data)
        assert not serializer.is_valid()
        assert "name" in serializer.errors

    def test_name_max_length(self, employee):
        """Test that name has max length validation."""
        data = {
            "name": "x" * 251,  # Exceeds 250 char limit
            "expense_type": "TAXABLE",
            "employee_id": employee.id,
            "amount": 1000000,
            "month": "11/2025",
        }

        serializer = TravelExpenseSerializer(data=data)
        assert not serializer.is_valid()
        assert "name" in serializer.errors

    def test_amount_required(self, employee):
        """Test that amount is required."""
        data = {
            "name": "Test expense",
            "expense_type": "TAXABLE",
            "employee_id": employee.id,
            "month": "11/2025",
        }

        serializer = TravelExpenseSerializer(data=data)
        assert not serializer.is_valid()
        assert "amount" in serializer.errors

    def test_amount_positive(self, employee):
        """Test that amount must be positive."""
        data = {
            "name": "Test expense",
            "expense_type": "TAXABLE",
            "employee_id": employee.id,
            "amount": 0,
            "month": "11/2025",
        }

        serializer = TravelExpenseSerializer(data=data)
        assert not serializer.is_valid()
        assert "amount" in serializer.errors

    def test_employee_required(self):
        """Test that employee is required."""
        data = {
            "name": "Test expense",
            "expense_type": "TAXABLE",
            "amount": 1000000,
            "month": "11/2025",
        }

        serializer = TravelExpenseSerializer(data=data)
        assert not serializer.is_valid()
        assert "employee_id" in serializer.errors

    def test_employee_must_be_active(self, employee):
        """Test that employee must be active."""
        employee.status = "resigned"
        employee.save()

        data = {
            "name": "Test expense",
            "expense_type": "TAXABLE",
            "employee_id": employee.id,
            "amount": 1000000,
            "month": "11/2025",
        }

        serializer = TravelExpenseSerializer(data=data)
        assert not serializer.is_valid()
        assert "employee_id" in serializer.errors

    def test_update_resets_status(self, employee, user):
        """Test that updating an expense resets status to NOT_CALCULATED."""
        expense = TravelExpense.objects.create(
            name="Original expense",
            expense_type=TravelExpense.ExpenseType.TAXABLE,
            employee=employee,
            amount=2000000,
            month=date(2025, 11, 1),
            created_by=user,
        )

        # Manually set status to CALCULATED
        expense.status = TravelExpense.TravelExpenseStatus.CALCULATED
        expense.save(update_fields=["status"])

        # Update expense
        data = {
            "name": "Updated expense",
            "expense_type": "TAXABLE",
            "employee_id": employee.id,
            "amount": 2500000,
            "month": "11/2025",
        }

        serializer = TravelExpenseSerializer(expense, data=data)
        assert serializer.is_valid()

        updated_expense = serializer.save(updated_by=user)

        # Status should be reset to NOT_CALCULATED
        assert updated_expense.status == TravelExpense.TravelExpenseStatus.NOT_CALCULATED

    def test_code_is_read_only(self, employee, user):
        """Test that code field is read-only."""
        expense = TravelExpense.objects.create(
            name="Test expense",
            expense_type=TravelExpense.ExpenseType.TAXABLE,
            employee=employee,
            amount=2000000,
            month=date(2025, 11, 1),
            created_by=user,
        )

        original_code = expense.code

        # Try to update code
        data = {
            "code": "TE-999999-9999",
            "name": "Updated expense",
            "expense_type": "TAXABLE",
            "employee_id": employee.id,
            "amount": 2500000,
            "month": "11/2025",
        }

        serializer = TravelExpenseSerializer(expense, data=data)
        assert serializer.is_valid()

        updated_expense = serializer.save(updated_by=user)

        # Code should remain unchanged
        assert updated_expense.code == original_code

    def test_status_is_read_only(self, employee, user):
        """Test that status field is read-only."""
        expense = TravelExpense.objects.create(
            name="Test expense",
            expense_type=TravelExpense.ExpenseType.TAXABLE,
            employee=employee,
            amount=2000000,
            month=date(2025, 11, 1),
            created_by=user,
        )

        # Try to set status to CALCULATED
        data = {
            "status": "CALCULATED",
            "name": "Updated expense",
            "expense_type": "TAXABLE",
            "employee_id": employee.id,
            "amount": 2500000,
            "month": "11/2025",
        }

        serializer = TravelExpenseSerializer(expense, data=data)
        assert serializer.is_valid()

        updated_expense = serializer.save(updated_by=user)

        # Status should be NOT_CALCULATED (reset by serializer)
        assert updated_expense.status == TravelExpense.TravelExpenseStatus.NOT_CALCULATED
