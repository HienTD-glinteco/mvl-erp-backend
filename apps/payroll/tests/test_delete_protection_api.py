"""API tests for delete protection - ensure proper HTTP status codes."""

from datetime import date

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.payroll.models import PenaltyTicket, RecoveryVoucher, TravelExpense

User = get_user_model()


@pytest.mark.django_db
class TestDeleteProtectionAPIResponses:
    """Test that delete protection returns 400 (not 500) via API."""

    @pytest.fixture(autouse=True)
    def setup_fixtures(self, employee):
        self.employee = employee
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="apiuser",
            email="api@test.com",
            password="testpass123",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_authenticate(user=self.user)

    def test_delete_calculated_travel_expense_returns_400(self):
        """Test DELETE request for CALCULATED travel expense returns 400."""
        expense = TravelExpense.objects.create(
            name="Test Expense",
            expense_type=TravelExpense.ExpenseType.TAXABLE,
            employee=self.employee,
            amount=100000,
            month=date(2025, 11, 1),
            status=TravelExpense.TravelExpenseStatus.CALCULATED,
            created_by=self.user,
        )

        response = self.client.delete(f"/api/payroll/travel-expenses/{expense.id}/")

        # Should return 400, not 500
        assert response.status_code == 400
        assert "Cannot delete" in response.content.decode()

    def test_delete_paid_penalty_ticket_returns_400(self):
        """Test DELETE request for PAID penalty ticket returns 400."""
        ticket = PenaltyTicket.objects.create(
            employee=self.employee,
            employee_code=self.employee.code,
            employee_name=self.employee.fullname,
            month=date(2025, 11, 1),
            amount=50000,
            violation_count=1,
            violation_type=PenaltyTicket.ViolationType.UNIFORM_ERROR,
            status=PenaltyTicket.Status.PAID,
            payment_date=date(2025, 11, 15),
            created_by=self.user,
        )

        response = self.client.delete(f"/api/payroll/penalty-tickets/{ticket.id}/")

        # Should return 400, not 500
        assert response.status_code == 400
        assert "Cannot delete" in response.content.decode()

    def test_delete_calculated_recovery_voucher_returns_400(self):
        """Test DELETE request for CALCULATED recovery voucher returns 400."""
        voucher = RecoveryVoucher.objects.create(
            name="Test Voucher",
            voucher_type=RecoveryVoucher.VoucherType.RECOVERY,
            employee=self.employee,
            amount=200000,
            month=date(2025, 11, 1),
            status=RecoveryVoucher.RecoveryVoucherStatus.CALCULATED,
            created_by=self.user,
        )

        response = self.client.delete(f"/api/payroll/recovery-vouchers/{voucher.id}/")

        # Should return 400, not 500
        assert response.status_code == 400
        assert "Cannot delete" in response.content.decode()

    def test_delete_not_calculated_returns_204(self):
        """Test DELETE request for NOT_CALCULATED items returns 204 (success)."""
        expense = TravelExpense.objects.create(
            name="Test Expense",
            expense_type=TravelExpense.ExpenseType.TAXABLE,
            employee=self.employee,
            amount=100000,
            month=date(2025, 11, 1),
            status=TravelExpense.TravelExpenseStatus.NOT_CALCULATED,
            created_by=self.user,
        )

        response = self.client.delete(f"/api/payroll/travel-expenses/{expense.id}/")

        # Should succeed with 204
        assert response.status_code == 204
