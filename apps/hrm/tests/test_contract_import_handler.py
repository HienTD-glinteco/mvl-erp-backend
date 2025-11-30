"""Tests for contract import handler."""

from datetime import date
from decimal import Decimal

import pytest

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.import_handlers.contract import (
    ContractImportSerializer,
    copy_snapshot_from_contract_type,
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
    FlexibleBooleanField,
    FlexibleChoiceField,
    FlexibleDateField,
    FlexibleDecimalField,
    normalize_value,
)
from libs.strings import normalize_header


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


@pytest.mark.django_db
class TestFlexibleFields:
    """Test FlexibleFields from libs.drf.serializers."""

    def test_flexible_date_field_valid_iso(self):
        """Test FlexibleDateField with ISO format."""
        field = FlexibleDateField()
        assert field.to_internal_value("2025-01-15") == date(2025, 1, 15)

    def test_flexible_date_field_valid_european(self):
        """Test FlexibleDateField with DD/MM/YYYY format."""
        field = FlexibleDateField()
        assert field.to_internal_value("15/01/2025") == date(2025, 1, 15)

    def test_flexible_date_field_valid_dash(self):
        """Test FlexibleDateField with DD-MM-YYYY format."""
        field = FlexibleDateField()
        assert field.to_internal_value("15-01-2025") == date(2025, 1, 15)

    def test_flexible_date_field_object(self):
        """Test FlexibleDateField with date object."""
        field = FlexibleDateField()
        test_date = date(2025, 1, 15)
        assert field.to_internal_value(test_date) == test_date

    def test_flexible_date_field_empty(self):
        """Test FlexibleDateField with empty value."""
        field = FlexibleDateField()
        assert field.to_internal_value("") is None
        assert field.to_internal_value("-") is None
        assert field.to_internal_value(None) is None

    def test_flexible_decimal_field_integer(self):
        """Test FlexibleDecimalField with integer."""
        field = FlexibleDecimalField(max_digits=20, decimal_places=0)
        assert field.to_internal_value(15000000) == Decimal("15000000")

    def test_flexible_decimal_field_with_comma_decimal(self):
        """Test FlexibleDecimalField with comma as decimal separator."""
        field = FlexibleDecimalField(max_digits=20, decimal_places=2)
        assert field.to_internal_value("15000,50") == Decimal("15000.50")

    def test_flexible_decimal_field_plain_string(self):
        """Test FlexibleDecimalField with plain string."""
        field = FlexibleDecimalField(max_digits=20, decimal_places=0)
        assert field.to_internal_value("15000000") == Decimal("15000000")

    def test_flexible_decimal_field_empty(self):
        """Test FlexibleDecimalField with empty value."""
        field = FlexibleDecimalField(max_digits=20, decimal_places=0)
        assert field.to_internal_value("") is None
        assert field.to_internal_value(None) is None

    def test_flexible_boolean_field_vietnamese_true(self):
        """Test FlexibleBooleanField with Vietnamese true values."""
        field = FlexibleBooleanField()
        assert field.to_internal_value("có") is True
        assert field.to_internal_value("Có") is True

    def test_flexible_boolean_field_vietnamese_false(self):
        """Test FlexibleBooleanField with Vietnamese false values."""
        field = FlexibleBooleanField()
        assert field.to_internal_value("không") is False
        assert field.to_internal_value("Không") is False

    def test_flexible_boolean_field_english(self):
        """Test FlexibleBooleanField with English values."""
        field = FlexibleBooleanField()
        assert field.to_internal_value("yes") is True
        assert field.to_internal_value("no") is False
        assert field.to_internal_value("true") is True
        assert field.to_internal_value("false") is False

    def test_flexible_boolean_field_native(self):
        """Test FlexibleBooleanField with native bool."""
        field = FlexibleBooleanField()
        assert field.to_internal_value(True) is True
        assert field.to_internal_value(False) is False

    def test_flexible_boolean_field_empty(self):
        """Test FlexibleBooleanField with empty value."""
        field = FlexibleBooleanField()
        assert field.to_internal_value("") is None
        assert field.to_internal_value(None) is None

    def test_flexible_choice_field_with_mapping(self):
        """Test FlexibleChoiceField with value mapping."""
        choices = [("full", "Full"), ("reduced", "Reduced")]
        mapping = {"100": "full", "100%": "full", "85": "reduced", "85%": "reduced"}
        field = FlexibleChoiceField(choices=choices, value_mapping=mapping)

        assert field.to_internal_value("100") == "full"
        assert field.to_internal_value("100%") == "full"
        assert field.to_internal_value("85") == "reduced"
        assert field.to_internal_value("85%") == "reduced"

    def test_flexible_choice_field_direct_value(self):
        """Test FlexibleChoiceField with direct choice value."""
        choices = [("full", "Full"), ("reduced", "Reduced")]
        field = FlexibleChoiceField(choices=choices)

        assert field.to_internal_value("full") == "full"
        assert field.to_internal_value("Full") == "full"
        assert field.to_internal_value("FULL") == "full"

    def test_flexible_choice_field_empty(self):
        """Test FlexibleChoiceField with empty value."""
        choices = [("full", "Full"), ("reduced", "Reduced")]
        field = FlexibleChoiceField(choices=choices)

        assert field.to_internal_value("") is None
        assert field.to_internal_value(None) is None


@pytest.mark.django_db
class TestContractImportSerializer:
    """Test ContractImportSerializer validation."""

    def test_serializer_valid_data(self):
        """Test serializer with valid data."""
        data = {
            "sign_date": date(2025, 1, 15),
            "effective_date": date(2025, 2, 1),
        }

        serializer = ContractImportSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_serializer_date_validation(self):
        """Test serializer date validation."""
        # Sign date after effective date
        data = {
            "sign_date": date(2025, 2, 15),
            "effective_date": date(2025, 2, 1),
        }

        serializer = ContractImportSerializer(data=data)
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
        return {
            "employee": employee,
            "contract_type": contract_type,
        }

    def test_pre_import_initialize_prefetches_employees(self, setup_test_data):
        """Test that pre_import_initialize prefetches all employees."""
        options = {}
        pre_import_initialize("test-job-id", options)

        assert "_employees_by_code" in options
        employees_by_code = options["_employees_by_code"]
        assert "mv000001" in employees_by_code
        assert employees_by_code["mv000001"].fullname == "Test Employee"

    def test_pre_import_initialize_prefetches_contract_types(self, setup_test_data):
        """Test that pre_import_initialize prefetches all contract types."""
        contract_type = setup_test_data["contract_type"]
        options = {}
        pre_import_initialize("test-job-id", options)

        assert "_contract_types_by_code" in options
        contract_types_by_code = options["_contract_types_by_code"]
        assert contract_type.code.lower() in contract_types_by_code
        assert contract_types_by_code[contract_type.code.lower()].name == "Full-time Employment"


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

    @pytest.fixture
    def initialized_options(self, template_headers):
        """Options dict with pre-initialized data from pre_import_initialize."""
        options = {"headers": template_headers}
        pre_import_initialize("test-job-id", options)
        return options

    def test_import_handler_success_basic(self, setup_test_data, initialized_options):
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

        result = import_handler(1, row, "test-job-id", initialized_options)

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

    def test_import_handler_with_custom_salary(self, setup_test_data, initialized_options):
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

        result = import_handler(1, row, "test-job-id", initialized_options)

        assert result["ok"] is True
        assert result["action"] == "created"

        contract = Contract.objects.get(code=result["contract_code"])
        assert contract.base_salary == Decimal("20000000")
        assert contract.lunch_allowance == Decimal("600000")
        assert contract.phone_allowance == Decimal("300000")
        assert contract.other_allowance == Decimal("150000")
        assert contract.expiration_date is None

    def test_import_handler_missing_employee_code(self, initialized_options):
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

        result = import_handler(1, row, "test-job-id", initialized_options)

        assert result["ok"] is True
        assert result["action"] == "skipped"
        assert "employee code" in result["warnings"][0].lower()

    def test_import_handler_missing_contract_type_code(self, setup_test_data, initialized_options):
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

        result = import_handler(1, row, "test-job-id", initialized_options)

        assert result["ok"] is True
        assert result["action"] == "skipped"
        assert "contract type code" in result["warnings"][0].lower()

    def test_import_handler_employee_not_found(self, setup_test_data, initialized_options):
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

        result = import_handler(1, row, "test-job-id", initialized_options)

        assert result["ok"] is False
        assert "not found" in result["error"]

    def test_import_handler_contract_type_not_found(self, setup_test_data, initialized_options):
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

        result = import_handler(1, row, "test-job-id", initialized_options)

        assert result["ok"] is False
        assert "not found" in result["error"]

    def test_import_handler_sign_date_after_effective_date(self, setup_test_data, initialized_options):
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

        result = import_handler(1, row, "test-job-id", initialized_options)

        assert result["ok"] is False
        assert "Sign date must be on or before effective date" in result["error"]

    def test_import_handler_expiration_before_effective(self, setup_test_data, initialized_options):
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

        result = import_handler(1, row, "test-job-id", initialized_options)

        assert result["ok"] is False
        assert "Expiration date must be on or after effective date" in result["error"]

    def test_import_handler_skip_duplicate(self, setup_test_data, initialized_options):
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

        initialized_options["allow_update"] = False
        result = import_handler(1, row, "test-job-id", initialized_options)

        assert result["ok"] is True
        assert result["action"] == "skipped"
        assert "already exists" in result["warnings"][0]

    def test_import_handler_update_existing(self, setup_test_data, initialized_options):
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

        initialized_options["allow_update"] = True
        result = import_handler(1, row, "test-job-id", initialized_options)

        assert result["ok"] is True
        assert result["action"] == "updated"

        # Verify contract was updated
        existing.refresh_from_db()
        assert existing.expiration_date == date(2026, 2, 1)
        assert existing.base_salary == Decimal("20000000")
        assert existing.note == "Updated note"

    def test_import_handler_cannot_update_non_draft(self, setup_test_data, initialized_options):
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

        initialized_options["allow_update"] = True
        result = import_handler(1, row, "test-job-id", initialized_options)

        assert result["ok"] is False
        assert "only DRAFT contracts can be updated" in result["error"]

    def test_import_handler_no_headers(self):
        """Test import fails without headers."""
        row = ["1", "MV000001", "LHD001", "2025-01-15", "2025-02-01"]

        options = {}  # No headers
        result = import_handler(1, row, "test-job-id", options)

        assert result["ok"] is False
        assert "Headers not provided" in result["error"]

    def test_import_handler_with_boolean_and_enum_fields(self, setup_test_data, initialized_options):
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

        result = import_handler(1, row, "test-job-id", initialized_options)

        assert result["ok"] is True
        assert result["action"] == "created"

        contract = Contract.objects.get(code=result["contract_code"])
        assert contract.net_percentage == ContractType.NetPercentage.REDUCED
        assert contract.tax_calculation_method == ContractType.TaxCalculationMethod.FLAT_10
        assert contract.has_social_insurance is False
        assert contract.working_conditions == "Custom conditions"
