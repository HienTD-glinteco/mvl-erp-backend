"""Tests for KPI period summary fix and delete protection."""

from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from apps.payroll.models import (
    DepartmentKPIAssessment,
    EmployeeKPIAssessment,
    KPIAssessmentPeriod,
    KPIConfig,
    PenaltyTicket,
    RecoveryVoucher,
    TravelExpense,
)

User = get_user_model()


@pytest.mark.django_db
class KPIPeriodSummaryTest(TestCase):
    """Test KPI period summary action with manager assessment logic."""

    @pytest.fixture(autouse=True)
    def setup_fixtures(self, department, employee):
        self.department = department
        self.employee = employee

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_authenticate(user=self.user)

        kpi_config = KPIConfig.objects.create(
            config={
                "grade_thresholds": [],
                "unit_control": {},
            }
        )

        self.period = KPIAssessmentPeriod.objects.create(
            month=date(2025, 12, 1),
            kpi_config_snapshot=kpi_config.config,
        )

    def test_summary_counts_departments_with_manager_assessment(self):
        """Test that departments_finished counts departments with at least one manager grade."""
        # Create department assessment
        dept_assessment = DepartmentKPIAssessment.objects.create(
            period=self.period,
            department=self.department,
            grade="A",
        )

        # Create employee assessment WITH manager grade
        EmployeeKPIAssessment.objects.create(
            period=self.period,
            employee=self.employee,
            department_snapshot=self.department,
            grade_manager="B",
        )

        response = self.client.get(f"/api/payroll/kpi-periods/{self.period.id}/summary/")

        self.assertEqual(response.status_code, 200)
        # Response might be wrapped
        if isinstance(response.json(), dict) and "data" in response.json():
            data = response.json()["data"]
        else:
            data = response.json()

        self.assertEqual(data["total_departments"], 1)
        self.assertEqual(data["departments_finished"], 1)
        self.assertEqual(data["departments_not_finished"], 0)

    def test_summary_counts_departments_without_manager_assessment(self):
        """Test that departments_not_finished counts departments with no manager grades."""
        # Create department assessment
        dept_assessment = DepartmentKPIAssessment.objects.create(
            period=self.period,
            department=self.department,
            grade="A",
        )

        # Create employee assessment WITHOUT manager grade
        EmployeeKPIAssessment.objects.create(
            period=self.period,
            employee=self.employee,
            department_snapshot=self.department,
            grade_manager=None,
        )

        response = self.client.get(f"/api/payroll/kpi-periods/{self.period.id}/summary/")

        self.assertEqual(response.status_code, 200)
        # Response might be wrapped
        if isinstance(response.json(), dict) and "data" in response.json():
            data = response.json()["data"]
        else:
            data = response.json()

        self.assertEqual(data["total_departments"], 1)
        self.assertEqual(data["departments_finished"], 0)
        self.assertEqual(data["departments_not_finished"], 1)


@pytest.mark.django_db
class TravelExpenseDeleteProtectionTest(TestCase):
    """Test delete protection for TravelExpense with CALCULATED status."""

    @pytest.fixture(autouse=True)
    def setup_fixtures(self, employee):
        self.employee = employee

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    def test_can_delete_not_calculated_travel_expense(self):
        """Test that NOT_CALCULATED travel expenses can be deleted."""
        expense = TravelExpense.objects.create(
            name="Test Expense",
            expense_type=TravelExpense.ExpenseType.TAXABLE,
            employee=self.employee,
            amount=100000,
            month=date(2025, 11, 1),
            status=TravelExpense.TravelExpenseStatus.NOT_CALCULATED,
            created_by=self.user,
        )

        expense_id = expense.id
        expense.delete()

        # Verify deletion succeeded
        self.assertFalse(TravelExpense.objects.filter(id=expense_id).exists())

    def test_cannot_delete_calculated_travel_expense(self):
        """Test that CALCULATED travel expenses cannot be deleted."""
        expense = TravelExpense.objects.create(
            name="Test Expense",
            expense_type=TravelExpense.ExpenseType.TAXABLE,
            employee=self.employee,
            amount=100000,
            month=date(2025, 11, 1),
            status=TravelExpense.TravelExpenseStatus.CALCULATED,
            created_by=self.user,
        )

        with self.assertRaises(ValidationError) as context:
            expense.delete()

        self.assertIn("Cannot delete travel expense", str(context.exception))
        # Verify expense still exists
        self.assertTrue(TravelExpense.objects.filter(id=expense.id).exists())


@pytest.mark.django_db
class PenaltyTicketDeleteProtectionTest(TestCase):
    """Test delete protection for PenaltyTicket with PAID status."""

    @pytest.fixture(autouse=True)
    def setup_fixtures(self, employee):
        self.employee = employee

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    def test_can_delete_unpaid_penalty_ticket(self):
        """Test that UNPAID penalty tickets can be deleted."""
        ticket = PenaltyTicket.objects.create(
            employee=self.employee,
            employee_code=self.employee.code,
            employee_name=self.employee.fullname,
            month=date(2025, 11, 1),
            amount=50000,
            violation_count=1,
            violation_type=PenaltyTicket.ViolationType.UNIFORM_ERROR,
            status=PenaltyTicket.Status.UNPAID,
            created_by=self.user,
        )

        ticket_id = ticket.id
        ticket.delete()

        # Verify deletion succeeded
        self.assertFalse(PenaltyTicket.objects.filter(id=ticket_id).exists())

    def test_cannot_delete_paid_penalty_ticket(self):
        """Test that PAID penalty tickets cannot be deleted."""
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

        with self.assertRaises(ValidationError) as context:
            ticket.delete()

        self.assertIn("Cannot delete penalty ticket", str(context.exception))
        # Verify ticket still exists
        self.assertTrue(PenaltyTicket.objects.filter(id=ticket.id).exists())


@pytest.mark.django_db
class RecoveryVoucherDeleteProtectionTest(TestCase):
    """Test delete protection for RecoveryVoucher with CALCULATED status."""

    @pytest.fixture(autouse=True)
    def setup_fixtures(self, employee):
        self.employee = employee

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    def test_can_delete_not_calculated_recovery_voucher(self):
        """Test that NOT_CALCULATED recovery vouchers can be deleted."""
        voucher = RecoveryVoucher.objects.create(
            name="Test Voucher",
            voucher_type=RecoveryVoucher.VoucherType.RECOVERY,
            employee=self.employee,
            amount=200000,
            month=date(2025, 11, 1),
            status=RecoveryVoucher.RecoveryVoucherStatus.NOT_CALCULATED,
            created_by=self.user,
        )

        voucher_id = voucher.id
        voucher.delete()

        # Verify deletion succeeded
        self.assertFalse(RecoveryVoucher.objects.filter(id=voucher_id).exists())

    def test_cannot_delete_calculated_recovery_voucher(self):
        """Test that CALCULATED recovery vouchers cannot be deleted."""
        voucher = RecoveryVoucher.objects.create(
            name="Test Voucher",
            voucher_type=RecoveryVoucher.VoucherType.RECOVERY,
            employee=self.employee,
            amount=200000,
            month=date(2025, 11, 1),
            status=RecoveryVoucher.RecoveryVoucherStatus.CALCULATED,
            created_by=self.user,
        )

        with self.assertRaises(ValidationError) as context:
            voucher.delete()

        self.assertIn("Cannot delete recovery voucher", str(context.exception))
        # Verify voucher still exists
        self.assertTrue(RecoveryVoucher.objects.filter(id=voucher.id).exists())
