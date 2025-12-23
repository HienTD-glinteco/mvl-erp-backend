import random
import string
from datetime import date

import pytest

from apps.hrm.models import Employee
from apps.payroll.api.serializers import RecoveryVoucherSerializer
from apps.payroll.models import RecoveryVoucher


def make_employee(branch, block, department, **overrides):
    """Create an employee with required fields populated."""

    suffix = "".join(random.choices(string.digits, k=6))
    defaults = {
        "code": f"E{suffix}",
        "fullname": "John Doe",
        "username": f"johndoe{suffix}",
        "email": f"johndoe{suffix}@example.com",
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
class TestRecoveryVoucherSerializer:
    """Test cases for RecoveryVoucher serializer"""

    def test_serialize_voucher(self, branch, block, department):
        """Test serializing a voucher"""
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

        serializer = RecoveryVoucherSerializer(voucher)
        data = serializer.data

        assert data["id"] == voucher.id
        assert data["code"] == "RV-202509-0001"
        assert data["name"] == "Test Voucher"
        assert data["voucher_type"] == "BACK_PAY"
        assert data["employee"]["id"] == employee.id
        assert data["employee"]["code"] == employee.code
        assert data["employee"]["fullname"] == employee.fullname
        assert data["employee_code"] == employee.code
        assert data["employee_name"] == employee.fullname
        assert data["branch"]["code"] == employee.branch.code
        assert data["block"]["code"] == employee.block.code
        assert data["department"]["code"] == employee.department.code
        assert data["amount"] == 1500000
        assert data["month"] == "09/2025"
        assert data["status"] == "NOT_CALCULATED"
        assert data["note"] == "Test note"

    def test_validate_month_valid(self):
        """Test validating month with valid format"""
        serializer = RecoveryVoucherSerializer()
        result = serializer.validate_month("09/2025")
        assert result == date(2025, 9, 1)

    def test_validate_month_invalid_format(self):
        """Test validating month with invalid format"""
        serializer = RecoveryVoucherSerializer()
        with pytest.raises(Exception):  # ValidationError
            serializer.validate_month("2025-09-01")

    def test_validate_month_invalid_month(self):
        """Test validating month with invalid month value"""
        serializer = RecoveryVoucherSerializer()
        with pytest.raises(Exception):  # ValidationError
            serializer.validate_month("13/2025")

    def test_validate_employee_active(self, branch, block, department):
        """Test validating active employee"""
        employee = make_employee(branch, block, department)

        serializer = RecoveryVoucherSerializer()
        result = serializer.validate_employee_id(employee)
        assert result == employee

    def test_validate_employee_inactive(self, branch, block, department):
        """Test validating inactive employee"""
        employee = make_employee(
            branch,
            block,
            department,
            status=Employee.Status.RESIGNED,
            resignation_start_date=date(2024, 1, 1),
            resignation_reason=Employee.ResignationReason.OTHER,
        )

        serializer = RecoveryVoucherSerializer()
        with pytest.raises(Exception):  # ValidationError
            serializer.validate_employee_id(employee)

    def test_validate_amount_positive(self):
        """Test validating positive amount"""
        serializer = RecoveryVoucherSerializer()
        result = serializer.validate_amount(1500000)
        assert result == 1500000

    def test_validate_amount_zero(self):
        """Test validating zero amount"""
        serializer = RecoveryVoucherSerializer()
        with pytest.raises(Exception):  # ValidationError
            serializer.validate_amount(0)

    def test_validate_amount_negative(self):
        """Test validating negative amount"""
        serializer = RecoveryVoucherSerializer()
        with pytest.raises(Exception):  # ValidationError
            serializer.validate_amount(-1000)

    def test_validate_name_valid(self):
        """Test validating valid name"""
        serializer = RecoveryVoucherSerializer()
        result = serializer.validate_name("Test Voucher")
        assert result == "Test Voucher"

    def test_validate_name_empty(self):
        """Test validating empty name"""
        serializer = RecoveryVoucherSerializer()
        with pytest.raises(Exception):  # ValidationError
            serializer.validate_name("")

    def test_validate_name_too_long(self):
        """Test validating name exceeding max length"""
        serializer = RecoveryVoucherSerializer()
        long_name = "A" * 251
        with pytest.raises(Exception):  # ValidationError
            serializer.validate_name(long_name)

    def test_validate_note_valid(self):
        """Test validating valid note"""
        serializer = RecoveryVoucherSerializer()
        result = serializer.validate_note("Test note")
        assert result == "Test note"

    def test_validate_note_too_long(self):
        """Test validating note exceeding max length"""
        serializer = RecoveryVoucherSerializer()
        long_note = "A" * 501
        with pytest.raises(Exception):  # ValidationError
            serializer.validate_note(long_note)
