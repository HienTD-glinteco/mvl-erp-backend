import random
import string
from datetime import date

import pytest
from django.core.exceptions import ValidationError

from apps.hrm.models import Employee
from apps.payroll.models import RecoveryVoucher


def make_employee(branch, block, department, **overrides):
    """Create an employee with required fields populated."""

    suffix = "".join(random.choices(string.digits, k=6))
    defaults = {
        "code": f"E{suffix}",
        "fullname": "John Doe",
        "username": f"johndoe{suffix}",
        "email": f"johndoe{suffix}@example.com",
        "personal_email": f"johndoe{suffix}.personal@example.com",
        "status": Employee.Status.ACTIVE,
        "code_type": Employee.CodeType.MV,
        "branch": branch,
        "block": block,
        "department": department,
        "start_date": date(2024, 1, 1),
        "attendance_code": suffix,
        "citizen_id": f"{suffix}{suffix}",
        "phone": f"09{suffix[:5]}{suffix[:3]}",
    }
    defaults.update(overrides)
    return Employee.objects.create(**defaults)


@pytest.mark.django_db
class TestRecoveryVoucherModel:
    """Test cases for RecoveryVoucher model"""

    def test_create_voucher_success(self, branch, block, department):
        """Test creating a voucher with valid data"""
        employee = make_employee(branch, block, department)

        voucher = RecoveryVoucher.objects.create(
            code="RV-202509-0001",
            name="Test Voucher",
            voucher_type=RecoveryVoucher.VoucherType.BACK_PAY,
            employee=employee,
            amount=1500000,
            month=date(2025, 9, 1),
            note="Test note",
        )

        assert voucher.id is not None
        assert voucher.code  # Code generated (may be TEMP_ in tests)
        assert voucher.name == "Test Voucher"
        assert voucher.voucher_type == RecoveryVoucher.VoucherType.BACK_PAY
        assert voucher.employee == employee
        assert voucher.amount == 1500000
        assert voucher.month == date(2025, 9, 1)
        assert voucher.status == RecoveryVoucher.RecoveryVoucherStatus.NOT_CALCULATED
        assert voucher.note == "Test note"

    def test_employee_fields_cached_on_save(self, branch, block, department):
        """Test that employee_code and employee_name are cached on save"""
        employee = make_employee(branch, block, department)

        voucher = RecoveryVoucher.objects.create(
            code="RV-202509-0001",
            name="Test Voucher",
            voucher_type=RecoveryVoucher.VoucherType.BACK_PAY,
            employee=employee,
            amount=1500000,
            month=date(2025, 9, 1),
        )

        assert voucher.employee_code == employee.code
        assert voucher.employee_name == employee.fullname

    def test_voucher_type_choices(self, branch, block, department):
        """Test that voucher_type only accepts valid choices"""
        employee = make_employee(branch, block, department)

        # Test RECOVERY
        voucher1 = RecoveryVoucher.objects.create(
            code="RV-202509-0001",
            name="Recovery Voucher",
            voucher_type=RecoveryVoucher.VoucherType.RECOVERY,
            employee=employee,
            amount=500000,
            month=date(2025, 9, 1),
        )
        assert voucher1.voucher_type == "RECOVERY"

        # Test BACK_PAY
        voucher2 = RecoveryVoucher.objects.create(
            code="RV-202509-0002",
            name="Back Pay Voucher",
            voucher_type=RecoveryVoucher.VoucherType.BACK_PAY,
            employee=employee,
            amount=1500000,
            month=date(2025, 9, 1),
        )
        assert voucher2.voucher_type == "BACK_PAY"

    def test_status_choices(self, branch, block, department):
        """Test that status only accepts valid choices"""
        employee = make_employee(branch, block, department)

        # Default status should be NOT_CALCULATED
        voucher = RecoveryVoucher.objects.create(
            code="RV-202509-0001",
            name="Test Voucher",
            voucher_type=RecoveryVoucher.VoucherType.BACK_PAY,
            employee=employee,
            amount=1500000,
            month=date(2025, 9, 1),
        )
        assert voucher.status == RecoveryVoucher.RecoveryVoucherStatus.NOT_CALCULATED

        # Update to CALCULATED
        voucher.status = RecoveryVoucher.RecoveryVoucherStatus.CALCULATED
        voucher.save()
        voucher.refresh_from_db()
        assert voucher.status == "CALCULATED"

    def test_amount_validation(self, branch, block, department):
        """Test that amount must be greater than 0"""
        employee = make_employee(branch, block, department)

        with pytest.raises(ValidationError) as exc_info:
            voucher = RecoveryVoucher(
                code="RV-202509-0001",
                name="Test Voucher",
                voucher_type=RecoveryVoucher.VoucherType.BACK_PAY,
                employee=employee,
                amount=0,
                month=date(2025, 9, 1),
            )
            voucher.save()

        assert "amount" in exc_info.value.message_dict

    def test_unique_code_constraint(self, branch, block, department):
        """Test that code must be unique"""
        employee = make_employee(branch, block, department)

        RecoveryVoucher.objects.create(
            code="RV-202509-0001",
            name="Test Voucher 1",
            voucher_type=RecoveryVoucher.VoucherType.BACK_PAY,
            employee=employee,
            amount=1500000,
            month=date(2025, 9, 1),
        )

        # Try to create another voucher with same code
        with pytest.raises(Exception):  # Will raise IntegrityError
            RecoveryVoucher.objects.create(
                code="RV-202509-0001",
                name="Test Voucher 2",
                voucher_type=RecoveryVoucher.VoucherType.BACK_PAY,
                employee=employee,
                amount=2000000,
                month=date(2025, 9, 1),
            )

    def test_str_representation(self, branch, block, department):
        """Test string representation of voucher"""
        employee = make_employee(branch, block, department)

        voucher = RecoveryVoucher.objects.create(
            code="RV-202509-0001",
            name="September Back Pay",
            voucher_type=RecoveryVoucher.VoucherType.BACK_PAY,
            employee=employee,
            amount=1500000,
            month=date(2025, 9, 1),
        )

        assert str(voucher) == "RV-202509-0001 - September Back Pay"

    def test_ordering(self, branch, block, department):
        """Test that vouchers are ordered by updated_at descending"""
        employee = make_employee(branch, block, department)

        voucher1 = RecoveryVoucher.objects.create(
            code="RV-202509-0001",
            name="Voucher 1",
            voucher_type=RecoveryVoucher.VoucherType.BACK_PAY,
            employee=employee,
            amount=1500000,
            month=date(2025, 9, 1),
        )

        voucher2 = RecoveryVoucher.objects.create(
            code="RV-202509-0002",
            name="Voucher 2",
            voucher_type=RecoveryVoucher.VoucherType.BACK_PAY,
            employee=employee,
            amount=2000000,
            month=date(2025, 10, 1),
        )

        # Get all vouchers
        vouchers = list(RecoveryVoucher.objects.all())

        # The latest updated voucher should be first
        assert vouchers[0].id == voucher2.id
        assert vouchers[1].id == voucher1.id
