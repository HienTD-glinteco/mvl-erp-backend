from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import Block, Branch, Department, Position

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