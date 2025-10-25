from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import Block, Branch, Department, OrganizationChart, Position

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
        self.assertEqual(positions[0], director)  # "Giám đốc" (Director) alphabetically first
        self.assertEqual(positions[1], staff)  # "Nhân viên" (Employee) second
        self.assertEqual(positions[2], ceo)  # "Tổng Giám đốc" (General Director) last


class OrganizationChartModelTest(TestCase):
    """Test cases for OrganizationChart model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            first_name="Test",
            last_name="User",
        )

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
        self.department = Department.objects.create(
            name="Phòng Nhân sự", code="NS", block=self.block, branch=self.branch
        )
        self.position = Position.objects.create(name="Trưởng phòng", code="TP")

    def test_create_organization_chart(self):
        """Test creating an organization chart entry"""
        org_chart = OrganizationChart.objects.create(
            employee=self.user,
            position=self.position,
            department=self.department,
            start_date=date.today(),
            is_primary=True,
        )

        self.assertEqual(org_chart.employee, self.user)
        self.assertEqual(org_chart.position, self.position)
        self.assertEqual(org_chart.department, self.department)
        self.assertTrue(org_chart.is_primary)
        self.assertTrue(org_chart.is_active)
        self.assertIsNone(org_chart.end_date)

    def test_organization_chart_str(self):
        """Test string representation of organization chart"""
        org_chart = OrganizationChart.objects.create(
            employee=self.user,
            position=self.position,
            department=self.department,
            start_date=date.today(),
        )

        expected = f"{self.user.get_full_name()} - {self.position.name} at {self.department.name}"
        self.assertEqual(str(org_chart), expected)

    def test_organization_chart_validation(self):
        """Test organization chart custom validation"""
        # Create first primary position
        OrganizationChart.objects.create(
            employee=self.user,
            position=self.position,
            department=self.department,
            start_date=date.today(),
            is_primary=True,
        )

        # Create another position for the same user in same department
        another_position = Position.objects.create(
            name="Phó Trưởng phòng",
            code="PTP",
        )

        # This should not raise ValidationError if we're not trying to make it primary
        org_chart2 = OrganizationChart.objects.create(
            employee=self.user,
            position=another_position,
            department=self.department,
            start_date=date.today(),
            is_primary=False,
        )

        # But trying to make it primary should raise ValidationError
        org_chart2.is_primary = True
        with self.assertRaises(ValidationError):
            org_chart2.clean()

    def test_organization_unique_together(self):
        """Test organization chart unique constraint"""
        start_date = date.today()

        OrganizationChart.objects.create(
            employee=self.user,
            position=self.position,
            department=self.department,
            start_date=start_date,
        )

        # Should fail - same employee, position, department, start_date
        with self.assertRaises(Exception):  # IntegrityError
            OrganizationChart.objects.create(
                employee=self.user,
                position=self.position,
                department=self.department,
                start_date=start_date,
            )
