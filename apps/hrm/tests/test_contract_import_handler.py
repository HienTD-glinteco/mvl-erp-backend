"""Tests for contract import handler."""

from datetime import date
from decimal import Decimal

import pytest

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.import_handlers.contract import (
    copy_snapshot_from_contract_type,
    import_handler,
    lookup_contract_type,
    lookup_employee,
    normalize_header,
    normalize_value,
    parse_boolean,
    parse_date,
    parse_decimal,
)
from apps.hrm.models import (
    Block,
    Branch,
    Contract,
    ContractType,
    Department,
    Employee,
)


@pytest.mark.django_db
class TestUtilityFunctions:
    """Test utility functions used in contract import handler."""

    def test_normalize_header(self):
        """Test header normalization."""
        assert normalize_header("Mã nhân viên") == "mã nhân viên"
        assert normalize_header("  Ngày ký  ") == "ngày ký"
        assert normalize_header("LƯƠNG CƠ BẢN") == "lương cơ bản"
        assert normalize_header("") == ""
        assert normalize_header(None) == ""

    def test_normalize_value(self):
        """Test value normalization."""
        assert normalize_value("  test  ") == "test"
        assert normalize_value(123) == "123"
        assert normalize_value(None) == ""
        assert normalize_value("") == ""

    def test_parse_date_valid(self):
        """Test date parsing with valid inputs."""
        # YYYY-MM-DD format
        parsed_date, error = parse_date("2025-01-15", "sign_date")
        assert parsed_date == date(2025, 1, 15)
        assert error is None

        # DD/MM/YYYY format
        parsed_date, error = parse_date("15/01/2025", "sign_date")
        assert parsed_date == date(2025, 1, 15)
        assert error is None

        # DD-MM-YYYY format
        parsed_date, error = parse_date("15-01-2025", "sign_date")
        assert parsed_date == date(2025, 1, 15)
        assert error is None

        # Date object
        test_date = date(2025, 1, 15)
        parsed_date, error = parse_date(test_date, "sign_date")
        assert parsed_date == test_date
        assert error is None

    def test_parse_date_invalid(self):
        """Test date parsing with invalid inputs."""
        # Invalid format
        parsed_date, error = parse_date("invalid", "sign_date")
        assert parsed_date is None
        assert "Invalid date format" in error

        # Empty value
        parsed_date, error = parse_date("", "sign_date")
        assert parsed_date is None
        assert error is None

        # Dash only
        parsed_date, error = parse_date("-", "sign_date")
        assert parsed_date is None
        assert error is None

    def test_parse_decimal_valid(self):
        """Test decimal parsing with valid inputs."""
        # Integer
        value, error = parse_decimal(15000000, "base_salary")
        assert value == Decimal("15000000")
        assert error is None

        # String with commas
        value, error = parse_decimal("15,000,000", "base_salary")
        assert value == Decimal("15000000")
        assert error is None

        # String without commas
        value, error = parse_decimal("15000000", "base_salary")
        assert value == Decimal("15000000")
        assert error is None

    def test_parse_decimal_invalid(self):
        """Test decimal parsing with invalid inputs."""
        # Invalid string
        value, error = parse_decimal("invalid", "base_salary")
        assert value is None
        assert "Invalid decimal" in error

        # Empty value
        value, error = parse_decimal("", "base_salary")
        assert value is None
        assert error is None

    def test_parse_boolean_valid(self):
        """Test boolean parsing with valid inputs."""
        # True values
        for true_val in ["có", "yes", "true", "1", True]:
            value, error = parse_boolean(true_val, "has_social_insurance")
            assert value is True
            assert error is None

        # False values
        for false_val in ["không", "no", "false", "0", False]:
            value, error = parse_boolean(false_val, "has_social_insurance")
            assert value is False
            assert error is None

    def test_parse_boolean_invalid(self):
        """Test boolean parsing with invalid inputs."""
        value, error = parse_boolean("maybe", "has_social_insurance")
        assert value is None
        assert "Invalid boolean" in error

        value, error = parse_boolean("", "has_social_insurance")
        assert value is None
        assert error is None


@pytest.mark.django_db
class TestLookupFunctions:
    """Test lookup functions for employee and contract type."""

    @pytest.fixture(autouse=True)
    def setup_base_data(self):
        """Create base data for tests."""
        # Create province and administrative unit
        province = Province.objects.create(name="Test Province", code="TP")
        admin_unit = AdministrativeUnit.objects.create(
            name="Test Unit",
            code="TU",
            parent_province=province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )

        # Create branch, block, department
        branch = Branch.objects.create(
            name="Test Branch",
            code="TB",
            province=province,
            administrative_unit=admin_unit,
        )
        block = Block.objects.create(
            name="Test Block",
            code="TBL",
            branch=branch,
            block_type=Block.BlockType.BUSINESS,
        )
        department = Department.objects.create(
            name="Test Department",
            code="TD",
            branch=branch,
            block=block,
        )

        return {
            "province": province,
            "admin_unit": admin_unit,
            "branch": branch,
            "block": block,
            "department": department,
        }

    def test_lookup_employee_existing(self, setup_base_data):
        """Test lookup of existing employee."""
        department = setup_base_data["department"]
        employee = Employee.objects.create(
            code="MV000001",
            fullname="Test Employee",
            username="testuser",
            email="test@example.com",
            department=department,
            start_date=date(2024, 1, 1),
        )

        found, error = lookup_employee("MV000001")
        assert found == employee
        assert error is None

        # Case insensitive
        found, error = lookup_employee("mv000001")
        assert found == employee
        assert error is None

    def test_lookup_employee_not_found(self):
        """Test lookup of non-existent employee."""
        found, error = lookup_employee("NONEXISTENT")
        assert found is None
        assert "not found" in error

    def test_lookup_employee_empty_code(self):
        """Test lookup with empty employee code."""
        found, error = lookup_employee("")
        assert found is None
        assert "required" in error

    def test_lookup_contract_type_existing(self):
        """Test lookup of existing contract type."""
        contract_type = ContractType.objects.create(
            name="Full-time Employment",
            base_salary=15000000,
        )

        found, error = lookup_contract_type(contract_type.code)
        assert found == contract_type
        assert error is None

    def test_lookup_contract_type_not_found(self):
        """Test lookup of non-existent contract type."""
        found, error = lookup_contract_type("NONEXISTENT")
        assert found is None
        assert "not found" in error


@pytest.mark.django_db
class TestCopySnapshotFromContractType:
    """Test snapshot copying from contract type."""

    def test_copy_all_fields(self):
        """Test copying all snapshot fields."""
        contract_type = ContractType.objects.create(
            name="Test Contract Type",
            base_salary=15000000,
            lunch_allowance=500000,
            phone_allowance=200000,
            other_allowance=100000,
            net_percentage=ContractType.NetPercentage.FULL,
            tax_calculation_method=ContractType.TaxCalculationMethod.PROGRESSIVE,
            has_social_insurance=True,
            working_conditions="Standard conditions",
            rights_and_obligations="Standard rights",
            terms="Standard terms",
        )

        contract_data = {}
        copy_snapshot_from_contract_type(contract_type, contract_data)

        assert contract_data["base_salary"] == Decimal("15000000")
        assert contract_data["lunch_allowance"] == Decimal("500000")
        assert contract_data["phone_allowance"] == Decimal("200000")
        assert contract_data["other_allowance"] == Decimal("100000")
        assert contract_data["net_percentage"] == ContractType.NetPercentage.FULL
        assert contract_data["tax_calculation_method"] == ContractType.TaxCalculationMethod.PROGRESSIVE
        assert contract_data["has_social_insurance"] is True
        assert contract_data["working_conditions"] == "Standard conditions"
        assert contract_data["rights_and_obligations"] == "Standard rights"
        assert contract_data["terms"] == "Standard terms"

    def test_does_not_overwrite_existing(self):
        """Test that existing values are not overwritten."""
        contract_type = ContractType.objects.create(
            name="Test Contract Type",
            base_salary=15000000,
            lunch_allowance=500000,
        )

        contract_data = {
            "base_salary": Decimal("20000000"),  # Custom value
        }
        copy_snapshot_from_contract_type(contract_type, contract_data)

        # base_salary should not be overwritten
        assert contract_data["base_salary"] == Decimal("20000000")
        # lunch_allowance should be copied from contract type
        assert contract_data["lunch_allowance"] == Decimal("500000")


@pytest.mark.django_db
class TestContractImportHandler:
    """Test the main contract import handler."""

    @pytest.fixture
    def setup_test_data(self):
        """Setup test data for import handler tests."""
        # Create province and administrative unit
        province = Province.objects.create(name="Test Province", code="TP")
        admin_unit = AdministrativeUnit.objects.create(
            name="Test Unit",
            code="TU",
            parent_province=province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )

        # Create branch, block, department
        branch = Branch.objects.create(
            name="Test Branch",
            code="TB",
            province=province,
            administrative_unit=admin_unit,
        )
        block = Block.objects.create(
            name="Test Block",
            code="TBL",
            branch=branch,
            block_type=Block.BlockType.BUSINESS,
        )
        department = Department.objects.create(
            name="Test Department",
            code="TD",
            branch=branch,
            block=block,
        )

        # Create employee
        employee = Employee.objects.create(
            code="MV000001",
            fullname="Test Employee",
            username="testuser",
            email="test@example.com",
            department=department,
            start_date=date(2024, 1, 1),
        )

        # Create contract type
        contract_type = ContractType.objects.create(
            name="Full-time Employment",
            base_salary=15000000,
            lunch_allowance=500000,
            phone_allowance=200000,
            has_social_insurance=True,
        )

        return {
            "province": province,
            "admin_unit": admin_unit,
            "branch": branch,
            "block": block,
            "department": department,
            "employee": employee,
            "contract_type": contract_type,
        }

    @pytest.fixture
    def template_headers(self):
        """Standard template headers for import tests."""
        return [
            "Số Thứ Tự",
            "Mã Nhân Viên",
            "Mã Loại Hợp Đồng",
            "Ngày Ký",
            "Ngày Hiệu Lực",
            "Ngày Hết Hạn",
            "Lương Cơ Bản",
            "Phụ Cấp Ăn Trưa",
            "Phụ Cấp Điện Thoại",
            "Phụ Cấp Khác",
            "Tỷ Lệ Lương Net",
            "Phương Pháp Tính Thuế",
            "Có Bảo Hiểm Xã Hội",
            "Điều Kiện Làm Việc",
            "Quyền Và Nghĩa Vụ",
            "Điều Khoản",
            "Ghi Chú",
        ]

    def test_import_handler_success_basic(self, setup_test_data, template_headers):
        """Test successful contract import with basic fields."""
        employee = setup_test_data["employee"]
        contract_type = setup_test_data["contract_type"]

        row = [
            1,  # row_number
            employee.code,  # employee_code
            contract_type.code,  # contract_type_code
            "2025-01-15",  # sign_date
            "2025-02-01",  # effective_date
            "2026-02-01",  # expiration_date
            "",  # base_salary (use contract type default)
            "",  # lunch_allowance
            "",  # phone_allowance
            "",  # other_allowance
            "",  # net_percentage
            "",  # tax_calculation_method
            "",  # has_social_insurance
            "",  # working_conditions
            "",  # rights_and_obligations
            "",  # terms
            "Import test note",  # note
        ]

        options = {"headers": template_headers}
        result = import_handler(1, row, "test-job-id", options)

        assert result["ok"] is True
        assert result["action"] == "created"
        assert "contract_code" in result
        # Contract code format is: xx/yyyy/abc - MVL
        assert "/" in result["contract_code"]
        assert "MVL" in result["contract_code"]

        # Verify contract was created
        contract = Contract.objects.get(code=result["contract_code"])
        assert contract.employee == employee
        assert contract.contract_type == contract_type
        assert contract.sign_date == date(2025, 1, 15)
        assert contract.effective_date == date(2025, 2, 1)
        assert contract.expiration_date == date(2026, 2, 1)
        assert contract.status == Contract.ContractStatus.DRAFT
        assert contract.note == "Import test note"
        # Snapshot data from contract type
        assert contract.base_salary == contract_type.base_salary
        assert contract.lunch_allowance == contract_type.lunch_allowance

    def test_import_handler_with_custom_salary(self, setup_test_data, template_headers):
        """Test contract import with custom salary values."""
        employee = setup_test_data["employee"]
        contract_type = setup_test_data["contract_type"]

        row = [
            1,
            employee.code,
            contract_type.code,
            "2025-01-15",
            "2025-02-01",
            "",  # No expiration (indefinite)
            "20000000",  # Custom base_salary
            "600000",  # Custom lunch_allowance
            "300000",  # Custom phone_allowance
            "150000",  # Custom other_allowance
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ]

        options = {"headers": template_headers}
        result = import_handler(1, row, "test-job-id", options)

        assert result["ok"] is True
        assert result["action"] == "created"

        contract = Contract.objects.get(code=result["contract_code"])
        assert contract.base_salary == Decimal("20000000")
        assert contract.lunch_allowance == Decimal("600000")
        assert contract.phone_allowance == Decimal("300000")
        assert contract.other_allowance == Decimal("150000")
        assert contract.expiration_date is None

    def test_import_handler_missing_employee_code(self, template_headers):
        """Test import with missing employee code - should skip."""
        row = [
            1,
            "",  # Missing employee_code
            "LHD001",
            "2025-01-15",
            "2025-02-01",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ]

        options = {"headers": template_headers}
        result = import_handler(1, row, "test-job-id", options)

        assert result["ok"] is True
        assert result["action"] == "skipped"
        assert "employee code" in result["warnings"][0].lower()

    def test_import_handler_missing_contract_type_code(self, setup_test_data, template_headers):
        """Test import with missing contract type code - should skip."""
        employee = setup_test_data["employee"]

        row = [
            1,
            employee.code,
            "",  # Missing contract_type_code
            "2025-01-15",
            "2025-02-01",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ]

        options = {"headers": template_headers}
        result = import_handler(1, row, "test-job-id", options)

        assert result["ok"] is True
        assert result["action"] == "skipped"
        assert "contract type code" in result["warnings"][0].lower()

    def test_import_handler_employee_not_found(self, setup_test_data, template_headers):
        """Test import with non-existent employee."""
        contract_type = setup_test_data["contract_type"]

        row = [
            1,
            "NONEXISTENT",  # Non-existent employee
            contract_type.code,
            "2025-01-15",
            "2025-02-01",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ]

        options = {"headers": template_headers}
        result = import_handler(1, row, "test-job-id", options)

        assert result["ok"] is False
        assert "not found" in result["error"]

    def test_import_handler_contract_type_not_found(self, setup_test_data, template_headers):
        """Test import with non-existent contract type."""
        employee = setup_test_data["employee"]

        row = [
            1,
            employee.code,
            "NONEXISTENT",  # Non-existent contract type
            "2025-01-15",
            "2025-02-01",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ]

        options = {"headers": template_headers}
        result = import_handler(1, row, "test-job-id", options)

        assert result["ok"] is False
        assert "not found" in result["error"]

    def test_import_handler_missing_sign_date(self, setup_test_data, template_headers):
        """Test import with missing sign date."""
        employee = setup_test_data["employee"]
        contract_type = setup_test_data["contract_type"]

        row = [
            1,
            employee.code,
            contract_type.code,
            "",  # Missing sign_date
            "2025-02-01",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ]

        options = {"headers": template_headers}
        result = import_handler(1, row, "test-job-id", options)

        assert result["ok"] is False
        assert "Sign date is required" in result["error"]

    def test_import_handler_missing_effective_date(self, setup_test_data, template_headers):
        """Test import with missing effective date."""
        employee = setup_test_data["employee"]
        contract_type = setup_test_data["contract_type"]

        row = [
            1,
            employee.code,
            contract_type.code,
            "2025-01-15",
            "",  # Missing effective_date
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ]

        options = {"headers": template_headers}
        result = import_handler(1, row, "test-job-id", options)

        assert result["ok"] is False
        assert "Effective date is required" in result["error"]

    def test_import_handler_sign_date_after_effective_date(self, setup_test_data, template_headers):
        """Test import with sign date after effective date."""
        employee = setup_test_data["employee"]
        contract_type = setup_test_data["contract_type"]

        row = [
            1,
            employee.code,
            contract_type.code,
            "2025-02-15",  # sign_date after effective_date
            "2025-02-01",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ]

        options = {"headers": template_headers}
        result = import_handler(1, row, "test-job-id", options)

        assert result["ok"] is False
        assert "Sign date must be on or before effective date" in result["error"]

    def test_import_handler_expiration_before_effective(self, setup_test_data, template_headers):
        """Test import with expiration date before effective date."""
        employee = setup_test_data["employee"]
        contract_type = setup_test_data["contract_type"]

        row = [
            1,
            employee.code,
            contract_type.code,
            "2025-01-15",
            "2025-02-01",
            "2025-01-20",  # expiration_date before effective_date
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ]

        options = {"headers": template_headers}
        result = import_handler(1, row, "test-job-id", options)

        assert result["ok"] is False
        assert "Expiration date must be on or after effective date" in result["error"]

    def test_import_handler_skip_duplicate(self, setup_test_data, template_headers):
        """Test import skips duplicate when allow_update=False."""
        employee = setup_test_data["employee"]
        contract_type = setup_test_data["contract_type"]

        # Create existing contract
        Contract.objects.create(
            employee=employee,
            contract_type=contract_type,
            sign_date=date(2025, 1, 15),
            effective_date=date(2025, 2, 1),
            status=Contract.ContractStatus.DRAFT,
        )

        row = [
            1,
            employee.code,
            contract_type.code,
            "2025-01-15",
            "2025-02-01",  # Same effective date and contract type
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ]

        options = {"headers": template_headers, "allow_update": False}
        result = import_handler(1, row, "test-job-id", options)

        assert result["ok"] is True
        assert result["action"] == "skipped"
        assert "already exists" in result["warnings"][0]

    def test_import_handler_update_existing(self, setup_test_data, template_headers):
        """Test import updates existing contract when allow_update=True."""
        employee = setup_test_data["employee"]
        contract_type = setup_test_data["contract_type"]

        # Create existing contract
        existing = Contract.objects.create(
            employee=employee,
            contract_type=contract_type,
            sign_date=date(2025, 1, 15),
            effective_date=date(2025, 2, 1),
            base_salary=15000000,
            status=Contract.ContractStatus.DRAFT,
        )

        row = [
            1,
            employee.code,
            contract_type.code,
            "2025-01-15",
            "2025-02-01",
            "2026-02-01",  # Add expiration date
            "20000000",  # Update salary
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "Updated note",
        ]

        options = {"headers": template_headers, "allow_update": True}
        result = import_handler(1, row, "test-job-id", options)

        assert result["ok"] is True
        assert result["action"] == "updated"

        # Verify contract was updated
        existing.refresh_from_db()
        assert existing.expiration_date == date(2026, 2, 1)
        assert existing.base_salary == Decimal("20000000")
        assert existing.note == "Updated note"

    def test_import_handler_cannot_update_non_draft(self, setup_test_data, template_headers):
        """Test import cannot update non-DRAFT contract."""
        employee = setup_test_data["employee"]
        contract_type = setup_test_data["contract_type"]

        # Create existing ACTIVE contract
        Contract.objects.create(
            employee=employee,
            contract_type=contract_type,
            sign_date=date(2025, 1, 15),
            effective_date=date(2025, 2, 1),
            status=Contract.ContractStatus.ACTIVE,
        )

        row = [
            1,
            employee.code,
            contract_type.code,
            "2025-01-15",
            "2025-02-01",
            "",
            "20000000",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ]

        options = {"headers": template_headers, "allow_update": True}
        result = import_handler(1, row, "test-job-id", options)

        assert result["ok"] is False
        assert "only DRAFT contracts can be updated" in result["error"]

    def test_import_handler_no_headers(self):
        """Test import fails without headers."""
        row = ["1", "MV000001", "LHD001", "2025-01-15", "2025-02-01"]

        options = {}  # No headers
        result = import_handler(1, row, "test-job-id", options)

        assert result["ok"] is False
        assert "Headers not provided" in result["error"]

    def test_import_handler_with_boolean_and_enum_fields(self, setup_test_data, template_headers):
        """Test import with boolean and enum field values."""
        employee = setup_test_data["employee"]
        contract_type = setup_test_data["contract_type"]

        row = [
            1,
            employee.code,
            contract_type.code,
            "2025-01-15",
            "2025-02-01",
            "",
            "",
            "",
            "",
            "",
            "85%",  # net_percentage
            "10%",  # tax_calculation_method
            "không",  # has_social_insurance = False
            "Custom conditions",
            "",
            "",
            "",
        ]

        options = {"headers": template_headers}
        result = import_handler(1, row, "test-job-id", options)

        assert result["ok"] is True
        assert result["action"] == "created"

        contract = Contract.objects.get(code=result["contract_code"])
        assert contract.net_percentage == ContractType.NetPercentage.REDUCED
        assert contract.tax_calculation_method == ContractType.TaxCalculationMethod.FLAT_10
        assert contract.has_social_insurance is False
        assert contract.working_conditions == "Custom conditions"
