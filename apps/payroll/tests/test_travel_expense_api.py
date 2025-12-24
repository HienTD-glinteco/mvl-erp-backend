"""Tests for TravelExpense API endpoints."""

import json
from datetime import date
from pathlib import Path

import pytest
from rest_framework import status

from apps.payroll.models import TravelExpense


@pytest.fixture
def travel_expense_samples():
    fixture_path = Path(__file__).parent / "fixtures" / "travel_expense_samples.json"
    with fixture_path.open() as f:
        return json.load(f)


@pytest.mark.django_db
class TestTravelExpenseAPI:
    """Test TravelExpense API endpoints."""

    def test_list_travel_expenses(self, api_client, superuser, employee):
        """Test listing travel expenses."""

        # Create test expenses
        for i in range(3):
            TravelExpense.objects.create(
                name=f"Expense {i + 1}",
                expense_type=TravelExpense.ExpenseType.TAXABLE
                if i % 2 == 0
                else TravelExpense.ExpenseType.NON_TAXABLE,
                employee=employee,
                amount=(i + 1) * 1000000,
                month=date(2025, 11, 1),
                note=f"Note {i + 1}",
                created_by=superuser,
            )

        response = api_client.get("/api/payroll/travel-expenses/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["success"] is True
        assert "data" in data
        assert data["data"]["count"] == 3
        assert len(data["data"]["results"]) == 3

    def test_create_travel_expense(self, api_client, employee):
        """Test creating a travel expense."""

        create_data = {
            "name": "Client visit 11/2025",
            "expense_type": "TAXABLE",
            "employee_id": employee.id,
            "amount": 2500000,
            "month": "11/2025",
            "note": "Taxi + meals",
        }

        response = api_client.post(
            "/api/payroll/travel-expenses/",
            data=json.dumps(create_data),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        assert data["success"] is True
        assert data["data"]["name"] == create_data["name"]
        assert data["data"]["status"] == "NOT_CALCULATED"
        assert data["data"]["code"].startswith("TE-202511-")

    def test_create_travel_expense_from_samples(self, api_client, employee, travel_expense_samples):
        """Test creating travel expense using JSON samples."""
        create_data = travel_expense_samples["create_request"].copy()
        create_data["employee_id"] = employee.id

        response = api_client.post(
            "/api/payroll/travel-expenses/",
            data=json.dumps(create_data),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["success"] is True
        assert body["data"]["name"] == create_data["name"]
        assert body["data"]["expense_type"] == create_data["expense_type"]
        assert body["data"]["amount"] == create_data["amount"]
        assert body["data"]["month"] == create_data["month"]
        assert body["data"]["status"] == "NOT_CALCULATED"
        assert body["data"]["note"] == create_data["note"]
        assert body["data"]["employee"]["id"] == employee.id

    def test_update_travel_expense(self, api_client, superuser, employee):
        """Test updating a travel expense."""

        expense = TravelExpense.objects.create(
            name="Original expense",
            expense_type=TravelExpense.ExpenseType.TAXABLE,
            employee=employee,
            amount=2000000,
            month=date(2025, 11, 1),
            created_by=superuser,
        )

        update_data = {
            "name": "Updated expense",
            "expense_type": "NON_TAXABLE",
            "employee_id": employee.id,
            "amount": 5000000,
            "month": "11/2025",
            "note": "Updated note",
        }

        response = api_client.put(
            f"/api/payroll/travel-expenses/{expense.id}/",
            data=json.dumps(update_data),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["success"] is True
        assert data["data"]["name"] == "Updated expense"
        assert data["data"]["status"] == "NOT_CALCULATED"

    def test_delete_travel_expense(self, api_client, superuser, employee):
        """Test deleting a travel expense."""

        expense = TravelExpense.objects.create(
            name="To be deleted",
            expense_type=TravelExpense.ExpenseType.TAXABLE,
            employee=employee,
            amount=1000000,
            month=date(2025, 11, 1),
            created_by=superuser,
        )
        expense_id = expense.id

        response = api_client.delete(f"/api/payroll/travel-expenses/{expense_id}/")

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify expense is deleted
        assert not TravelExpense.objects.filter(id=expense_id).exists()

    def test_filter_by_expense_type(self, api_client, superuser, employee):
        """Test filtering by expense type."""

        TravelExpense.objects.create(
            name="Taxable 1",
            expense_type=TravelExpense.ExpenseType.TAXABLE,
            employee=employee,
            amount=1000000,
            month=date(2025, 11, 1),
            created_by=superuser,
        )
        TravelExpense.objects.create(
            name="Non-taxable 1",
            expense_type=TravelExpense.ExpenseType.NON_TAXABLE,
            employee=employee,
            amount=1000000,
            month=date(2025, 11, 1),
            created_by=superuser,
        )

        response = api_client.get("/api/payroll/travel-expenses/?expense_type=TAXABLE")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["data"]["count"] == 1
        assert data["data"]["results"][0]["expense_type"] == "TAXABLE"
