"""Tests for recruitment candidate import handler."""

from datetime import date

import pytest

from apps.hrm.import_handlers.recruitment_candidate import (
    convert_months_to_experience,
    find_or_create_recruitment_request,
    get_or_create_recruitment_channel,
    get_or_create_recruitment_source,
    import_handler,
    normalize_text,
    parse_date_field,
    parse_integer_field,
    validate_citizen_id,
    validate_email,
)
from apps.hrm.models import (
    Block,
    Branch,
    Department,
    Employee,
    JobDescription,
    RecruitmentCandidate,
    RecruitmentChannel,
    RecruitmentRequest,
    RecruitmentSource,
)


@pytest.mark.django_db
class TestUtilityFunctions:
    """Test utility functions used in import handler."""

    def test_normalize_text(self):
        """Test text normalization."""
        assert normalize_text("  Phòng IT  ") == "phòng it"
        assert normalize_text("CHI  NHÁNH   HÀ NỘI") == "chi nhánh hà nội"
        assert normalize_text("LinkedIn") == "linkedin"
        assert normalize_text("") == ""
        assert normalize_text(None) == ""
        assert normalize_text("   ") == ""

    def test_parse_integer_field(self):
        """Test integer parsing."""
        # Valid integers
        value, error = parse_integer_field(84, "months", min_value=0)
        assert value == 84
        assert error is None

        value, error = parse_integer_field("48", "months", min_value=0)
        assert value == 48
        assert error is None

        # Below minimum
        value, error = parse_integer_field(-5, "months", min_value=0)
        assert value is None
        assert "at least 0" in error

        # Above maximum
        value, error = parse_integer_field(10, "status", min_value=1, max_value=7)
        assert value is None
        assert "at most 7" in error

        # Invalid value
        value, error = parse_integer_field("abc", "months")
        assert value is None
        assert "Invalid integer" in error

        # Empty value
        value, error = parse_integer_field("", "months")
        assert value is None
        assert error is None

        value, error = parse_integer_field(None, "months")
        assert value is None
        assert error is None

    def test_parse_date_field(self):
        """Test date parsing."""
        # Valid date
        parsed_date, error = parse_date_field("2025-11-01", "submitted_date")
        assert parsed_date == date(2025, 11, 1)
        assert error is None

        # Invalid format
        parsed_date, error = parse_date_field("11/01/2025", "submitted_date")
        assert parsed_date is None
        assert "Invalid date format" in error

        # Empty value
        parsed_date, error = parse_date_field("", "submitted_date")
        assert parsed_date is None
        assert error is None

        # Already a date object
        test_date = date(2025, 11, 1)
        parsed_date, error = parse_date_field(test_date, "submitted_date")
        assert parsed_date == test_date
        assert error is None

    def test_validate_citizen_id(self):
        """Test citizen ID validation."""
        # Valid 12 digits
        error = validate_citizen_id("123456789012")
        assert error is None

        # With spaces/dashes (should be cleaned)
        error = validate_citizen_id("123-456-789-012")
        assert error is None

        # Too short
        error = validate_citizen_id("12345")
        assert "exactly 12 digits" in error

        # Too long
        error = validate_citizen_id("1234567890123")
        assert "exactly 12 digits" in error

        # Empty
        error = validate_citizen_id("")
        assert "required" in error

    def test_validate_email(self):
        """Test email validation."""
        # Valid emails
        assert validate_email("test@example.com") is None
        assert validate_email("user.name+tag@example.co.uk") is None

        # Invalid emails
        assert validate_email("invalid") is not None
        assert validate_email("@example.com") is not None
        assert validate_email("user@") is not None

        # Empty
        assert validate_email("") is not None

    def test_convert_months_to_experience(self):
        """Test months to experience conversion."""
        assert convert_months_to_experience(0) == RecruitmentCandidate.YearsOfExperience.NO_EXPERIENCE
        assert convert_months_to_experience(6) == RecruitmentCandidate.YearsOfExperience.LESS_THAN_ONE_YEAR
        assert convert_months_to_experience(11) == RecruitmentCandidate.YearsOfExperience.LESS_THAN_ONE_YEAR
        assert convert_months_to_experience(18) == RecruitmentCandidate.YearsOfExperience.ONE_TO_THREE_YEARS
        assert convert_months_to_experience(36) == RecruitmentCandidate.YearsOfExperience.ONE_TO_THREE_YEARS
        assert convert_months_to_experience(48) == RecruitmentCandidate.YearsOfExperience.THREE_TO_FIVE_YEARS
        assert convert_months_to_experience(60) == RecruitmentCandidate.YearsOfExperience.THREE_TO_FIVE_YEARS
        assert convert_months_to_experience(84) == RecruitmentCandidate.YearsOfExperience.MORE_THAN_FIVE_YEARS
        assert convert_months_to_experience(120) == RecruitmentCandidate.YearsOfExperience.MORE_THAN_FIVE_YEARS


@pytest.mark.django_db
class TestEntityCreation:
    """Test entity lookup and creation functions."""

    def test_get_or_create_recruitment_source_existing(self):
        """Test getting existing recruitment source."""
        # Create existing source
        existing_source = RecruitmentSource.objects.create(name="LinkedIn", allow_referral=False)

        cache = {}
        source, error = get_or_create_recruitment_source("LinkedIn", cache)

        assert error is None
        assert source.id == existing_source.id
        assert source.name == "LinkedIn"

        # Should be cached
        assert "source_linkedin" in cache

    def test_get_or_create_recruitment_source_case_insensitive(self):
        """Test case-insensitive lookup for recruitment source."""
        # Create source with mixed case
        existing_source = RecruitmentSource.objects.create(name="LinkedIn", allow_referral=False)

        cache = {}
        # Lookup with different case
        source, error = get_or_create_recruitment_source("linkedin", cache)

        assert error is None
        assert source.id == existing_source.id

    def test_get_or_create_recruitment_source_new(self):
        """Test creating new recruitment source."""
        cache = {}
        source, error = get_or_create_recruitment_source("TopCV", cache)

        assert error is None
        assert source is not None
        assert source.name == "TopCV"
        assert source.allow_referral is False
        assert source.description == "Auto-created from import"
        assert source.code.startswith("RS")

    def test_get_or_create_recruitment_channel_existing(self):
        """Test getting existing recruitment channel."""
        existing_channel = RecruitmentChannel.objects.create(
            name="Website Tuyển Dụng", belong_to=RecruitmentChannel.BelongTo.JOB_WEBSITE
        )

        cache = {}
        channel, error = get_or_create_recruitment_channel("Website Tuyển Dụng", cache)

        assert error is None
        assert channel.id == existing_channel.id

    def test_get_or_create_recruitment_channel_new(self):
        """Test creating new recruitment channel."""
        cache = {}
        channel, error = get_or_create_recruitment_channel("Mạng Xã Hội", cache)

        assert error is None
        assert channel is not None
        assert channel.name == "Mạng Xã Hội"
        assert channel.belong_to == RecruitmentChannel.BelongTo.JOB_WEBSITE
        assert channel.description == "Auto-created from import"

    def test_find_or_create_recruitment_request_existing(self, sample_department, sample_branch, sample_block):
        """Test finding existing recruitment request."""
        # Create job description
        job_desc = JobDescription.objects.create(
            title="Backend Developer",
            position_title="Backend Developer",
            responsibility="Coding",
            requirement="Python",
            benefit="Salary",
            proposed_salary="Negotiable",
        )

        # Create existing request
        proposer = Employee.objects.create(
            code="MV0001",
            fullname="Test Proposer",
            username="proposer",
            email="proposer@test.com",
            phone="0977777777",
            citizen_id="777777777777",  # Unique citizen ID
            start_date=date.today(),
            status=Employee.Status.ACTIVE,
            branch=sample_branch,
            block=sample_block,
            department=sample_department,
            personal_email="proposer.personal@test.com",
        )

        existing_request = RecruitmentRequest.objects.create(
            name="Tuyển Backend Developer Senior",
            job_description=job_desc,
            department=sample_department,
            proposer=proposer,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            status=RecruitmentRequest.Status.OPEN,
            proposed_salary="Negotiable",
            number_of_positions=2,
        )

        cache = {}
        request, error = find_or_create_recruitment_request("Tuyển Backend Developer Senior", sample_department, cache)

        assert error is None
        assert request.id == existing_request.id

    def test_find_or_create_recruitment_request_new(self, sample_department, sample_branch, sample_block):
        """Test creating new recruitment request."""
        # Create proposer
        proposer = Employee.objects.create(
            code="MV0001",
            fullname="Test Proposer",
            username="proposer",
            email="proposer@test.com",
            phone="0966666666",
            citizen_id="666666666666",  # Unique citizen ID
            start_date=date.today(),
            status=Employee.Status.ACTIVE,
            branch=sample_branch,
            block=sample_block,
            department=sample_department,
            personal_email="proposer.new.personal@test.com",
        )

        cache = {}
        request, error = find_or_create_recruitment_request("Tuyển Frontend Developer", sample_department, cache)

        assert error is None
        assert request is not None
        assert request.name == "Tuyển Frontend Developer"
        assert request.department == sample_department
        assert request.proposer == proposer
        assert request.recruitment_type == RecruitmentRequest.RecruitmentType.NEW_HIRE
        assert request.status == RecruitmentRequest.Status.DRAFT
        assert request.code.startswith("RR")

        # Check job description was created
        assert request.job_description is not None
        assert request.job_description.title == "Tuyển Frontend Developer"


@pytest.mark.django_db
class TestImportHandler:
    """Test the main import handler function."""

    def test_import_handler_success(
        self, sample_branch, sample_block, sample_department, sample_proposer, template_headers
    ):
        """Test successful candidate import."""
        row = [
            1,  # row_number
            "Nguyễn Văn An",  # name
            "123456789001",  # citizen_id
            "nguyenvanan@example.com",  # email
            "0912345678",  # phone
            "Tuyển Backend Developer Senior",  # recruitment_request_name
            "LinkedIn",  # recruitment_source_name
            "Website Tuyển Dụng",  # recruitment_channel_name
            sample_department.name,  # department_name
            sample_block.name,  # block_name
            sample_branch.name,  # branch_name
            "",  # referrer_code (empty)
            84,  # months_of_experience
            "2025-11-01",  # submitted_date
            1,  # status (CONTACTED)
            "",  # onboard_date (empty for CONTACTED status)
            "Ứng viên có 7 năm kinh nghiệm",  # note
        ]

        options = {"headers": template_headers}
        result = import_handler(1, row, "test-job-id", options)

        assert result["ok"] is True
        assert result["action"] == "created"
        assert "result" in result
        assert "candidate_code" in result["result"]
        assert result["result"]["candidate_code"].startswith("UV")

        # Verify candidate was created
        candidate = RecruitmentCandidate.objects.get(citizen_id="123456789001")
        assert candidate.name == "Nguyễn Văn An"
        assert candidate.email == "nguyenvanan@example.com"
        assert candidate.phone == "0912345678"
        assert candidate.status == RecruitmentCandidate.Status.CONTACTED
        assert candidate.years_of_experience == RecruitmentCandidate.YearsOfExperience.MORE_THAN_FIVE_YEARS
        assert candidate.submitted_date == date(2025, 11, 1)
        assert candidate.note == "Ứng viên có 7 năm kinh nghiệm"
        assert candidate.referrer is None

        # Verify organizational structure is set
        assert candidate.branch == sample_branch
        assert candidate.block == sample_block
        assert candidate.department == sample_department

    def test_import_handler_with_referrer(
        self, sample_branch, sample_block, sample_department, sample_proposer, template_headers
    ):
        """Test candidate import with referrer."""
        # Create referrer employee
        referrer = Employee.objects.create(
            code="MV0005",
            fullname="Test Referrer",
            username="referrer",
            email="referrer@test.com",
            phone="0999999999",
            citizen_id="999999999999",  # Unique citizen ID for referrer
            start_date=date.today(),
            status=Employee.Status.ACTIVE,
            branch=sample_branch,
            block=sample_block,
            department=sample_department,
            personal_email="referrer.personal@test.com",
        )
        row = [
            1,
            "Hoàng Văn Em",
            "123456789005",
            "hoangvanem@example.com",
            "0956789012",
            "Tuyển DevOps Engineer",
            "LinkedIn",
            "Quảng Cáo Online",
            sample_department.name,
            sample_block.name,
            sample_branch.name,
            "MV0005",  # referrer_code
            72,
            "2025-11-08",
            4,  # INTERVIEW_SCHEDULED_2
            "",  # onboard_date
            "6 năm kinh nghiệm",
        ]

        options = {"headers": template_headers}
        result = import_handler(1, row, "test-job-id", options)

        assert result["ok"] is True
        assert result["action"] == "created"

        candidate = RecruitmentCandidate.objects.get(citizen_id="123456789005")
        assert candidate.referrer == referrer
        assert candidate.status == RecruitmentCandidate.Status.INTERVIEW_SCHEDULED_2

    def test_import_handler_missing_required_field(self, template_headers):
        """Test import with missing required field - should skip row."""
        row = [
            1,  # row_number
            "",  # Missing name
            "123456789001",
            "test@example.com",
            "0912345678",
            "Request",
            "Source",
            "Channel",
            "Department",
            "Block",
            "Branch",
            "",
            12,
            "2025-11-01",
            1,
            "",
            "",
        ]

        options = {"headers": template_headers}
        result = import_handler(1, row, "test-job-id", options)

        assert result["ok"] is True
        assert result["action"] == "skipped"
        assert "Missing required field" in result["warnings"][0]

    def test_import_handler_invalid_citizen_id(self, template_headers):
        """Test import with invalid citizen ID."""
        row = [
            1,
            "Test User",
            "12345",  # Too short
            "test@example.com",
            "0912345678",
            "Request",
            "Source",
            "Channel",
            "Department",
            "Block",
            "Branch",
            "",
            12,
            "2025-11-01",
            1,
            "",
            "",
        ]

        options = {"headers": template_headers}
        result = import_handler(1, row, "test-job-id", options)

        assert result["ok"] is False
        assert "12 digits" in result["error"]

    def test_import_handler_duplicate_citizen_id(
        self, sample_branch, sample_block, sample_department, sample_proposer, template_headers
    ):
        """Test import with duplicate citizen ID."""
        # Create existing candidate
        source = RecruitmentSource.objects.create(name="Test Source")
        channel = RecruitmentChannel.objects.create(name="Test Channel")
        job_desc = JobDescription.objects.create(
            title="Test Job",
            position_title="Test Job",
            responsibility="",
            requirement="",
            benefit="",
            proposed_salary="Negotiable",
        )
        request = RecruitmentRequest.objects.create(
            name="Test Request",
            job_description=job_desc,
            department=sample_department,
            proposer=sample_proposer,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            status=RecruitmentRequest.Status.DRAFT,
            proposed_salary="Negotiable",
        )
        RecruitmentCandidate.objects.create(
            name="Existing Candidate",
            citizen_id="123456789001",
            email="existing@example.com",
            phone="0912345678",
            recruitment_request=request,
            recruitment_source=source,
            recruitment_channel=channel,
            submitted_date=date.today(),
        )

        # Try to import with same citizen ID (should skip with allow_update=False)
        row = [
            1,
            "New Candidate",
            "123456789001",  # Duplicate
            "new@example.com",
            "0923456789",
            "Request",
            "Source",
            "Channel",
            sample_department.name,
            sample_block.name,
            sample_branch.name,
            "",
            12,
            "2025-11-01",
            1,
            "",
            "",
        ]

        options = {"headers": template_headers}
        result = import_handler(1, row, "test-job-id", options)

        # Should skip since allow_update=False
        assert result["ok"] is True
        assert result["action"] == "skipped"
        assert "already exists" in result["warnings"][0]

    def test_import_handler_invalid_status_code(
        self, sample_branch, sample_block, sample_department, template_headers
    ):
        """Test import with invalid status code."""
        row = [
            1,
            "Test User",
            "123456789001",
            "test@example.com",
            "0912345678",
            "Request",
            "Source",
            "Channel",
            sample_department.name,
            sample_block.name,
            sample_branch.name,
            "",
            12,
            "2025-11-01",
            10,  # Invalid status code
            "",
            "",
        ]

        options = {"headers": template_headers}
        result = import_handler(1, row, "test-job-id", options)

        assert result["ok"] is False
        assert "Status code" in result["error"] or "at most 7" in result["error"]

    def test_import_handler_branch_not_found(self, sample_department, template_headers):
        """Test import when branch is not found."""
        row = [
            1,
            "Test User",
            "123456789001",
            "test@example.com",
            "0912345678",
            "Request",
            "Source",
            "Channel",
            sample_department.name,
            sample_department.block.name,
            "Nonexistent Branch",  # Doesn't exist
            "",
            12,
            "2025-11-01",
            1,
            "",
            "",
        ]

        options = {"headers": template_headers}
        result = import_handler(1, row, "test-job-id", options)

        assert result["ok"] is False
        assert "Branch" in result["error"] and "not found" in result["error"]

    def test_import_handler_insufficient_columns(self, template_headers):
        """Test import with missing headers."""
        row = ["Test", "123456789001", "test@example.com"]  # Only 3 columns

        options = {}  # No headers
        result = import_handler(1, row, "test-job-id", options)

        assert result["ok"] is False
        assert "Headers not provided" in result["error"]

    def test_import_handler_caching(
        self, sample_branch, sample_block, sample_department, sample_proposer, template_headers
    ):
        """Test that entities are cached across multiple imports."""
        options = {"headers": template_headers}

        # First import
        row1 = [
            1,
            "Candidate 1",
            "123456789001",
            "candidate1@example.com",
            "0912345678",
            "Tuyển Backend Developer",
            "LinkedIn",
            "Website",
            sample_department.name,
            sample_block.name,
            sample_branch.name,
            "",
            24,
            "2025-11-01",
            1,
            "",
            "",
        ]
        result1 = import_handler(1, row1, "test-job-id", options)
        assert result1["ok"] is True

        # Second import with same source/channel/request
        row2 = [
            2,
            "Candidate 2",
            "123456789002",
            "candidate2@example.com",
            "0923456789",
            "Tuyển Backend Developer",  # Same request
            "LinkedIn",  # Same source
            "Website",  # Same channel
            sample_department.name,
            sample_block.name,
            sample_branch.name,
            "",
            36,
            "2025-11-02",
            2,
            "",
            "",
        ]
        result2 = import_handler(2, row2, "test-job-id", options)
        assert result2["ok"] is True

        # Verify cache is populated
        assert "_cache" in options
        assert "source_linkedin" in options["_cache"]
        assert "channel_website" in options["_cache"]

        # Verify only one source/channel/request was created
        assert RecruitmentSource.objects.filter(name__iexact="LinkedIn").count() == 1
        assert RecruitmentChannel.objects.filter(name__iexact="Website").count() == 1
        assert RecruitmentRequest.objects.filter(name__iexact="Tuyển Backend Developer").count() == 1

    def test_import_handler_hired_without_onboard_date(
        self, sample_branch, sample_block, sample_department, sample_proposer, template_headers
    ):
        """Test import with HIRED status but missing onboard_date."""
        row = [
            1,
            "Test Candidate",
            "123456789001",
            "test@example.com",
            "0912345678",
            "Tuyển Backend Developer",
            "LinkedIn",
            "Website",
            sample_department.name,
            sample_block.name,
            sample_branch.name,
            "",
            24,
            "2025-11-01",
            6,  # HIRED status
            "",  # Missing onboard_date
            "",
        ]

        options = {"headers": template_headers}
        result = import_handler(1, row, "test-job-id", options)

        assert result["ok"] is False
        assert "Onboard date is required when status is HIRED" in result["error"]

    def test_import_handler_hired_with_onboard_date(
        self, sample_branch, sample_block, sample_department, sample_proposer, template_headers
    ):
        """Test import with HIRED status and onboard_date."""
        row = [
            1,
            "Test Candidate",
            "123456789001",
            "test@example.com",
            "0912345678",
            "Tuyển Backend Developer",
            "LinkedIn",
            "Website",
            sample_department.name,
            sample_block.name,
            sample_branch.name,
            "",
            24,
            "2025-11-01",
            6,  # HIRED status
            "2025-11-15",  # onboard_date
            "",
        ]

        options = {"headers": template_headers}
        result = import_handler(1, row, "test-job-id", options)

        assert result["ok"] is True
        candidate = RecruitmentCandidate.objects.get(citizen_id="123456789001")
        assert candidate.status == RecruitmentCandidate.Status.HIRED
        assert candidate.onboard_date == date(2025, 11, 15)

    def test_import_handler_allow_update(
        self, sample_branch, sample_block, sample_department, sample_proposer, template_headers
    ):
        """Test import with allow_update=True updates existing candidate."""
        # Create existing candidate
        source = RecruitmentSource.objects.create(name="Test Source")
        channel = RecruitmentChannel.objects.create(name="Test Channel")
        job_desc = JobDescription.objects.create(
            title="Test Job",
            position_title="Test Job",
            responsibility="",
            requirement="",
            benefit="",
            proposed_salary="Negotiable",
        )
        request = RecruitmentRequest.objects.create(
            name="Test Request",
            job_description=job_desc,
            department=sample_department,
            proposer=sample_proposer,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            status=RecruitmentRequest.Status.DRAFT,
            proposed_salary="Negotiable",
        )
        existing = RecruitmentCandidate.objects.create(
            name="Old Name",
            citizen_id="123456789001",
            email="old@example.com",
            phone="0912345678",
            recruitment_request=request,
            recruitment_source=source,
            recruitment_channel=channel,
            submitted_date=date.today(),
            status=RecruitmentCandidate.Status.CONTACTED,
        )

        # Import with allow_update=True
        row = [
            1,
            "Updated Name",
            "123456789001",  # Same citizen ID
            "updated@example.com",
            "0923456789",
            "Tuyển Backend Developer",
            "LinkedIn",
            "Website",
            sample_department.name,
            sample_block.name,
            sample_branch.name,
            "",
            24,
            "2025-11-01",
            2,  # Updated status
            "",
            "Updated note",
        ]

        options = {"headers": template_headers, "allow_update": True}
        result = import_handler(1, row, "test-job-id", options)

        assert result["ok"] is True
        assert result["action"] == "updated"

        # Verify candidate was updated
        candidate = RecruitmentCandidate.objects.get(citizen_id="123456789001")
        assert candidate.id == existing.id  # Same object
        assert candidate.name == "Updated Name"
        assert candidate.email == "updated@example.com"
        assert candidate.status == RecruitmentCandidate.Status.INTERVIEW_SCHEDULED_1
        assert candidate.note == "Updated note"


# Fixtures


@pytest.fixture
def template_headers():
    """Standard template headers for import tests."""
    return [
        "Số Thứ Tự",
        "Họ và Tên",
        "CMND/CCCD",
        "Email",
        "Số Điện Thoại",
        "Tên Yêu Cầu Tuyển Dụng",
        "Tên Nguồn Tuyển Dụng",
        "Tên Kênh Tuyển Dụng",
        "Tên Phòng Ban",
        "Tên Khối",
        "Tên Chi Nhánh",
        "Mã Nhân Viên Giới Thiệu",
        "Số Tháng Kinh Nghiệm",
        "Ngày Nộp Hồ Sơ",
        "Trạng Thái",
        "Ngày Onboard",
        "Ghi Chú",
    ]


@pytest.fixture
def sample_province():
    """Create a sample province."""
    from apps.core.models import Province

    return Province.objects.create(name="Hà Nội", code="HN")


@pytest.fixture
def sample_administrative_unit(sample_province):
    """Create a sample administrative unit."""
    from apps.core.models import AdministrativeUnit

    return AdministrativeUnit.objects.create(name="Test Administrative Unit", parent_province=sample_province)


@pytest.fixture
def sample_branch(sample_province, sample_administrative_unit):
    """Create a sample branch."""
    return Branch.objects.create(
        name="Chi Nhánh Hà Nội",
        province=sample_province,
        administrative_unit=sample_administrative_unit,
    )


@pytest.fixture
def sample_block(sample_branch):
    """Create a sample block."""
    return Block.objects.create(name="Khối Kinh Doanh", branch=sample_branch, block_type=Block.BlockType.BUSINESS)


@pytest.fixture
def sample_department(sample_block, sample_branch):
    """Create a sample department."""
    return Department.objects.create(name="Phòng IT", block=sample_block, branch=sample_branch)


@pytest.fixture
def sample_proposer(sample_branch, sample_block, sample_department):
    """Create a sample employee to act as proposer."""
    return Employee.objects.create(
        code="MV0001",
        fullname="Test Proposer",
        username="proposer",
        email="proposer@test.com",
        phone="0988888888",
        citizen_id="888888888888",  # Unique citizen ID for proposer
        start_date=date.today(),
        status=Employee.Status.ACTIVE,
        branch=sample_branch,
        block=sample_block,
        department=sample_department,
    )
