from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import Block, Branch, BranchContactInfo, Department, Employee, Position

User = get_user_model()


class BranchModelTest(TestCase):
    """Test cases for Branch model"""

    def setUp(self):
        # Create Province and AdministrativeUnit for Branch
        self.province = Province.objects.create(
            code="01",
            name="Thành phố Hà Nội",
            english_name="Hanoi",
            level=Province.ProvinceLevel.CENTRAL_CITY,
            enabled=True,
        )
        self.administrative_unit = AdministrativeUnit.objects.create(
            code="001",
            name="Quận Ba Đình",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
            enabled=True,
        )

        self.branch_data = {
            "name": "Chi nhánh Hà Nội",
            "code": "HN",
            "address": "123 Lê Duẩn, Hà Nội",
            "phone": "0243456789",
            "email": "hanoi@maivietland.com",
            "province": self.province,
            "administrative_unit": self.administrative_unit,
        }

    def test_create_branch(self):
        """Test creating a branch"""
        branch = Branch.objects.create(**self.branch_data)
        self.assertEqual(branch.name, self.branch_data["name"])
        self.assertEqual(branch.code, self.branch_data["code"])
        self.assertTrue(branch.is_active)
        self.assertEqual(str(branch), f"{branch.code} - {branch.name}")

    def test_branch_code_unique(self):
        """Test branch code uniqueness"""
        Branch.objects.create(**self.branch_data)

        # Try to create another branch with same code
        with self.assertRaises(Exception):  # IntegrityError
            Branch.objects.create(**self.branch_data)

    def test_branch_phone_field_max_length(self):
        """Test phone field accepts up to 1000 characters"""
        # Test with exactly 1000 characters
        long_phone = "0" * 1000
        branch_data = self.branch_data.copy()
        branch_data["phone"] = long_phone
        branch_data["code"] = "TEST1000"

        branch = Branch.objects.create(**branch_data)
        self.assertEqual(len(branch.phone), 1000)
        self.assertEqual(branch.phone, long_phone)

    def test_branch_phone_field_accepts_empty_string(self):
        """Test phone field accepts empty string (blank=True)"""
        branch_data = self.branch_data.copy()
        branch_data["phone"] = ""
        branch_data["code"] = "TESTEMPTY"

        branch = Branch.objects.create(**branch_data)
        self.assertEqual(branch.phone, "")

    def test_branch_phone_field_accepts_multiple_numbers(self):
        """Test phone field can store multiple phone numbers separated by commas"""
        multiple_phones = "024-12345678, 091-234-5678, +84-28-7654321"
        branch_data = self.branch_data.copy()
        branch_data["phone"] = multiple_phones
        branch_data["code"] = "TESTMULTI"

        branch = Branch.objects.create(**branch_data)
        self.assertEqual(branch.phone, multiple_phones)

    def test_branch_phone_field_accepts_various_formats(self):
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
            branch_data = self.branch_data.copy()
            branch_data["phone"] = phone_format
            branch_data["code"] = f"TESTFMT{i}"

            branch = Branch.objects.create(**branch_data)
            self.assertEqual(branch.phone, phone_format, f"Failed for: {description}")


class BranchContactInfoModelTest(TestCase):
    """Test cases for BranchContactInfo model"""

    def setUp(self):
        self.province = Province.objects.create(
            code="01",
            name="Ha Noi",
            english_name="Hanoi",
            level=Province.ProvinceLevel.CENTRAL_CITY,
            enabled=True,
        )
        self.administrative_unit = AdministrativeUnit.objects.create(
            code="001",
            name="Ba Dinh",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
            enabled=True,
        )
        self.branch = Branch.objects.create(
            name="Hanoi Branch",
            code="HN",
            province=self.province,
            administrative_unit=self.administrative_unit,
        )

    def test_create_branch_contact_info(self):
        """Ensure a BranchContactInfo can be created"""

        contact = BranchContactInfo.objects.create(
            branch=self.branch,
            business_line="Mortgage",
            name="Alice Nguyen",
            phone_number="0912345678",
            email="alice.nguyen@example.com",
        )

        self.assertEqual(contact.branch, self.branch)
        self.assertEqual(contact.business_line, "Mortgage")
        self.assertEqual(contact.phone_number, "0912345678")

    def test_str_representation(self):
        """__str__ should include branch code, name, and business line"""

        contact = BranchContactInfo.objects.create(
            branch=self.branch,
            business_line="Corporate",
            name="Bob Tran",
            phone_number="0987654321",
            email="bob.tran@example.com",
        )

        str_value = str(contact)
        self.assertIn(self.branch.code, str_value)
        self.assertIn("Bob Tran", str_value)
        self.assertIn("Corporate", str_value)


class BlockModelTest(TestCase):
    """Test cases for Block model"""

    def setUp(self):
        # Create Province and AdministrativeUnit for Branch
        self.province = Province.objects.create(
            code="01",
            name="Thành phố Hà Nội",
            english_name="Hanoi",
            level=Province.ProvinceLevel.CENTRAL_CITY,
            enabled=True,
        )
        self.administrative_unit = AdministrativeUnit.objects.create(
            code="001",
            name="Quận Ba Đình",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
            enabled=True,
        )

        self.branch = Branch.objects.create(
            name="Chi nhánh Hà Nội",
            code="HN",
            province=self.province,
            administrative_unit=self.administrative_unit,
        )

    def test_create_support_block(self):
        """Test creating a support block"""
        block = Block.objects.create(
            name="Khối Hỗ trợ",
            code="HT",
            block_type=Block.BlockType.SUPPORT,
            branch=self.branch,
        )
        self.assertEqual(block.block_type, Block.BlockType.SUPPORT)
        self.assertEqual(block.get_block_type_display(), "Support Block")
        self.assertTrue(block.is_active)

    def test_create_business_block(self):
        """Test creating a business block"""
        block = Block.objects.create(
            name="Khối Kinh doanh",
            code="KD",
            block_type=Block.BlockType.BUSINESS,
            branch=self.branch,
        )
        self.assertEqual(block.block_type, Block.BlockType.BUSINESS)
        self.assertEqual(block.get_block_type_display(), "Business Block")

    def test_block_unique_together(self):
        """Test block code uniqueness within branch"""
        Block.objects.create(
            name="Khối Hỗ trợ",
            code="HT",
            block_type=Block.BlockType.SUPPORT,
            branch=self.branch,
        )

        # Should fail - same code in same branch
        with self.assertRaises(Exception):  # IntegrityError
            Block.objects.create(
                name="Khối khác",
                code="HT",
                block_type=Block.BlockType.BUSINESS,
                branch=self.branch,
            )


class DepartmentModelTest(TestCase):
    """Test cases for Department model"""

    def setUp(self):
        # Create Province and AdministrativeUnit for Branch
        self.province = Province.objects.create(
            code="01",
            name="Thành phố Hà Nội",
            english_name="Hanoi",
            level=Province.ProvinceLevel.CENTRAL_CITY,
            enabled=True,
        )
        self.administrative_unit = AdministrativeUnit.objects.create(
            code="001",
            name="Quận Ba Đình",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
            enabled=True,
        )

        self.branch = Branch.objects.create(
            name="Chi nhánh Hà Nội",
            code="HN",
            province=self.province,
            administrative_unit=self.administrative_unit,
        )
        self.block = Block.objects.create(
            name="Khối Hỗ trợ",
            code="HT",
            block_type=Block.BlockType.SUPPORT,
            branch=self.branch,
        )

    def test_create_department(self):
        """Test creating a department"""
        department = Department.objects.create(name="Phòng Nhân sự", code="NS", block=self.block, branch=self.branch)
        self.assertEqual(department.name, "Phòng Nhân sự")
        self.assertEqual(department.code, "NS")
        self.assertEqual(department.block, self.block)
        self.assertIsNone(department.parent_department)
        self.assertTrue(department.is_active)

    def test_department_hierarchy(self):
        """Test department hierarchical structure"""
        parent_dept = Department.objects.create(name="Phòng Nhân sự", code="NS", block=self.block, branch=self.branch)

        child_dept = Department.objects.create(
            name="Ban Tuyển dụng",
            code="TD",
            branch=self.branch,
            block=self.block,
            parent_department=parent_dept,
        )

        self.assertEqual(child_dept.parent_department, parent_dept)
        self.assertEqual(child_dept.full_hierarchy, "Phòng Nhân sự > Ban Tuyển dụng")
        self.assertEqual(parent_dept.full_hierarchy, "Phòng Nhân sự")

    def test_department_unique_together(self):
        """Test department code uniqueness within block"""
        Department.objects.create(name="Phòng Nhân sự", code="NS", block=self.block, branch=self.branch)

        # Should fail - same code in same block
        with self.assertRaises(Exception):  # IntegrityError
            Department.objects.create(name="Phòng khác", code="NS", block=self.block, branch=self.branch)


class PositionModelTest(TestCase):
    """Test cases for Position model"""

    def test_create_position(self):
        """Test creating a position"""
        position = Position.objects.create(name="Tổng Giám đốc", code="TGD")
        self.assertEqual(position.name, "Tổng Giám đốc")
        self.assertEqual(position.code, "TGD")
        self.assertTrue(position.is_active)

    def test_position_code_unique(self):
        """Test position code uniqueness"""
        Position.objects.create(name="Tổng Giám đốc", code="TGD")

        # Should fail - same code
        with self.assertRaises(Exception):  # IntegrityError
            Position.objects.create(name="Tổng Giám đốc khác", code="TGD")

    def test_position_ordering(self):
        """Test position ordering by name"""
        director = Position.objects.create(name="Giám đốc", code="GD")
        staff = Position.objects.create(name="Nhân viên", code="NV")
        ceo = Position.objects.create(name="Tổng Giám đốc", code="TGD")

        positions = list(Position.objects.all())
        self.assertEqual(positions[0], director)  # "Giám đốc" alphabetically first
        self.assertEqual(positions[1], staff)  # "Nhân viên" second
        self.assertEqual(positions[2], ceo)  # "Tổng Giám đốc" last


# OrganizationChartModelTest class removed as OrganizationChart model no longer exists
# Employee model now directly stores position, department, block, and branch


class OrganizationLeadershipFieldsTest(TestCase):
    """Ensure newly added director/leader relationships behave correctly."""

    def setUp(self):
        self.province = Province.objects.create(
            code="01",
            name="Thành phố Hà Nội",
            english_name="Hanoi",
            level=Province.ProvinceLevel.CENTRAL_CITY,
            enabled=True,
        )
        self.administrative_unit = AdministrativeUnit.objects.create(
            code="001",
            name="Quận Ba Đình",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
            enabled=True,
        )
        self.branch = Branch.objects.create(
            name="Chi nhánh Hà Nội",
            code="HN",
            province=self.province,
            administrative_unit=self.administrative_unit,
        )
        self.support_block = Block.objects.create(
            name="Khối Hỗ trợ",
            code="HT",
            block_type=Block.BlockType.SUPPORT,
            branch=self.branch,
        )
        self.department = Department.objects.create(
            name="Phòng Nhân sự",
            code="NS",
            branch=self.branch,
            block=self.support_block,
        )
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

    def tearDown(self):
        self.hr_report_patcher.stop()
        self.recruitment_report_patcher.stop()
        self.timesheet_patcher.stop()
        super().tearDown()

    def _create_employee(self, **overrides):
        self.employee_counter += 1
        suffix = f"{self.employee_counter:03d}"
        defaults = {
            "fullname": f"Leader {suffix}",
            "username": f"leader{suffix}",
            "email": f"leader{suffix}@example.com",
            "phone": f"09{self.employee_counter:08d}",
            "attendance_code": f"{self.employee_counter:05d}",
            "start_date": date(2024, 1, 1),
            "department": self.department,
            "branch": self.branch,
            "block": self.support_block,
            "citizen_id": f"123456{self.employee_counter:04d}",
        }
        defaults.update(overrides)
        return Employee.objects.create(**defaults)

    def test_branch_director_relationship_is_set_and_cleared(self):
        director = self._create_employee(fullname="Branch Director")
        self.branch.director = director
        self.branch.save(update_fields=["director"])

        self.branch.refresh_from_db()
        self.assertEqual(self.branch.director, director)
        self.assertIn(self.branch, director.directed_branches.all())

        director.delete()
        self.branch.refresh_from_db()
        self.assertIsNone(self.branch.director)

    def test_block_director_relationship_is_set_and_cleared(self):
        director = self._create_employee(fullname="Block Director")
        self.support_block.director = director
        self.support_block.save(update_fields=["director"])

        self.support_block.refresh_from_db()
        self.assertEqual(self.support_block.director, director)
        self.assertIn(self.support_block, director.directed_blocks.all())

        director.delete()
        self.support_block.refresh_from_db()
        self.assertIsNone(self.support_block.director)

    def test_department_leader_relationship_is_set_and_cleared(self):
        leader = self._create_employee(fullname="Department Leader")
        self.department.leader = leader
        self.department.save(update_fields=["leader"])

        self.department.refresh_from_db()
        self.assertEqual(self.department.leader, leader)
        self.assertIn(self.department, leader.led_departments.all())

        leader.delete()
        self.department.refresh_from_db()
        self.assertIsNone(self.department.leader)


class ProposalShortDescriptionTest(TestCase):
    """Test cases for Proposal short_description property."""

    def setUp(self):
        # Create required dependencies
        self.province = Province.objects.create(
            code="10",
            name="Test Province",
            english_name="Test Province",
            level=Province.ProvinceLevel.CENTRAL_CITY,
            enabled=True,
        )
        self.administrative_unit = AdministrativeUnit.objects.create(
            code="100",
            name="Test Unit",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
            enabled=True,
        )
        self.branch = Branch.objects.create(
            name="Test Branch",
            code="TB001",
            province=self.province,
            administrative_unit=self.administrative_unit,
        )
        self.block = Block.objects.create(
            name="Test Block",
            code="TBL001",
            branch=self.branch,
            block_type=Block.BlockType.BUSINESS,
        )
        self.department = Department.objects.create(
            name="Test Department",
            code="TD001",
            branch=self.branch,
            block=self.block,
        )
        self.position = Position.objects.create(
            name="Test Position",
            code="TP001",
        )
        self.employee = Employee.objects.create(
            code_type="MV",
            fullname="Test Employee",
            username="testemployee",
            email="test@example.com",
            citizen_id="123456789001",
            start_date="2023-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

    def test_short_description_returns_none_for_no_type(self):
        """Test that short_description returns None when proposal_type is not set."""
        from apps.hrm.models import Proposal

        proposal = Proposal(created_by=self.employee)
        self.assertIsNone(proposal.short_description)

    def test_short_description_post_maternity_benefits(self):
        """Test short_description for post_maternity_benefits proposal."""
        from apps.hrm.constants import ProposalType
        from apps.hrm.models import Proposal

        proposal = Proposal.objects.create(
            proposal_type=ProposalType.POST_MATERNITY_BENEFITS,
            created_by=self.employee,
            post_maternity_benefits_start_date=date(2024, 1, 1),
            post_maternity_benefits_end_date=date(2024, 3, 31),
        )
        self.assertEqual(proposal.short_description, "2024-01-01 - 2024-03-31")

    def test_short_description_late_exemption(self):
        """Test short_description for late_exemption proposal."""
        from apps.hrm.constants import ProposalType
        from apps.hrm.models import Proposal

        proposal = Proposal.objects.create(
            proposal_type=ProposalType.LATE_EXEMPTION,
            created_by=self.employee,
            late_exemption_start_date=date(2024, 1, 1),
            late_exemption_end_date=date(2024, 1, 31),
            late_exemption_minutes=30,
        )
        # Format: "{minutes} day - {start_date} - {end_date} "
        self.assertIn("30", proposal.short_description)
        self.assertIn("2024-01-01", proposal.short_description)
        self.assertIn("2024-01-31", proposal.short_description)

    def test_short_description_paid_leave(self):
        """Test short_description for paid_leave proposal."""
        from apps.hrm.constants import ProposalType, ProposalWorkShift
        from apps.hrm.models import Proposal

        proposal = Proposal.objects.create(
            proposal_type=ProposalType.PAID_LEAVE,
            created_by=self.employee,
            paid_leave_start_date=date(2024, 1, 15),
            paid_leave_end_date=date(2024, 1, 15),
            paid_leave_shift=ProposalWorkShift.MORNING,
            paid_leave_reason="Doctor appointment",
        )
        # Format: "{shift} - {start_date} - {end_date}"
        self.assertEqual(proposal.short_description, "morning - 2024-01-15 - 2024-01-15")

    def test_short_description_unpaid_leave(self):
        """Test short_description for unpaid_leave proposal."""
        from apps.hrm.constants import ProposalType
        from apps.hrm.models import Proposal

        proposal = Proposal.objects.create(
            proposal_type=ProposalType.UNPAID_LEAVE,
            created_by=self.employee,
            unpaid_leave_start_date=date(2024, 2, 1),
            unpaid_leave_end_date=date(2024, 2, 5),
            unpaid_leave_reason="Personal matters",
        )
        self.assertEqual(proposal.short_description, "2024-02-01 - 2024-02-05")

    def test_short_description_maternity_leave(self):
        """Test short_description for maternity_leave proposal."""
        from apps.hrm.constants import ProposalType
        from apps.hrm.models import Proposal

        proposal = Proposal.objects.create(
            proposal_type=ProposalType.MATERNITY_LEAVE,
            created_by=self.employee,
            maternity_leave_start_date=date(2024, 6, 1),
            maternity_leave_end_date=date(2024, 12, 1),
        )
        self.assertEqual(proposal.short_description, "2024-06-01 - 2024-12-01")

    def test_short_description_timesheet_entry_complaint(self):
        """Test short_description for timesheet_entry_complaint proposal returns None."""
        from apps.hrm.constants import ProposalType
        from apps.hrm.models import Proposal

        proposal = Proposal.objects.create(
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            created_by=self.employee,
            timesheet_entry_complaint_complaint_reason="Incorrect check-in time recorded",
        )
        # Timesheet entry complaint returns None as per implementation
        self.assertIsNone(proposal.short_description)

    def test_short_description_timesheet_entry_complaint_returns_none(self):
        """Test short_description for timesheet_entry_complaint proposal returns None even with long reason."""
        from apps.hrm.constants import ProposalType
        from apps.hrm.models import Proposal

        long_reason = "A" * 100
        proposal = Proposal.objects.create(
            proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT,
            created_by=self.employee,
            timesheet_entry_complaint_complaint_reason=long_reason,
        )
        # Timesheet entry complaint returns None as per implementation
        self.assertIsNone(proposal.short_description)

    def test_short_description_job_transfer(self):
        """Test short_description for job_transfer proposal."""
        from apps.hrm.constants import ProposalType
        from apps.hrm.models import Proposal

        new_department = Department.objects.create(
            name="New Department",
            code="ND001",
            branch=self.branch,
            block=self.block,
        )
        proposal = Proposal.objects.create(
            proposal_type=ProposalType.JOB_TRANSFER,
            created_by=self.employee,
            job_transfer_new_department=new_department,
            job_transfer_new_position=self.position,
            job_transfer_effective_date=date(2024, 3, 1),
        )
        # Format: "{branch_name}, {block_name}, {department_name}, {position_name}"
        self.assertEqual(proposal.short_description, "Test Branch, Test Block, New Department, Test Position")

    def test_short_description_returns_none_for_missing_data(self):
        """Test that short_description returns None when required data is missing."""
        from apps.hrm.constants import ProposalType
        from apps.hrm.models import Proposal

        # Post maternity benefits without dates
        proposal = Proposal(
            proposal_type=ProposalType.POST_MATERNITY_BENEFITS,
            created_by=self.employee,
        )
        self.assertIsNone(proposal.short_description)
