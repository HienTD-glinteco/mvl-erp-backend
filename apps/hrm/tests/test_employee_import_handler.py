"""Tests for employee import handler."""

import pytest
from datetime import date

from apps.core.models import AdministrativeUnit, Nationality, Province
from apps.hrm.import_handlers.employee import (
    combine_start_date,
    generate_email,
    generate_username,
    import_handler as employee_import_handler,
    is_section_header_row,
    lookup_or_create_branch,
    lookup_or_create_block,
    lookup_or_create_contract_type,
    lookup_or_create_department,
    lookup_or_create_nationality,
    lookup_or_create_position,
    normalize_header,
    parse_date,
    parse_emergency_contact,
    parse_phone,
    strip_non_digits,
)
from apps.hrm.models import (
    Block,
    Branch,
    ContractType,
    Department,
    Employee,
    Position,
)


@pytest.mark.django_db
class TestUtilityFunctions:
    """Test utility functions used in import handler."""

    def test_normalize_header(self):
        """Test header normalization."""
        assert normalize_header("Mã nhân viên") == "mã nhân viên"
        assert normalize_header("  Tên  ") == "tên"
        assert normalize_header("EMAIL") == "email"
        assert normalize_header("") == ""
        assert normalize_header(None) == ""

    def test_is_section_header_row(self):
        """Test section header detection."""
        # Section headers
        assert is_section_header_row([], "Chi nhánh: Bắc Giang") is True
        assert is_section_header_row([], "Phòng Kinh Doanh 18_BG") is True
        assert is_section_header_row([], "Khối: Hỗ trợ") is True

        # Not section headers
        assert is_section_header_row([], "CTV000000109") is False
        assert is_section_header_row([], "") is False

    def test_parse_date(self):
        """Test date parsing."""
        # Various formats
        assert parse_date("18/12/1997") == date(1997, 12, 18)
        assert parse_date("18-12-1997") == date(1997, 12, 18)
        assert parse_date("1997-12-18") == date(1997, 12, 18)
        assert parse_date("18.12.1997") == date(1997, 12, 18)

        # Invalid values
        assert parse_date("") is None
        assert parse_date("-") is None
        assert parse_date("invalid") is None
        assert parse_date(None) is None

        # Already date object
        test_date = date(2023, 1, 1)
        assert parse_date(test_date) == test_date

    def test_combine_start_date(self):
        """Test combining day, month, year into date."""
        # Valid combination
        start_date, warnings = combine_start_date(23, 12, 2023)
        assert start_date == date(2023, 12, 23)
        assert len(warnings) == 0

        # Missing day (use first day of month)
        start_date, warnings = combine_start_date(None, 12, 2023)
        assert start_date == date(2023, 12, 1)
        assert "first day of month" in warnings[0]

        # Missing month or year
        start_date, warnings = combine_start_date(23, None, 2023)
        assert start_date is None
        assert len(warnings) > 0

        # Invalid date
        start_date, warnings = combine_start_date(31, 2, 2023)
        assert start_date is None
        assert len(warnings) > 0

    def test_strip_non_digits(self):
        """Test stripping non-digit characters."""
        assert strip_non_digits("0834186111") == "0834186111"
        assert strip_non_digits("083-418-6111") == "0834186111"
        assert strip_non_digits("+84 834 186 111") == "84834186111"
        assert strip_non_digits("ABC123") == "123"
        assert strip_non_digits("") == ""
        assert strip_non_digits(None) == ""

    def test_generate_username(self):
        """Test username generation."""
        existing = set()

        # From code
        username1 = generate_username("CTV000001", "John Doe", existing)
        assert username1 == "ctv000001"

        # Ensure uniqueness
        username2 = generate_username("CTV000001", "Jane Doe", existing)
        assert username2 == "ctv0000011"

        # From fullname
        username3 = generate_username("", "Nguyễn Văn A", set())
        assert username3 == "nguyenvana"

    def test_generate_email(self):
        """Test email generation."""
        existing = set()

        # Basic generation
        email1 = generate_email("testuser", existing)
        assert email1 == "testuser@no-reply.maivietland"

        # Ensure uniqueness
        email2 = generate_email("testuser", existing)
        assert email2 == "testuser1@no-reply.maivietland"

    def test_parse_phone(self):
        """Test phone parsing and validation."""
        # Valid 10-digit phone
        phone, warnings = parse_phone("0834186111")
        assert phone == "0834186111"
        assert len(warnings) == 0

        # With non-digits (should strip)
        phone, warnings = parse_phone("083-418-6111")
        assert phone == "0834186111"
        assert len(warnings) == 0

        # Invalid length
        phone, warnings = parse_phone("12345")
        assert phone == ""
        assert len(warnings) > 0

        # Empty
        phone, warnings = parse_phone("")
        assert phone == ""
        assert len(warnings) == 0

    def test_parse_emergency_contact(self):
        """Test emergency contact parsing."""
        # Just phone number
        phone, name = parse_emergency_contact("0943973622")
        assert phone == "0943973622"
        assert name == ""

        # Name and phone
        phone, name = parse_emergency_contact("Mother - 0943973622")
        assert phone == "0943973622"
        assert name == "Mother"

        # Empty
        phone, name = parse_emergency_contact("")
        assert phone == ""
        assert name == ""


@pytest.mark.django_db
class TestReferenceLookupFunctions:
    """Test reference model lookup/creation functions."""

    @pytest.fixture
    def setup_base_data(self):
        """Create base data needed for references."""
        # Create province and administrative unit for branches
        province = Province.objects.create(name="Test Province", code="TP")
        admin_unit = AdministrativeUnit.objects.create(
            name="Test Unit",
            code="TU",
        )
        return {"province": province, "admin_unit": admin_unit}

    def test_lookup_or_create_position(self):
        """Test position lookup/creation."""
        # Create position
        position1, created1 = lookup_or_create_position("Manager")
        assert position1 is not None
        assert position1.name == "Manager"
        assert created1 is True

        # Lookup existing (case insensitive)
        position2, created2 = lookup_or_create_position("manager")
        assert position2.id == position1.id
        assert created2 is False

        # Empty name
        position3, created3 = lookup_or_create_position("")
        assert position3 is None
        assert created3 is False

    def test_lookup_or_create_contract_type(self):
        """Test contract type lookup/creation."""
        # Create contract type
        ct1, created1 = lookup_or_create_contract_type("Full Time")
        assert ct1 is not None
        assert ct1.name == "Full Time"
        assert created1 is True

        # Lookup existing
        ct2, created2 = lookup_or_create_contract_type("Full Time")
        assert ct2.id == ct1.id
        assert created2 is False

    def test_lookup_or_create_nationality(self):
        """Test nationality lookup/creation."""
        # Create nationality
        nat1, created1 = lookup_or_create_nationality("Việt Nam")
        assert nat1 is not None
        assert nat1.name == "Việt Nam"
        assert created1 is True

        # Lookup existing
        nat2, created2 = lookup_or_create_nationality("Việt Nam")
        assert nat2.id == nat1.id
        assert created2 is False

    def test_lookup_or_create_branch(self, setup_base_data):
        """Test branch lookup/creation."""
        # Create branch
        branch1, created1 = lookup_or_create_branch("Hà Nội")
        assert branch1 is not None
        assert branch1.name == "Hà Nội"
        assert created1 is True

        # Lookup existing
        branch2, created2 = lookup_or_create_branch("hà nội")
        assert branch2.id == branch1.id
        assert created2 is False

    def test_lookup_or_create_block(self, setup_base_data):
        """Test block lookup/creation."""
        branch, _ = lookup_or_create_branch("Test Branch")

        # Create block
        block1, created1 = lookup_or_create_block("Khối Kinh doanh", branch)
        assert block1 is not None
        assert block1.name == "Khối Kinh doanh"
        assert block1.branch == branch
        assert created1 is True

        # Lookup existing
        block2, created2 = lookup_or_create_block("khối kinh doanh", branch)
        assert block2.id == block1.id
        assert created2 is False

    def test_lookup_or_create_department(self, setup_base_data):
        """Test department lookup/creation."""
        branch, _ = lookup_or_create_branch("Test Branch")
        block, _ = lookup_or_create_block("Test Block", branch)

        # Create department
        dept1, created1 = lookup_or_create_department("Sales", block, branch)
        assert dept1 is not None
        assert dept1.name == "Sales"
        assert dept1.block == block
        assert dept1.branch == branch
        assert created1 is True

        # Lookup existing
        dept2, created2 = lookup_or_create_department("sales", block, branch)
        assert dept2.id == dept1.id
        assert created2 is False


@pytest.mark.django_db
class TestEmployeeImportHandler:
    """Test employee import handler."""

    @pytest.fixture
    def setup_test_data(self):
        """Setup test data for import."""
        # Create province and administrative unit
        province = Province.objects.create(name="Bắc Giang", code="BG")
        admin_unit = AdministrativeUnit.objects.create(
            name="Test Unit",
            code="TU",
        )

        # Create branch, block, department
        branch = Branch.objects.create(
            name="Bắc Giang",
            code="BG",
            province=province,
            administrative_unit=admin_unit,
        )
        block = Block.objects.create(
            name="Khối Kinh doanh 9",
            code="KD9",
            branch=branch,
            block_type=Block.BlockType.BUSINESS,
        )
        department = Department.objects.create(
            name="Phòng Kinh Doanh 18_BG",
            code="KB18",
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

    def test_skip_section_header_row(self):
        """Test that section header rows are skipped."""
        headers = [
            "STT",
            "Mã nhân viên",
            "Tên",
            "Mã MCC",
        ]
        row = ["", "Chi nhánh: Bắc Giang", "", ""]

        options = {"headers": headers}

        result = employee_import_handler(1, row, "test-job-id", options)

        assert result["ok"] is True
        assert result["action"] == "skipped"
        assert "Section header row" in result["warnings"][0]

    def test_skip_row_without_required_fields(self):
        """Test that rows without code or fullname are skipped."""
        headers = ["STT", "Mã nhân viên", "Tên", "Email"]
        row = ["1", "", "", "test@example.com"]

        options = {"headers": headers}

        result = employee_import_handler(1, row, "test-job-id", options)

        assert result["ok"] is True
        assert result["action"] == "skipped"
        assert "Missing required fields" in result["warnings"][0]

    def test_create_employee_basic(self, setup_test_data):
        """Test creating an employee with basic fields."""
        headers = [
            "STT",
            "Mã nhân viên",
            "Tên",
            "Chi nhánh",
            "Khối",
            "Phòng Ban",
            "Điện thoại",
            "Email",
        ]
        row = [
            "1",
            "CTV000001",
            "Nguyễn Văn A",
            "Bắc Giang",
            "Khối Kinh doanh 9",
            "Phòng Kinh Doanh 18_BG",
            "0834186111",
            "nguyenvana@example.com",
        ]

        options = {"headers": headers}

        result = employee_import_handler(1, row, "test-job-id", options)

        assert result["ok"] is True
        assert result["action"] == "created"
        assert result["employee_code"] == "CTV000001"

        # Verify employee was created
        employee = Employee.objects.get(code="CTV000001")
        assert employee.fullname == "Nguyễn Văn A"
        assert employee.phone == "0834186111"
        assert employee.email == "nguyenvana@example.com"
        assert employee.department.name == "Phòng Kinh Doanh 18_BG"

    def test_create_employee_with_start_date_components(self, setup_test_data):
        """Test creating employee with start date from day/month/year."""
        headers = [
            "Mã nhân viên",
            "Tên",
            "Ngày bắt đầu làm việc",
            "Tháng bắt đầu làm việc",
            "Năm bắt đầu làm việc",
            "Chi nhánh",
            "Khối",
            "Phòng Ban",
            "Điện thoại",
        ]
        row = [
            "CTV000002",
            "Trần Thị B",
            "23",
            "12",
            "2023",
            "Bắc Giang",
            "Khối Kinh doanh 9",
            "Phòng Kinh Doanh 18_BG",
            "0886809955",
        ]

        options = {"headers": headers}

        result = employee_import_handler(1, row, "test-job-id", options)

        assert result["ok"] is True
        assert result["action"] == "created"

        # Verify start date
        employee = Employee.objects.get(code="CTV000002")
        assert employee.start_date == date(2023, 12, 23)

    def test_create_employee_with_enum_mappings(self, setup_test_data):
        """Test creating employee with Vietnamese enum values."""
        headers = [
            "Mã nhân viên",
            "Tên",
            "Giới tính",
            "Tình trạng",
            "Hôn nhân",
            "Chi nhánh",
            "Khối",
            "Phòng Ban",
            "Điện thoại",
        ]
        row = [
            "CTV000003",
            "Lê Văn C",
            "Nam",
            "Chính thức",
            "Đã kết hôn",
            "Bắc Giang",
            "Khối Kinh doanh 9",
            "Phòng Kinh Doanh 18_BG",
            "0123456789",
        ]

        options = {"headers": headers}

        result = employee_import_handler(1, row, "test-job-id", options)

        assert result["ok"] is True

        # Verify enum mappings
        employee = Employee.objects.get(code="CTV000003")
        assert employee.gender == Employee.Gender.MALE
        assert employee.status == Employee.Status.ACTIVE
        assert employee.marital_status == Employee.MaritalStatus.MARRIED

    def test_create_employee_with_generated_username_email(self, setup_test_data):
        """Test employee creation with auto-generated username and email."""
        headers = [
            "Mã nhân viên",
            "Tên",
            "Chi nhánh",
            "Khối",
            "Phòng Ban",
            "Điện thoại",
        ]
        row = [
            "CTV000004",
            "Phạm Thị D",
            "Bắc Giang",
            "Khối Kinh doanh 9",
            "Phòng Kinh Doanh 18_BG",
            "0987654321",
        ]

        options = {"headers": headers}

        result = employee_import_handler(1, row, "test-job-id", options)

        assert result["ok"] is True
        assert "Generated username" in str(result["warnings"])
        assert "Generated email" in str(result["warnings"])

        # Verify generated fields
        employee = Employee.objects.get(code="CTV000004")
        assert employee.username
        assert employee.email
        assert "@no-reply.maivietland" in employee.email

    def test_create_employee_with_references(self, setup_test_data):
        """Test creating employee with reference lookups."""
        headers = [
            "Mã nhân viên",
            "Tên",
            "Loại nhân viên",
            "Chức vụ",
            "Quốc tịch",
            "Chi nhánh",
            "Khối",
            "Phòng Ban",
            "Điện thoại",
        ]
        row = [
            "CTV000005",
            "Hoàng Văn E",
            "Chính thức",
            "Trưởng Phòng",
            "Việt Nam",
            "Bắc Giang",
            "Khối Kinh doanh 9",
            "Phòng Kinh Doanh 18_BG",
            "0111222333",
        ]

        options = {"headers": headers}

        result = employee_import_handler(1, row, "test-job-id", options)

        assert result["ok"] is True

        # Verify references were created
        employee = Employee.objects.get(code="CTV000005")
        assert employee.contract_type.name == "Chính thức"
        assert employee.position.name == "Trưởng Phòng"
        assert employee.nationality.name == "Việt Nam"

    def test_update_existing_employee(self, setup_test_data):
        """Test updating an existing employee."""
        # Create initial employee
        department = setup_test_data["department"]
        employee = Employee.objects.create(
            code="CTV000006",
            fullname="Old Name",
            username="olduser",
            email="old@example.com",
            phone="0000000000",
            department=department,
            start_date=date(2020, 1, 1),
        )

        # Import with updated data
        headers = [
            "Mã nhân viên",
            "Tên",
            "Chi nhánh",
            "Khối",
            "Phòng Ban",
            "Điện thoại",
            "Email",
        ]
        row = [
            "CTV000006",
            "New Name",
            "Bắc Giang",
            "Khối Kinh doanh 9",
            "Phòng Kinh Doanh 18_BG",
            "1111111111",
            "new@example.com",
        ]

        options = {"headers": headers}

        result = employee_import_handler(1, row, "test-job-id", options)

        assert result["ok"] is True
        assert result["action"] == "updated"

        # Verify updates
        employee.refresh_from_db()
        assert employee.fullname == "New Name"
        assert employee.phone == "1111111111"
        assert employee.email == "new@example.com"

    def test_handle_invalid_phone_gracefully(self, setup_test_data):
        """Test that invalid phone is handled with warning."""
        headers = [
            "Mã nhân viên",
            "Tên",
            "Điện thoại",
            "Chi nhánh",
            "Khối",
            "Phòng Ban",
        ]
        row = [
            "CTV000007",
            "Test User",
            "12345",  # Invalid phone
            "Bắc Giang",
            "Khối Kinh doanh 9",
            "Phòng Kinh Doanh 18_BG",
        ]

        options = {"headers": headers}

        result = employee_import_handler(1, row, "test-job-id", options)

        # Should still succeed but with warning
        assert result["ok"] is True
        assert len(result["warnings"]) > 0

        # Employee should be created but without phone
        employee = Employee.objects.get(code="CTV000007")
        assert employee.phone == ""

    def test_parse_emergency_contact_field(self, setup_test_data):
        """Test parsing emergency contact field."""
        headers = [
            "Mã nhân viên",
            "Tên",
            "Liên lạc khẩn cấp",
            "Chi nhánh",
            "Khối",
            "Phòng Ban",
            "Điện thoại",
        ]
        row = [
            "CTV000008",
            "Test User",
            "0943973622",
            "Bắc Giang",
            "Khối Kinh doanh 9",
            "Phòng Kinh Doanh 18_BG",
            "1234567890",
        ]

        options = {"headers": headers}

        result = employee_import_handler(1, row, "test-job-id", options)

        assert result["ok"] is True

        # Verify emergency contact
        employee = Employee.objects.get(code="CTV000008")
        assert employee.emergency_contact_phone == "0943973622"

    def test_full_employee_row_from_srs_sample(self, setup_test_data):
        """Test importing a full employee row from SRS sample data."""
        headers = [
            "STT",
            "Mã nhân viên",
            "Tên",
            "Mã MCC",
            "Tình trạng",
            "Ngày bắt đầu làm việc",
            "Tháng bắt đầu làm việc",
            "Năm bắt đầu làm việc",
            "Loại nhân viên",
            "Chức vụ",
            "Chi nhánh",
            "Khối",
            "Phòng Ban",
            "Điện thoại",
            "Email cá nhân",
            "Email",
            "Số tài khoản VPBank",
            "Số tài khoản VietcomBank",
            "Mã số thuế",
            "Liên lạc khẩn cấp",
            "Giới tính",
            "Ngày sinh",
            "Nơi sinh",
            "Nguyên quán",
            "Hôn nhân",
            "Dân tộc",
            "Tôn giáo",
            "Quốc tịch",
            "Số passport",
            "Số CMND",
            "Ngày cấp",
            "Nơi cấp",
            "Địa chỉ cư trú",
            "Địa chỉ thường trú",
            "Tài khoản đăng nhập",
            "Ghi chú",
        ]
        row = [
            "1",
            "CTV000000109",
            "Đào Thanh Tùng",
            "7504",
            "W",  # Unknown status, should handle gracefully
            "23",
            "12",
            "2023",
            "Chính thức",
            "Trưởng Phòng Kinh Doanh",
            "Bắc Giang",
            "Khối Kinh doanh 9",
            "Phòng Kinh Doanh 18_BG",
            "0834186111",
            "daotungbds@gmail.com",
            "tungdtctv@maivietland.vn",
            "0943973622",
            "",
            "8456494039",
            "0943973622",
            "Nam",
            "18/12/1997",
            "Bắc Giang",
            "",
            "Độc thân",
            "Kinh",
            "Không",
            "Việt Nam",
            "",
            "024097014658",
            "09/08/2021",
            "Cục CS QLHC về TTXH",
            "TT Vôi, Lạng Giang, Bắc Giang",
            "TT Vôi, Lạng Giang, Bắc Giang",
            "TUNGDTCTV@MVL",
            "",
        ]

        options = {"headers": headers}

        result = employee_import_handler(1, row, "test-job-id", options)

        assert result["ok"] is True
        assert result["employee_code"] == "CTV000000109"

        # Verify comprehensive data
        employee = Employee.objects.get(code="CTV000000109")
        assert employee.fullname == "Đào Thanh Tùng"
        assert employee.attendance_code == "7504"
        assert employee.start_date == date(2023, 12, 23)
        assert employee.contract_type.name == "Chính thức"
        assert employee.position.name == "Trưởng Phòng Kinh Doanh"
        assert employee.phone == "0834186111"
        assert employee.personal_email == "daotungbds@gmail.com"
        assert employee.email == "tungdtctv@maivietland.vn"
        assert employee.tax_code == "8456494039"
        assert employee.gender == Employee.Gender.MALE
        assert employee.date_of_birth == date(1997, 12, 18)
        assert employee.place_of_birth == "Bắc Giang"
        assert employee.marital_status == Employee.MaritalStatus.SINGLE
        assert employee.ethnicity == "Kinh"
        assert employee.religion == "Không"
        assert employee.nationality.name == "Việt Nam"
        assert employee.citizen_id == "024097014658"
        assert employee.citizen_id_issued_date == date(2021, 8, 9)
        assert employee.citizen_id_issued_place == "Cục CS QLHC về TTXH"
        assert employee.residential_address == "TT Vôi, Lạng Giang, Bắc Giang"
        assert employee.permanent_address == "TT Vôi, Lạng Giang, Bắc Giang"
        assert employee.username == "TUNGDTCTV@MVL"
        assert "VPBank: 0943973622" in employee.note
