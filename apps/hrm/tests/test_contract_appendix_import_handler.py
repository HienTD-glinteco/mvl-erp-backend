"""Tests for contract appendix import handler."""

from datetime import date

import pytest

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.import_handlers.contract_appendix import (
    ContractAppendixImportSerializer,
    import_handler,
    pre_import_initialize,
)
from apps.hrm.models import (
    Block,
    Branch,
    Contract,
    ContractType,
    Department,
    Employee,
)
from libs.drf.serializers import (
    FlexibleDateField,
    normalize_value,
)
from libs.strings import normalize_header


@pytest.mark.django_db
class TestUtilityFunctions:
    """Test utility functions used in contract appendix import handler."""

    def test_normalize_header(self):
        """Test header normalization."""
        assert normalize_header("Số Hợp Đồng") == "số hợp đồng"
        assert normalize_header("  Ngày ký  ") == "ngày ký"
        assert normalize_header("MÃ NHÂN VIÊN") == "mã nhân viên"
        assert normalize_header("") == ""
        assert normalize_header(None) == ""

    def test_normalize_value(self):
        """Test value normalization."""
        assert normalize_value("  test  ") == "test"
        assert normalize_value(123) == "123"
        assert normalize_value(None) == ""
        assert normalize_value("") == ""


@pytest.mark.django_db
class TestFlexibleDateFieldForAppendix:
    """Test FlexibleDateField for appendix import."""

    def test_flexible_date_field_valid_iso(self):
        """Test FlexibleDateField with ISO format."""
        field = FlexibleDateField()
        assert field.to_internal_value("2025-01-15") == date(2025, 1, 15)

    def test_flexible_date_field_valid_european(self):
        """Test FlexibleDateField with DD/MM/YYYY format."""
        field = FlexibleDateField()
        assert field.to_internal_value("15/01/2025") == date(2025, 1, 15)

    def test_flexible_date_field_object(self):
        """Test FlexibleDateField with date object."""
        field = FlexibleDateField()
        test_date = date(2025, 1, 15)
        assert field.to_internal_value(test_date) == test_date


@pytest.mark.django_db
class TestContractAppendixImportSerializer:
    """Test ContractAppendixImportSerializer validation."""

    def test_serializer_valid_data(self):
        """Test serializer with valid data."""
        data = {
            "sign_date": date(2025, 1, 15),
            "effective_date": date(2025, 2, 1),
        }

        serializer = ContractAppendixImportSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_serializer_valid_data_with_content(self):
        """Test serializer with valid data including content."""
        data = {
            "sign_date": date(2025, 1, 15),
            "effective_date": date(2025, 2, 1),
            "content": "Salary adjustment",
            "note": "Approved by HR",
        }

        serializer = ContractAppendixImportSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["content"] == "Salary adjustment"
        assert serializer.validated_data["note"] == "Approved by HR"

    def test_serializer_date_validation(self):
        """Test serializer date validation."""
        # Sign date after effective date
        data = {
            "sign_date": date(2025, 2, 15),
            "effective_date": date(2025, 2, 1),
        }

        serializer = ContractAppendixImportSerializer(data=data)
        assert not serializer.is_valid()
        assert "sign_date" in serializer.errors


@pytest.mark.django_db
class TestPreImportInitialize:
    """Test the pre_import_initialize function."""

    @pytest.fixture
    def setup_test_data(self):
        """Setup test data for pre-import tests."""
        province = Province.objects.create(name="Test Province", code="TP")
        admin_unit = AdministrativeUnit.objects.create(
            name="Test Unit",
            code="TU",
            parent_province=province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )
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
        employee = Employee.objects.create(
            code="MV000001",
            fullname="Test Employee",
            username="testuser",
            email="test@example.com",
            department=department,
            start_date=date(2024, 1, 1),
        )
        contract_type = ContractType.objects.create(
            name="Full-time Employment",
            base_salary=15000000,
        )
        contract = Contract.objects.create(
            employee=employee,
            contract_type=contract_type,
            sign_date=date(2024, 1, 1),
            effective_date=date(2024, 1, 15),
            status=Contract.ContractStatus.ACTIVE,
        )
        return {
            "employee": employee,
            "contract_type": contract_type,
            "contract": contract,
        }

    def test_pre_import_initialize_prefetches_employees(self, setup_test_data):
        """Test that pre_import_initialize prefetches all employees."""
        options = {}
        pre_import_initialize("test-job-id", options)

        assert "_employees_by_code" in options
        employees_by_code = options["_employees_by_code"]
        assert "mv000001" in employees_by_code
        assert employees_by_code["mv000001"].fullname == "Test Employee"

    def test_pre_import_initialize_prefetches_contracts(self, setup_test_data):
        """Test that pre_import_initialize prefetches all contracts."""
        contract = setup_test_data["contract"]
        options = {}
        pre_import_initialize("test-job-id", options)

        assert "_contracts_by_key" in options
        contracts_by_key = options["_contracts_by_key"]
        # Should be accessible by contract code
        assert contract.code.lower() in contracts_by_key
        # Should also be accessible by (employee_code, contract_code)
        assert ("mv000001", contract.code.lower()) in contracts_by_key

    def test_pre_import_initialize_prefetches_appendices(self, setup_test_data):
        """Test that pre_import_initialize prefetches all appendices."""
        contract = setup_test_data["contract"]
        # Create an existing appendix
        appendix = ContractAppendix.objects.create(
            contract=contract,
            sign_date=date(2024, 6, 1),
            effective_date=date(2024, 7, 1),
        )

        options = {}
        pre_import_initialize("test-job-id", options)

        assert "_appendices_by_code" in options
        appendices_by_code = options["_appendices_by_code"]
        assert appendix.code.lower() in appendices_by_code


@pytest.mark.django_db
class TestContractAppendixImportHandler:
    """Test the main contract appendix import handler."""

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
        )

        # Create contract
        contract = Contract.objects.create(
            employee=employee,
            contract_type=contract_type,
            sign_date=date(2024, 1, 1),
            effective_date=date(2024, 1, 15),
            status=Contract.ContractStatus.ACTIVE,
        )

        return {
            "province": province,
            "admin_unit": admin_unit,
            "branch": branch,
            "block": block,
            "department": department,
            "employee": employee,
            "contract_type": contract_type,
            "contract": contract,
        }

    @pytest.fixture
    def template_headers(self):
        """Standard template headers for import tests."""
        return [
            "Số Thứ Tự",
            "Mã Nhân Viên",
            "Số Hợp Đồng",
            "Số Phụ Lục",
            "Ngày Ký",
            "Ngày Hiệu Lực",
            "Nội Dung Thay Đổi",
            "Ghi Chú",
        ]

    @pytest.fixture
    def initialized_options(self, template_headers):
        """Options dict with pre-initialized data from pre_import_initialize."""
        options = {"headers": template_headers}
        pre_import_initialize("test-job-id", options)
        return options

    def test_import_handler_success_basic(self, setup_test_data, initialized_options):
        """Test successful contract appendix import with basic fields."""
        employee = setup_test_data["employee"]
        contract = setup_test_data["contract"]

        row = [
            1,  # row_number
            employee.code,  # employee_code
            contract.code,  # contract_number
            "",  # code (let system auto-generate)
            "2025-01-15",  # sign_date
            "2025-02-01",  # effective_date
            "Salary adjustment for Q1",  # content
            "Approved by HR manager",  # note
        ]

        result = import_handler(1, row, "test-job-id", initialized_options)

        assert result["ok"] is True
        assert result["action"] == "created"
        assert "appendix_code" in result

        # Verify appendix was created
        appendix = ContractAppendix.objects.get(code=result["appendix_code"])
        assert appendix.contract == contract
        assert appendix.sign_date == date(2025, 1, 15)
        assert appendix.effective_date == date(2025, 2, 1)
        assert appendix.content == "Salary adjustment for Q1"
        assert appendix.note == "Approved by HR manager"

    def test_import_handler_success_without_employee_code(self, setup_test_data, initialized_options):
        """Test successful import using only contract number."""
        contract = setup_test_data["contract"]

        row = [
            1,
            "",  # No employee_code
            contract.code,  # contract_number
            "",  # code
            "2025-01-15",
            "2025-02-01",
            "Content change",
            "",
        ]

        result = import_handler(1, row, "test-job-id", initialized_options)

        assert result["ok"] is True
        assert result["action"] == "created"

    def test_import_handler_with_custom_code(self, setup_test_data, initialized_options):
        """Test import with custom appendix code."""
        contract = setup_test_data["contract"]

        row = [
            1,
            "",
            contract.code,
            "CUSTOM-001",  # Custom code
            "2025-01-15",
            "2025-02-01",
            "",
            "",
        ]

        result = import_handler(1, row, "test-job-id", initialized_options)

        assert result["ok"] is True
        assert result["action"] == "created"

        # Verify appendix was created with custom code
        appendix = ContractAppendix.objects.get(code="CUSTOM-001")
        assert appendix.contract == contract

    def test_import_handler_missing_contract_number(self, initialized_options):
        """Test import with missing contract number - should skip."""
        row = [
            1,
            "MV000001",
            "",  # Missing contract_number
            "",
            "2025-01-15",
            "2025-02-01",
            "",
            "",
        ]

        result = import_handler(1, row, "test-job-id", initialized_options)

        assert result["ok"] is True
        assert result["action"] == "skipped"
        assert "contract number" in result["warnings"][0].lower()

    def test_import_handler_contract_not_found(self, initialized_options):
        """Test import with non-existent contract."""
        row = [
            1,
            "",
            "NONEXISTENT",  # Non-existent contract
            "",
            "2025-01-15",
            "2025-02-01",
            "",
            "",
        ]

        result = import_handler(1, row, "test-job-id", initialized_options)

        assert result["ok"] is False
        assert "not found" in result["error"]

    def test_import_handler_employee_not_found(self, setup_test_data, initialized_options):
        """Test import with non-existent employee."""
        contract = setup_test_data["contract"]

        row = [
            1,
            "NONEXISTENT",  # Non-existent employee
            contract.code,
            "",
            "2025-01-15",
            "2025-02-01",
            "",
            "",
        ]

        result = import_handler(1, row, "test-job-id", initialized_options)

        assert result["ok"] is False
        assert "not found" in result["error"]

    def test_import_handler_contract_employee_mismatch(self, setup_test_data, initialized_options):
        """Test import with contract not belonging to specified employee."""
        contract = setup_test_data["contract"]
        department = setup_test_data["department"]

        # Create another employee with unique citizen_id
        other_employee = Employee.objects.create(
            code="MV000002",
            fullname="Other Employee",
            username="otheruser",
            email="other@example.com",
            department=department,
            start_date=date(2024, 1, 1),
            citizen_id="999999999999",
        )

        # Refresh options to include new employee
        pre_import_initialize("test-job-id", initialized_options)

        row = [
            1,
            other_employee.code,  # Wrong employee
            contract.code,
            "",
            "2025-01-15",
            "2025-02-01",
            "",
            "",
        ]

        result = import_handler(1, row, "test-job-id", initialized_options)

        assert result["ok"] is False
        assert "does not belong to employee" in result["error"]

    def test_import_handler_sign_date_after_effective_date(self, setup_test_data, initialized_options):
        """Test import with sign date after effective date."""
        contract = setup_test_data["contract"]

        row = [
            1,
            "",
            contract.code,
            "",
            "2025-02-15",  # sign_date after effective_date
            "2025-02-01",
            "",
            "",
        ]

        result = import_handler(1, row, "test-job-id", initialized_options)

        assert result["ok"] is False
        assert "Sign date must be on or before effective date" in result["error"]

    def test_import_handler_skip_duplicate(self, setup_test_data, initialized_options):
        """Test import skips duplicate when allow_update=False."""
        contract = setup_test_data["contract"]

        # Create existing appendix
        existing = ContractAppendix.objects.create(
            contract=contract,
            sign_date=date(2025, 1, 15),
            effective_date=date(2025, 2, 1),
        )

        # Refresh options to include new appendix
        pre_import_initialize("test-job-id", initialized_options)

        row = [
            1,
            "",
            contract.code,
            existing.code,  # Same code as existing
            "2025-01-15",
            "2025-02-01",
            "",
            "",
        ]

        initialized_options["allow_update"] = False
        result = import_handler(1, row, "test-job-id", initialized_options)

        assert result["ok"] is True
        assert result["action"] == "skipped"
        assert "already exists" in result["warnings"][0]

    def test_import_handler_update_existing(self, setup_test_data, initialized_options):
        """Test import updates existing appendix when allow_update=True."""
        contract = setup_test_data["contract"]

        # Create existing appendix
        existing = ContractAppendix.objects.create(
            contract=contract,
            sign_date=date(2025, 1, 15),
            effective_date=date(2025, 2, 1),
            content="Original content",
        )

        # Refresh options to include new appendix
        pre_import_initialize("test-job-id", initialized_options)

        row = [
            1,
            "",
            contract.code,
            existing.code,
            "2025-01-15",
            "2025-02-01",
            "Updated content",  # New content
            "Updated note",
        ]

        initialized_options["allow_update"] = True
        result = import_handler(1, row, "test-job-id", initialized_options)

        assert result["ok"] is True
        assert result["action"] == "updated"

        # Verify appendix was updated
        existing.refresh_from_db()
        assert existing.content == "Updated content"
        assert existing.note == "Updated note"

    def test_import_handler_no_headers(self):
        """Test import fails without headers."""
        row = ["1", "MV000001", "HD001", "", "2025-01-15", "2025-02-01"]

        options = {}  # No headers
        result = import_handler(1, row, "test-job-id", options)

        assert result["ok"] is False
        assert "Headers not provided" in result["error"]

    def test_import_handler_date_formats(self, setup_test_data, initialized_options):
        """Test import with various date formats."""
        contract = setup_test_data["contract"]

        # Test DD/MM/YYYY format
        row = [
            1,
            "",
            contract.code,
            "",
            "15/01/2025",  # DD/MM/YYYY format
            "01/02/2025",
            "",
            "",
        ]

        result = import_handler(1, row, "test-job-id", initialized_options)

        assert result["ok"] is True
        assert result["action"] == "created"

        appendix = ContractAppendix.objects.get(code=result["appendix_code"])
        assert appendix.sign_date == date(2025, 1, 15)
        assert appendix.effective_date == date(2025, 2, 1)
