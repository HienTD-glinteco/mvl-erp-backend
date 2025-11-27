"""Tests for employee_type mapping utilities and import handler changes."""

from datetime import date

import pytest

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.constants import EmployeeType
from apps.hrm.import_handlers.employee import (
    import_handler as employee_import_handler,
    map_import_contract_type_to_employee_type,
)
from apps.hrm.models import (
    Block,
    Branch,
    ContractType,
    Department,
    Employee,
)
from apps.hrm.utils.employee_type_mapping import (
    get_employee_type_mapping,
    map_contract_type_to_employee_type,
    normalize_text,
    suggest_employee_type,
)


@pytest.mark.django_db
class TestNormalizeText:
    """Test the normalize_text function for accent-insensitive matching."""

    def test_normalize_vietnamese_accents(self):
        """Test removal of Vietnamese diacritics."""
        assert normalize_text("Chính thức") == "chinh thuc"
        assert normalize_text("Học việc") == "hoc viec"
        assert normalize_text("Thử việc") == "thu viec"
        assert normalize_text("Thực tập") == "thuc tap"
        assert normalize_text("Nghỉ không lương") == "nghi khong luong"

    def test_normalize_case(self):
        """Test lowercase conversion."""
        assert normalize_text("OFFICIAL") == "official"
        assert normalize_text("Probation") == "probation"
        assert normalize_text("INTERN") == "intern"

    def test_normalize_whitespace(self):
        """Test whitespace normalization."""
        assert normalize_text("  Chính   thức  ") == "chinh thuc"
        assert normalize_text("Học\tviec") == "hoc viec"

    def test_normalize_empty(self):
        """Test empty and None handling."""
        assert normalize_text("") == ""
        assert normalize_text(None) == ""


@pytest.mark.django_db
class TestMapContractTypeToEmployeeType:
    """Test the contract type to employee type mapping function."""

    def test_map_official(self):
        """Test mapping official contract types."""
        employee_type, mapped = map_contract_type_to_employee_type("Chính thức")
        assert mapped is True
        assert employee_type == EmployeeType.OFFICIAL

        employee_type, mapped = map_contract_type_to_employee_type("official")
        assert mapped is True
        assert employee_type == EmployeeType.OFFICIAL

    def test_map_apprentice(self):
        """Test mapping apprentice contract types."""
        employee_type, mapped = map_contract_type_to_employee_type("Học việc")
        assert mapped is True
        assert employee_type == EmployeeType.APPRENTICE

    def test_map_probation(self):
        """Test mapping probation contract types."""
        employee_type, mapped = map_contract_type_to_employee_type("Thử việc")
        assert mapped is True
        assert employee_type == EmployeeType.PROBATION

    def test_map_intern(self):
        """Test mapping intern contract types."""
        employee_type, mapped = map_contract_type_to_employee_type("Thực tập")
        assert mapped is True
        assert employee_type == EmployeeType.INTERN

    def test_map_unpaid_official(self):
        """Test mapping unpaid official contract types."""
        employee_type, mapped = map_contract_type_to_employee_type("Nghỉ không lương")
        assert mapped is True
        assert employee_type == EmployeeType.UNPAID_OFFICIAL

    def test_unmapped_returns_none(self):
        """Test that unmapped contract types return None."""
        employee_type, mapped = map_contract_type_to_employee_type("Unknown Type")
        assert mapped is False
        assert employee_type is None

    def test_empty_returns_none(self):
        """Test that empty values return None."""
        employee_type, mapped = map_contract_type_to_employee_type("")
        assert mapped is False
        assert employee_type is None

        employee_type, mapped = map_contract_type_to_employee_type(None)
        assert mapped is False
        assert employee_type is None

    def test_custom_mapping(self):
        """Test that custom mapping overrides defaults."""
        custom_mapping = {"custom type": EmployeeType.INTERN}
        employee_type, mapped = map_contract_type_to_employee_type(
            "Custom Type", custom_mapping=custom_mapping
        )
        assert mapped is True
        assert employee_type == EmployeeType.INTERN

    def test_pk_mapping(self):
        """Test that PK mapping takes priority."""
        pk_mapping = {123: EmployeeType.APPRENTICE}
        employee_type, mapped = map_contract_type_to_employee_type(
            "Chính thức",  # This would normally map to OFFICIAL
            contract_type_pk=123,
            pk_mapping=pk_mapping,
        )
        assert mapped is True
        assert employee_type == EmployeeType.APPRENTICE


@pytest.mark.django_db
class TestSuggestEmployeeType:
    """Test the employee type suggestion function."""

    def test_suggest_official(self):
        """Test suggestion for official-like types."""
        assert suggest_employee_type("Nhân viên chính thức mới") == EmployeeType.OFFICIAL
        assert suggest_employee_type("official employee") == EmployeeType.OFFICIAL

    def test_suggest_probation(self):
        """Test suggestion for probation-like types."""
        assert suggest_employee_type("Nhân viên thử việc") == EmployeeType.PROBATION

    def test_suggest_intern(self):
        """Test suggestion for intern-like types."""
        assert suggest_employee_type("Sinh viên thực tập") == EmployeeType.INTERN

    def test_suggest_none_for_unknown(self):
        """Test that unknown types return None."""
        assert suggest_employee_type("Completely Unknown") is None


@pytest.mark.django_db
class TestGetEmployeeTypeMapping:
    """Test the mapping dictionary generation."""

    def test_default_mapping_has_entries(self):
        """Test that default mapping has expected entries."""
        mapping = get_employee_type_mapping()
        assert len(mapping) > 0
        assert "chinh thuc" in mapping
        assert mapping["chinh thuc"] == EmployeeType.OFFICIAL

    def test_custom_mapping_extends_default(self):
        """Test that custom mapping extends defaults."""
        custom = {"new key": EmployeeType.INTERN}
        mapping = get_employee_type_mapping(custom)
        assert "new key" in mapping
        assert "chinh thuc" in mapping  # Default still present


@pytest.mark.django_db
class TestMapImportContractTypeToEmployeeType:
    """Test the import handler mapping function."""

    def test_map_with_known_type(self):
        """Test mapping with a known contract type."""
        employee_type, was_mapped, warning = map_import_contract_type_to_employee_type(
            "Chính thức", {}
        )
        assert employee_type == EmployeeType.OFFICIAL
        assert was_mapped is True
        assert warning is None

    def test_map_with_unknown_type_non_strict(self):
        """Test mapping with unknown type in non-strict mode."""
        employee_type, was_mapped, warning = map_import_contract_type_to_employee_type(
            "Unknown Type", {"import_employee_type_strict": False}
        )
        assert employee_type is None
        assert was_mapped is False
        assert warning is not None
        assert "Unmapped" in warning

    def test_map_with_empty_value(self):
        """Test mapping with empty value."""
        employee_type, was_mapped, warning = map_import_contract_type_to_employee_type("", {})
        assert employee_type is None
        assert was_mapped is False
        assert warning is None


@pytest.mark.django_db
class TestImportHandlerEmployeeType:
    """Test that import handler sets employee_type instead of creating ContractType."""

    @pytest.fixture
    def setup_test_data(self):
        """Setup test data for import."""
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

        return {
            "province": province,
            "admin_unit": admin_unit,
            "branch": branch,
            "block": block,
            "department": department,
        }

    def test_import_sets_employee_type_for_known_contract_type(self, setup_test_data):
        """Test that import sets employee_type for known contract type values."""
        initial_contract_type_count = ContractType.objects.count()

        headers = [
            "Mã nhân viên",
            "Tên",
            "Loại nhân viên",
            "Chi nhánh",
            "Khối",
            "Phòng Ban",
            "Điện thoại",
        ]
        row = [
            "TEST001",
            "Test Employee",
            "Chính thức",  # Should map to OFFICIAL employee_type
            "Test Branch",
            "Test Block",
            "Test Department",
            "0123456789",
        ]

        options = {"headers": headers}
        result = employee_import_handler(1, row, "test-job-id", options)

        assert result["ok"] is True
        assert result["action"] == "created"

        # Verify employee was created with employee_type set
        employee = Employee.objects.get(code="TEST001")
        assert employee.employee_type == EmployeeType.OFFICIAL

        # Verify no new ContractType was created
        assert ContractType.objects.count() == initial_contract_type_count

    def test_import_does_not_create_contract_type(self, setup_test_data):
        """Test that import does NOT create new ContractType records."""
        initial_contract_type_count = ContractType.objects.count()

        headers = [
            "Mã nhân viên",
            "Tên",
            "Loại nhân viên",
            "Chi nhánh",
            "Khối",
            "Phòng Ban",
            "Điện thoại",
        ]
        row = [
            "TEST002",
            "Another Employee",
            "Học việc",  # Apprentice type
            "Test Branch",
            "Test Block",
            "Test Department",
            "0987654321",
        ]

        options = {"headers": headers}
        result = employee_import_handler(1, row, "test-job-id", options)

        assert result["ok"] is True

        # Verify employee was created
        employee = Employee.objects.get(code="TEST002")
        assert employee.employee_type == EmployeeType.APPRENTICE

        # Verify ContractType table is unchanged
        assert ContractType.objects.count() == initial_contract_type_count

    def test_import_with_unmapped_contract_type_sets_null(self, setup_test_data):
        """Test that unmapped contract type values result in NULL employee_type."""
        initial_contract_type_count = ContractType.objects.count()

        headers = [
            "Mã nhân viên",
            "Tên",
            "Loại nhân viên",
            "Chi nhánh",
            "Khối",
            "Phòng Ban",
            "Điện thoại",
        ]
        row = [
            "TEST003",
            "Third Employee",
            "Some Unknown Type",  # Unknown type
            "Test Branch",
            "Test Block",
            "Test Department",
            "0111222333",
        ]

        options = {"headers": headers}
        result = employee_import_handler(1, row, "test-job-id", options)

        assert result["ok"] is True

        # Verify employee was created with NULL employee_type
        employee = Employee.objects.get(code="TEST003")
        assert employee.employee_type is None

        # Verify warning was generated
        assert any("Unmapped" in w for w in result.get("warnings", []))

        # Verify no ContractType was created
        assert ContractType.objects.count() == initial_contract_type_count

    def test_import_without_contract_type_field(self, setup_test_data):
        """Test import when contract_type field is empty."""
        headers = [
            "Mã nhân viên",
            "Tên",
            "Chi nhánh",
            "Khối",
            "Phòng Ban",
            "Điện thoại",
        ]
        row = [
            "TEST004",
            "Fourth Employee",
            "Test Branch",
            "Test Block",
            "Test Department",
            "0444555666",
        ]

        options = {"headers": headers}
        result = employee_import_handler(1, row, "test-job-id", options)

        assert result["ok"] is True

        # Verify employee was created with NULL employee_type
        employee = Employee.objects.get(code="TEST004")
        assert employee.employee_type is None

    def test_repeated_import_is_idempotent(self, setup_test_data):
        """Test that repeated imports don't create duplicate ContractType records."""
        initial_contract_type_count = ContractType.objects.count()

        headers = [
            "Mã nhân viên",
            "Tên",
            "Loại nhân viên",
            "Chi nhánh",
            "Khối",
            "Phòng Ban",
            "Điện thoại",
        ]

        # Import same contract type value multiple times
        for i in range(3):
            row = [
                f"TEST00{5 + i}",
                f"Employee {5 + i}",
                "Chính thức",
                "Test Branch",
                "Test Block",
                "Test Department",
                f"0{i}{i}{i}{i}{i}{i}{i}{i}{i}{i}",
            ]
            options = {"headers": headers}
            result = employee_import_handler(1, row, "test-job-id", options)
            assert result["ok"] is True

        # Verify no ContractType records were created
        assert ContractType.objects.count() == initial_contract_type_count

        # Verify all employees have the correct employee_type
        employees = Employee.objects.filter(code__startswith="TEST00")
        for emp in employees:
            if emp.code in ["TEST005", "TEST006", "TEST007"]:
                assert emp.employee_type == EmployeeType.OFFICIAL


@pytest.mark.django_db
class TestEmployeeTypeFieldOnModel:
    """Test the employee_type field on the Employee model."""

    @pytest.fixture
    def setup_employee_data(self):
        """Create minimal data needed for Employee."""
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
        return {"department": department}

    def test_employee_type_is_nullable(self, setup_employee_data):
        """Test that employee_type can be null."""
        employee = Employee.objects.create(
            code="TESTEMP001",
            fullname="Test Employee",
            username="testuser001",
            email="test001@example.com",
            phone="0123456789",
            department=setup_employee_data["department"],
            start_date=date.today(),
            employee_type=None,
        )
        assert employee.employee_type is None

    def test_employee_type_accepts_valid_choices(self, setup_employee_data):
        """Test that employee_type accepts all valid choices."""
        for choice_value, choice_label in EmployeeType.choices:
            employee = Employee.objects.create(
                code=f"TESTEMP_{choice_value}",
                fullname=f"Test {choice_label}",
                username=f"testuser_{choice_value.lower()}",
                email=f"test_{choice_value.lower()}@example.com",
                phone="0123456789",
                department=setup_employee_data["department"],
                start_date=date.today(),
                employee_type=choice_value,
            )
            assert employee.employee_type == choice_value
            employee.delete()  # Clean up
