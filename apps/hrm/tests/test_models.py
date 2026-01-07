from datetime import date
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from apps.hrm.models import Block, Branch, BranchContactInfo, Department, Employee, Position

User = get_user_model()


@pytest.mark.django_db
class TestBranchModel:
    """Test cases for Branch model"""

    @pytest.fixture
    def branch_data(self, province, admin_unit):
        return {
            "name": "Chi nhánh Hà Nội",
            "code": "HN",
            "address": "123 Lê Duẩn, Hà Nội",
            "phone": "0243456789",
            "email": "hanoi@maivietland.com",
            "province": province,
            "administrative_unit": admin_unit,
        }

    def test_create_branch(self, branch_data):
        """Test creating a branch"""
        branch = Branch.objects.create(**branch_data)
        assert branch.name == branch_data["name"]
        assert branch.code == branch_data["code"]
        assert branch.is_active is True
        assert str(branch) == f"{branch.code} - {branch.name}"

    def test_branch_code_unique(self, branch_data):
        """Test branch code uniqueness"""
        Branch.objects.create(**branch_data)

        # Try to create another branch with same code
        with pytest.raises(Exception):  # IntegrityError
            Branch.objects.create(**branch_data)

    def test_branch_phone_field_max_length(self, branch_data):
        """Test phone field accepts up to 1000 characters"""
        # Test with exactly 1000 characters
        long_phone = "0" * 1000
        data = branch_data.copy()
        data["phone"] = long_phone
        data["code"] = "TEST1000"

        branch = Branch.objects.create(**data)
        assert len(branch.phone) == 1000
        assert branch.phone == long_phone

    def test_branch_phone_field_accepts_empty_string(self, branch_data):
        """Test phone field accepts empty string (blank=True)"""
        data = branch_data.copy()
        data["phone"] = ""
        data["code"] = "TESTEMPTY"

        branch = Branch.objects.create(**data)
        assert branch.phone == ""

    def test_branch_phone_field_accepts_multiple_numbers(self, branch_data):
        """Test phone field can store multiple phone numbers separated by commas"""
        multiple_phones = "024-12345678, 091-234-5678, +84-28-7654321"
        data = branch_data.copy()
        data["phone"] = multiple_phones
        data["code"] = "TESTMULTI"

        branch = Branch.objects.create(**data)
        assert branch.phone == multiple_phones

    def test_branch_phone_field_accepts_various_formats(self, branch_data):
        """Test phone field accepts various phone number formats"""
        test_cases = [
            ("0243456789", "Simple 10-digit format"),
            ("024-345-6789", "Format with dashes"),
            ("+84-24-345-6789", "International format with country code"),
            ("(024) 345 6789", "Format with parentheses and spaces"),
            ("024.345.6789", "Format with dots"),
            ("Hotline: 1900-1234, Office: 024-567-8901", "Mixed text and numbers"),
        ]

        for i, (phone_format, description) in enumerate(test_cases):
            data = branch_data.copy()
            data["phone"] = phone_format
            data["code"] = f"TESTFMT{i}"

            branch = Branch.objects.create(**data)
            assert branch.phone == phone_format, f"Failed for: {description}"


@pytest.mark.django_db
class TestBranchContactInfoModel:
    """Test cases for BranchContactInfo model"""

    def test_create_branch_contact_info(self, branch):
        """Ensure a BranchContactInfo can be created"""

        contact = BranchContactInfo.objects.create(
            branch=branch,
            business_line="Mortgage",
            name="Alice Nguyen",
            phone_number="0912345678",
            email="alice.nguyen@example.com",
        )

        assert contact.branch == branch
        assert contact.business_line == "Mortgage"
        assert contact.phone_number == "0912345678"

    def test_str_representation(self, branch):
        """__str__ should include branch code, name, and business line"""

        contact = BranchContactInfo.objects.create(
            branch=branch,
            business_line="Corporate",
            name="Bob Tran",
            phone_number="0987654321",
            email="bob.tran@example.com",
        )

        str_value = str(contact)
        assert branch.code in str_value
        assert "Bob Tran" in str_value
        assert "Corporate" in str_value


@pytest.mark.django_db
class TestBlockModel:
    """Test cases for Block model"""

    def test_create_support_block(self, branch):
        """Test creating a support block"""
        block = Block.objects.create(
            name="Khối Hỗ trợ",
            code="HT",
            block_type=Block.BlockType.SUPPORT,
            branch=branch,
        )
        assert block.block_type == Block.BlockType.SUPPORT
        assert block.get_block_type_display() == "Support Block"
        assert block.is_active is True

    def test_create_business_block(self, branch):
        """Test creating a business block"""
        block = Block.objects.create(
            name="Khối Kinh doanh",
            code="KD",
            block_type=Block.BlockType.BUSINESS,
            branch=branch,
        )
        assert block.block_type == Block.BlockType.BUSINESS
        assert block.get_block_type_display() == "Business Block"

    def test_block_unique_together(self, branch):
        """Test block code uniqueness within branch"""
        Block.objects.create(
            name="Khối Hỗ trợ",
            code="HT",
            block_type=Block.BlockType.SUPPORT,
            branch=branch,
        )

        # Should fail - same code in same branch
        with pytest.raises(Exception):  # IntegrityError
            Block.objects.create(
                name="Khối khác",
                code="HT",
                block_type=Block.BlockType.BUSINESS,
                branch=branch,
            )


@pytest.mark.django_db
class TestDepartmentModel:
    """Test cases for Department model"""

    def test_create_department(self, block, branch):
        """Test creating a department"""
        department = Department.objects.create(name="Phòng Nhân sự", code="NS", block=block, branch=branch)
        assert department.name == "Phòng Nhân sự"
        assert department.code == "NS"
        assert department.block == block
        assert department.parent_department is None
        assert department.is_active is True

    def test_department_hierarchy(self, block, branch):
        """Test department hierarchical structure"""
        parent_dept = Department.objects.create(name="Phòng Nhân sự", code="NS", block=block, branch=branch)

        child_dept = Department.objects.create(
            name="Ban Tuyển dụng",
            code="TD",
            branch=branch,
            block=block,
            parent_department=parent_dept,
        )

        assert child_dept.parent_department == parent_dept
        assert child_dept.full_hierarchy == "Phòng Nhân sự > Ban Tuyển dụng"
        assert parent_dept.full_hierarchy == "Phòng Nhân sự"

    def test_department_unique_together(self, block, branch):
        """Test department code uniqueness within block"""
        Department.objects.create(name="Phòng Nhân sự", code="NS", block=block, branch=branch)

        # Should fail - same code in same block
        with pytest.raises(Exception):  # IntegrityError
            Department.objects.create(name="Phòng khác", code="NS", block=block, branch=branch)


@pytest.mark.django_db
class TestPositionModel:
    """Test cases for Position model"""

    def test_create_position(self):
        """Test creating a position"""
        position = Position.objects.create(name="Tổng Giám đốc", code="TGD")
        assert position.name == "Tổng Giám đốc"
        assert position.code == "TGD"
        assert position.is_active is True
        assert position.include_in_employee_report is True

    def test_position_code_unique(self):
        """Test position code uniqueness"""
        Position.objects.create(name="Tổng Giám đốc", code="TGD")

        # Should fail - same code
        with pytest.raises(Exception):  # IntegrityError
            Position.objects.create(name="Tổng Giám đốc khác", code="TGD")

    def test_position_ordering(self):
        """Test position ordering by name"""
        director = Position.objects.create(name="Giám đốc", code="GD")
        staff = Position.objects.create(name="Nhân viên", code="NV")
        ceo = Position.objects.create(name="Tổng Giám đốc", code="TGD")

        positions = list(Position.objects.all())
        assert positions[0] == director  # "Giám đốc" alphabetically first
        assert positions[1] == staff  # "Nhân viên" second
        assert positions[2] == ceo  # "Tổng Giám đốc" last

    def test_position_include_in_employee_report_default(self):
        """Test that include_in_employee_report defaults to True"""
        position = Position.objects.create(name="Manager", code="MGR")
        assert position.include_in_employee_report is True

    def test_position_include_in_employee_report_false(self):
        """Test creating a position with include_in_employee_report=False"""
        position = Position.objects.create(name="Contractor", code="CTR", include_in_employee_report=False)
        assert position.include_in_employee_report is False


@pytest.mark.django_db
class TestOrganizationLeadershipFields:
    """Ensure newly added director/leader relationships behave correctly."""

    @pytest.fixture(autouse=True)
    def setup_patches(self):
        # Patch Celery tasks invoked by employee signals to keep tests isolated
        self.hr_report_patcher = patch("apps.hrm.signals.hr_reports.aggregate_hr_reports_for_work_history.delay")
        self.recruitment_report_patcher = patch(
            "apps.hrm.signals.recruitment_reports.aggregate_recruitment_reports_for_candidate.delay"
        )
        self.timesheet_patcher = patch("apps.hrm.signals.employee.prepare_monthly_timesheets.delay")
        self.hr_report_patcher.start()
        self.recruitment_report_patcher.start()
        self.timesheet_patcher.start()
        self.employee_counter = 0

        yield

        self.hr_report_patcher.stop()
        self.recruitment_report_patcher.stop()
        self.timesheet_patcher.stop()

    def _create_employee(self, department, branch, block, **overrides):
        self.employee_counter += 1
        suffix = f"{self.employee_counter:03d}"
        defaults = {
            "fullname": f"Leader {suffix}",
            "username": f"leader{suffix}",
            "email": f"leader{suffix}@example.com",
            "personal_email": f"leader{suffix}.personal@example.com",
            "phone": f"09{self.employee_counter:08d}",
            "attendance_code": f"{self.employee_counter:05d}",
            "start_date": date(2024, 1, 1),
            "department": department,
            "branch": branch,
            "block": block,
            "citizen_id": f"123456{self.employee_counter:04d}",
        }
        defaults.update(overrides)
        return Employee.objects.create(**defaults)

    def test_branch_director_relationship_is_set_and_cleared(self, branch, block, department):
        director = self._create_employee(department, branch, block, fullname="Branch Director")
        branch.director = director
        branch.save(update_fields=["director"])

        branch.refresh_from_db()
        assert branch.director == director
        assert branch in director.directed_branches.all()

        director.delete()
        branch.refresh_from_db()
        assert branch.director is None

    def test_block_director_relationship_is_set_and_cleared(self, branch, block, department):
        director = self._create_employee(department, branch, block, fullname="Block Director")
        block.director = director
        block.save(update_fields=["director"])

        block.refresh_from_db()
        assert block.director == director
        assert block in director.directed_blocks.all()

        director.delete()
        block.refresh_from_db()
        assert block.director is None

    def test_department_leader_relationship_is_set_and_cleared(self, branch, block, department):
        leader = self._create_employee(department, branch, block, fullname="Department Leader")
        department.leader = leader
        department.save(update_fields=["leader"])

        department.refresh_from_db()
        assert department.leader == leader
        assert department in leader.led_departments.all()

        leader.delete()
        department.refresh_from_db()
        assert department.leader is None


@pytest.mark.django_db
class TestProposalShortDescription:
    """Test cases for Proposal short_description property."""

    @pytest.fixture
    def test_employee(self, branch, block, department, position):
        return Employee.objects.create(
            code_type="MV",
            fullname="Test Employee",
            username="testemployee",
            email="test@example.com",
            personal_email="test.personal@example.com",
            phone="0900789001",
            citizen_id="123456789001",
            start_date="2023-01-01",
            branch=branch,
            block=block,
            department=department,
            position=position,
        )

    def test_short_description_returns_none_for_no_type(self, test_employee):
        """Test that short_description returns None when proposal_type is not set."""
        from apps.hrm.models import Proposal

        proposal = Proposal(created_by=test_employee)
        assert proposal.short_description is None

    def test_short_description_post_maternity_benefits(self, test_employee):
        """Test short_description for post_maternity_benefits proposal."""
        from apps.hrm.constants import ProposalType
        from apps.hrm.models import Proposal

        proposal = Proposal.objects.create(
            proposal_type=ProposalType.POST_MATERNITY_BENEFITS,
            created_by=test_employee,
            post_maternity_benefits_start_date=date(2024, 1, 1),
            post_maternity_benefits_end_date=date(2024, 3, 31),
        )
        assert proposal.short_description == "2024-01-01 - 2024-03-31"

    def test_short_description_late_exemption(self, test_employee):
        """Test short_description for late_exemption proposal."""
        from apps.hrm.constants import ProposalType
        from apps.hrm.models import Proposal

        proposal = Proposal.objects.create(
            proposal_type=ProposalType.LATE_EXEMPTION,
            created_by=test_employee,
            late_exemption_start_date=date(2024, 1, 1),
            late_exemption_end_date=date(2024, 1, 31),
            late_exemption_minutes=30,
        )
        # Format: "{minutes} day - {start_date} - {end_date} "
        assert "30" in proposal.short_description
        assert "2024-01-01" in proposal.short_description
        assert "2024-01-31" in proposal.short_description

    def test_short_description_paid_leave(self, test_employee):
        """Test short_description for paid_leave proposal."""
        from apps.hrm.constants import ProposalType, ProposalWorkShift
        from apps.hrm.models import Proposal

        proposal = Proposal.objects.create(
            proposal_type=ProposalType.PAID_LEAVE,
            created_by=test_employee,
            paid_leave_start_date=date(2024, 1, 15),
            paid_leave_end_date=date(2024, 1, 15),
            paid_leave_shift=ProposalWorkShift.MORNING,
            paid_leave_reason="Doctor appointment",
        )
        # Format: "{shift} - {start_date} - {end_date}"
        assert proposal.short_description == "morning - 2024-01-15 - 2024-01-15"

    def test_short_description_unpaid_leave(self, test_employee):
        """Test short_description for unpaid_leave proposal."""
        from apps.hrm.constants import ProposalType
        from apps.hrm.models import Proposal

        proposal = Proposal.objects.create(
            proposal_type=ProposalType.UNPAID_LEAVE,
            created_by=test_employee,
            unpaid_leave_start_date=date(2024, 2, 1),
            unpaid_leave_end_date=date(2024, 2, 5),
            unpaid_leave_reason="Personal matters",
        )
        assert proposal.short_description == "2024-02-01 - 2024-02-05"

    def test_short_description_maternity_leave(self, test_employee):
        """Test short_description for maternity_leave proposal."""
        from apps.hrm.constants import ProposalType
        from apps.hrm.models import Proposal

        proposal = Proposal.objects.create(
            proposal_type=ProposalType.MATERNITY_LEAVE,
            created_by=test_employee,
            maternity_leave_start_date=date(2024, 6, 1),
            maternity_leave_end_date=date(2024, 12, 1),
        )
        assert proposal.short_description == "2024-06-01 - 2024-12-01"

    def test_short_description_timesheet_entry_complaint(self, test_employee):
        """Test short_description for timesheet_entry_complaint proposal returns None."""
        from apps.hrm.constants import ProposalType
        from apps.hrm.models import Proposal

        proposal = Proposal.objects.create(
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            created_by=test_employee,
            timesheet_entry_complaint_complaint_reason="Incorrect check-in time recorded",
        )
        # Timesheet entry complaint returns None as per implementation
        assert proposal.short_description is None

    def test_short_description_timesheet_entry_complaint_returns_none(self, test_employee):
        """Test short_description for timesheet_entry_complaint proposal returns None even with long reason."""
        from apps.hrm.constants import ProposalType
        from apps.hrm.models import Proposal

        long_reason = "A" * 100
        proposal = Proposal.objects.create(
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            created_by=test_employee,
            timesheet_entry_complaint_complaint_reason=long_reason,
        )
        # Timesheet entry complaint returns None as per implementation
        assert proposal.short_description is None

    def test_short_description_job_transfer(self, test_employee, position, branch, block):
        """Test short_description for job_transfer proposal."""
        from apps.hrm.constants import ProposalType
        from apps.hrm.models import Proposal

        new_department = Department.objects.create(
            name="New Department",
            code="ND001",
            branch=branch,
            block=block,
        )
        proposal = Proposal.objects.create(
            proposal_type=ProposalType.JOB_TRANSFER,
            created_by=test_employee,
            job_transfer_new_department=new_department,
            job_transfer_new_position=position,
            job_transfer_effective_date=date(2024, 3, 1),
        )
        # Format: "{branch_name}, {block_name}, {department_name}, {position_name}"
        assert proposal.short_description == "Test Branch, Test Block, New Department, Test Position"

    def test_short_description_returns_none_for_missing_data(self, test_employee):
        """Test that short_description returns None when required data is missing."""
        from apps.hrm.constants import ProposalType
        from apps.hrm.models import Proposal

        # Post maternity benefits without dates
        proposal = Proposal(
            proposal_type=ProposalType.POST_MATERNITY_BENEFITS,
            created_by=test_employee,
        )
        assert proposal.short_description is None
