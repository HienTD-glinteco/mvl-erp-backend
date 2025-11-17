"""Tests for data scope functionality on Position models."""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.core.models import AdministrativeUnit, Nationality, Province
from apps.hrm.constants import DataScope
from apps.hrm.models import Block, Branch, ContractType, Department, Employee, Position
from apps.hrm.utils import collect_allowed_units, filter_queryset_by_data_scope

User = get_user_model()


class PositionDataScopeTest(TestCase):
    """Test Position model with data_scope and is_leadership fields"""

    def test_create_position_with_default_data_scope(self):
        """Test creating a position with default data scope"""
        position = Position.objects.create(name="Manager", code="MGR")
        self.assertEqual(position.data_scope, DataScope.DEPARTMENT)
        self.assertFalse(position.is_leadership)

    def test_create_position_with_custom_data_scope(self):
        """Test creating a position with custom data scope"""
        position = Position.objects.create(name="CEO", code="CEO", data_scope=DataScope.ALL, is_leadership=True)
        self.assertEqual(position.data_scope, DataScope.ALL)
        self.assertTrue(position.is_leadership)

    def test_position_data_scope_choices(self):
        """Test all data scope choices are valid"""
        for scope_value, _ in DataScope.choices:
            position = Position.objects.create(
                name=f"Position {scope_value}", code=scope_value.upper()[:10], data_scope=scope_value
            )
            self.assertEqual(position.data_scope, scope_value)


# OrganizationChartEnhancedTest class removed as OrganizationChart model no longer exists
# Employee model now directly stores position, department, block, and branch


class DataScopeFilteringTest(TestCase):
    """Test data scope filtering utilities"""

    def setUp(self):
        """Set up test data with multiple organizational units and users"""
        # Create organizational structure
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

        # Branch 1
        self.branch1 = Branch.objects.create(
            name="Branch 1", code="BR1", province=self.province, administrative_unit=self.administrative_unit
        )
        self.block1 = Block.objects.create(
            name="Block 1", code="BL1", block_type=Block.BlockType.SUPPORT, branch=self.branch1
        )
        self.dept1 = Department.objects.create(name="Dept 1", code="D1", block=self.block1, branch=self.branch1)

        # Branch 2
        self.branch2 = Branch.objects.create(
            name="Branch 2", code="BR2", province=self.province, administrative_unit=self.administrative_unit
        )
        self.block2 = Block.objects.create(
            name="Block 2", code="BL2", block_type=Block.BlockType.SUPPORT, branch=self.branch2
        )
        self.dept2 = Department.objects.create(name="Dept 2", code="D2", block=self.block2, branch=self.branch2)

        # Positions with different data scopes
        self.pos_all = Position.objects.create(name="CEO", code="CEO", data_scope=DataScope.ALL)
        self.pos_branch = Position.objects.create(name="Branch Director", code="BD", data_scope=DataScope.BRANCH)
        self.pos_block = Position.objects.create(name="Block Head", code="BH", data_scope=DataScope.BLOCK)
        self.pos_dept = Position.objects.create(name="Dept Manager", code="DM", data_scope=DataScope.DEPARTMENT)
        self.pos_self = Position.objects.create(name="Employee", code="EMP", data_scope=DataScope.SELF)

        # Create contract type and nationality for employees
        self.contract_type = ContractType.objects.create(name="Full-time")
        self.nationality = Nationality.objects.create(name="Vietnamese")

        # Users with different assignments
        # Changed to superuser to bypass RoleBasedPermission for API tests
        self.user_ceo = User.objects.create_user(username="ceo", email="ceo@test.com")
        self.user_bd1 = User.objects.create_user(username="bd1", email="bd1@test.com")
        self.user_bh1 = User.objects.create_user(username="bh1", email="bh1@test.com")
        self.user_dm1 = User.objects.create_user(username="dm1", email="dm1@test.com")
        self.user_emp1 = User.objects.create_user(username="emp1", email="emp1@test.com")
        self.user_emp2 = User.objects.create_user(username="emp2", email="emp2@test.com")

        # Create Employee records to link users with organizational structure
        Employee.objects.create(
            user=self.user_ceo,
            code="CEO001",
            fullname="CEO User",
            username="ceo",
            email="ceo@test.com",
            personal_email="ceo@personal.com",
            attendance_code="CEO001",
            position=self.pos_all,
            department=self.dept1,
            contract_type=self.contract_type,
            start_date=date.today(),
            date_of_birth=date(1970, 1, 1),
            nationality=self.nationality,
            citizen_id="CEO0001",
        )
        Employee.objects.create(
            user=self.user_bd1,
            code="BD001",
            fullname="Branch Director 1",
            username="bd1",
            email="bd1@test.com",
            personal_email="bd1@personal.com",
            attendance_code="BD001",
            position=self.pos_branch,
            department=self.dept1,
            contract_type=self.contract_type,
            start_date=date.today(),
            date_of_birth=date(1975, 1, 1),
            nationality=self.nationality,
            citizen_id="BD0001",
        )
        Employee.objects.create(
            user=self.user_bh1,
            code="BH001",
            fullname="Block Head 1",
            username="bh1",
            email="bh1@test.com",
            personal_email="bh1@personal.com",
            attendance_code="BH001",
            position=self.pos_block,
            department=self.dept1,
            contract_type=self.contract_type,
            start_date=date.today(),
            date_of_birth=date(1980, 1, 1),
            nationality=self.nationality,
            citizen_id="BH0001",
        )
        Employee.objects.create(
            user=self.user_dm1,
            code="DM001",
            fullname="Dept Manager 1",
            username="dm1",
            email="dm1@test.com",
            personal_email="dm1@personal.com",
            attendance_code="DM001",
            position=self.pos_dept,
            department=self.dept1,
            contract_type=self.contract_type,
            start_date=date.today(),
            date_of_birth=date(1985, 1, 1),
            nationality=self.nationality,
            citizen_id="DM0001",
        )
        Employee.objects.create(
            user=self.user_emp1,
            code="EMP001",
            fullname="Employee 1",
            username="emp1",
            email="emp1@test.com",
            personal_email="emp1@personal.com",
            attendance_code="EMP001",
            position=self.pos_self,
            department=self.dept1,
            contract_type=self.contract_type,
            start_date=date.today(),
            date_of_birth=date(1990, 1, 1),
            nationality=self.nationality,
            citizen_id="EMP0001",
        )
        Employee.objects.create(
            user=self.user_emp2,
            code="EMP002",
            fullname="Employee 2",
            username="emp2",
            email="emp2@test.com",
            personal_email="emp2@personal.com",
            attendance_code="EMP002",
            position=self.pos_self,
            department=self.dept2,
            contract_type=self.contract_type,
            start_date=date.today(),
            date_of_birth=date(1991, 1, 1),
            nationality=self.nationality,
            citizen_id="EMP0002",
        )

    def test_collect_allowed_units_for_ceo(self):
        """Test that CEO with 'all' scope gets full access"""
        allowed = collect_allowed_units(self.user_ceo)
        self.assertTrue(allowed.has_all)

    def test_collect_allowed_units_for_branch_director(self):
        """Test that branch director gets branch-level access"""
        allowed = collect_allowed_units(self.user_bd1)
        self.assertFalse(allowed.has_all)
        self.assertIn(self.branch1.id, allowed.branches)
        self.assertEqual(len(allowed.branches), 1)

    def test_collect_allowed_units_for_block_head(self):
        """Test that block head gets block-level access"""
        allowed = collect_allowed_units(self.user_bh1)
        self.assertFalse(allowed.has_all)
        self.assertIn(self.block1.id, allowed.blocks)
        self.assertEqual(len(allowed.blocks), 1)

    def test_collect_allowed_units_for_dept_manager(self):
        """Test that department manager gets department-level access"""
        allowed = collect_allowed_units(self.user_dm1)
        self.assertFalse(allowed.has_all)
        self.assertIn(self.dept1.id, allowed.departments)
        self.assertEqual(len(allowed.departments), 1)

    def test_collect_allowed_units_for_self_scope(self):
        """Test that employee with self scope only sees themselves"""
        allowed = collect_allowed_units(self.user_emp1)
        self.assertFalse(allowed.has_all)
        self.assertIn(self.user_emp1.id, allowed.employees)
        self.assertEqual(len(allowed.employees), 1)

    def test_filter_queryset_by_data_scope_ceo_sees_all(self):
        """Test that CEO sees all users"""
        qs = User.objects.filter(employee__isnull=False)
        filtered = filter_queryset_by_data_scope(qs, self.user_ceo, org_field="employee__department")
        # CEO should see all users with assignments
        self.assertEqual(filtered.distinct().count(), 6)

    def test_filter_queryset_by_data_scope_dept_manager_sees_dept_only(self):
        """Test that department manager sees only their department"""
        qs = Employee.objects.all()
        filtered = filter_queryset_by_data_scope(qs, self.user_dm1, org_field="department")

        # Should see only assignments in dept1
        dept1_assignments = filtered.filter(department=self.dept1).count()
        self.assertGreater(dept1_assignments, 0)

        # Should not see dept2 assignments
        dept2_assignments = filtered.filter(department=self.dept2).count()
        self.assertEqual(dept2_assignments, 0)

    def test_filter_queryset_by_data_scope_branch_director_sees_branch(self):
        """Test that branch director sees their entire branch"""
        qs = Employee.objects.all()
        filtered = filter_queryset_by_data_scope(qs, self.user_bd1, org_field="department")

        # Should see all assignments in branch1
        branch1_count = filtered.filter(branch=self.branch1).count()
        self.assertGreater(branch1_count, 0)

    def test_superuser_bypasses_filtering(self):
        """Test that superuser bypasses all filtering"""
        superuser = User.objects.create_superuser(username="admin", email="admin@test.com", password="admin")
        qs = User.objects.all()
        filtered = filter_queryset_by_data_scope(qs, superuser, org_field="employee__department")
        self.assertEqual(filtered.count(), User.objects.count())


class LeadershipFilteringTest(TestCase):
    """Test leadership filtering functionality"""

    def setUp(self):
        """Set up test data"""
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
            name="Branch 1", code="BR1", province=self.province, administrative_unit=self.administrative_unit
        )
        self.block = Block.objects.create(
            name="Block 1", code="BL1", block_type=Block.BlockType.SUPPORT, branch=self.branch
        )
        self.dept = Department.objects.create(name="Dept 1", code="D1", block=self.block, branch=self.branch)

        # Positions
        self.pos_leader = Position.objects.create(
            name="Director", code="DIR", is_leadership=True, data_scope=DataScope.DEPARTMENT
        )
        self.pos_staff = Position.objects.create(
            name="Staff", code="STAFF", is_leadership=False, data_scope=DataScope.SELF
        )

        # Create contract type and nationality
        self.contract_type = ContractType.objects.create(name="Full-time")
        self.nationality = Nationality.objects.create(name="Vietnamese")

        # Users
        self.leader = User.objects.create_user(username="leader", email="leader@test.com")
        self.staff = User.objects.create_user(username="staff", email="staff@test.com")

        # Create Employee records
        Employee.objects.create(
            user=self.leader,
            code="LEAD001",
            fullname="Leader User",
            username="leader",
            email="leader@test.com",
            personal_email="leader@personal.com",
            attendance_code="LEAD001",
            position=self.pos_leader,
            department=self.dept,
            contract_type=self.contract_type,
            start_date=date.today(),
            date_of_birth=date(1980, 1, 1),
            nationality=self.nationality,
            citizen_id="LEAD0001",
        )
        Employee.objects.create(
            user=self.staff,
            code="STAFF001",
            fullname="Staff User",
            username="staff",
            email="staff@test.com",
            personal_email="staff@personal.com",
            attendance_code="STAFF001",
            position=self.pos_staff,
            department=self.dept,
            contract_type=self.contract_type,
            start_date=date.today(),
            date_of_birth=date(1985, 1, 1),
            nationality=self.nationality,
            citizen_id="STAFF0001",
        )

    def test_filter_by_leadership_includes_only_leaders(self):
        """Test filtering by leadership position"""
        from apps.hrm.utils import filter_by_leadership

        qs = User.objects.all()
        filtered = filter_by_leadership(qs, leadership_only=True)

        # Should include leader
        self.assertIn(self.leader, filtered)
        # Should not include staff
        self.assertNotIn(self.staff, filtered)

    def test_filter_by_leadership_false_returns_all(self):
        """Test that leadership filter with False returns all users"""
        from apps.hrm.utils import filter_by_leadership

        qs = User.objects.all()
        filtered = filter_by_leadership(qs, leadership_only=False)

        self.assertEqual(filtered.count(), qs.count())


class BranchDirectorDataScopeTest(TestCase):
    """Test branch director with branch-only assignment can see all child department employees"""

    def setUp(self):
        """Set up organizational hierarchy with branch director"""
        # Create base data
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

        # Create branch
        self.branch = Branch.objects.create(
            name="Branch Hanoi", code="HN", province=self.province, administrative_unit=self.administrative_unit
        )

        # Create multiple blocks in the branch
        self.block1 = Block.objects.create(
            name="Block Support", code="SUP", block_type=Block.BlockType.SUPPORT, branch=self.branch
        )
        self.block2 = Block.objects.create(
            name="Block Business", code="BIZ", block_type=Block.BlockType.BUSINESS, branch=self.branch
        )

        # Create multiple departments under blocks
        self.dept1 = Department.objects.create(name="HR Department", code="HR", block=self.block1, branch=self.branch)
        self.dept2 = Department.objects.create(
            name="Finance Department", code="FIN", block=self.block1, branch=self.branch
        )
        self.dept3 = Department.objects.create(
            name="Sales Department", code="SALES", block=self.block2, branch=self.branch
        )

        # Create positions
        self.pos_branch_director = Position.objects.create(
            name="Branch Director", code="BRDIR", data_scope=DataScope.BRANCH, is_leadership=True
        )
        self.pos_employee = Position.objects.create(
            name="Employee", code="EMP", data_scope=DataScope.SELF, is_leadership=False
        )

        # Create contract type and nationality
        self.contract_type = ContractType.objects.create(name="Full-time")
        self.nationality = Nationality.objects.create(name="Vietnamese")

        # Create users
        self.branch_director = User.objects.create_user(
            username="branch_director", email="director@branch.com", first_name="Branch", last_name="Director"
        )
        self.emp_dept1 = User.objects.create_user(
            username="emp_dept1", email="emp1@branch.com", first_name="Employee", last_name="One"
        )
        self.emp_dept2 = User.objects.create_user(
            username="emp_dept2", email="emp2@branch.com", first_name="Employee", last_name="Two"
        )
        self.emp_dept3 = User.objects.create_user(
            username="emp_dept3", email="emp3@branch.com", first_name="Employee", last_name="Three"
        )

        # Create Employee records
        Employee.objects.create(
            user=self.branch_director,
            code="BRDIR001",
            fullname="Branch Director",
            username="branch_director",
            email="director@branch.com",
            personal_email="director@personal.com",
            attendance_code="BRDIR001",
            position=self.pos_branch_director,
            department=self.dept1,
            contract_type=self.contract_type,
            start_date=date.today(),
            date_of_birth=date(1975, 1, 1),
            nationality=self.nationality,
            citizen_id="BRDIR0001",
        )
        Employee.objects.create(
            user=self.emp_dept1,
            code="EMP001",
            fullname="Employee One",
            username="emp_dept1",
            email="emp1@branch.com",
            personal_email="emp1@personal.com",
            attendance_code="EMP001",
            position=self.pos_employee,
            department=self.dept1,
            contract_type=self.contract_type,
            start_date=date.today(),
            date_of_birth=date(1990, 1, 1),
            nationality=self.nationality,
            citizen_id="EMP0001",
        )
        Employee.objects.create(
            user=self.emp_dept2,
            code="EMP002",
            fullname="Employee Two",
            username="emp_dept2",
            email="emp2@branch.com",
            personal_email="emp2@personal.com",
            attendance_code="EMP002",
            position=self.pos_employee,
            department=self.dept2,
            contract_type=self.contract_type,
            start_date=date.today(),
            date_of_birth=date(1991, 1, 1),
            nationality=self.nationality,
            citizen_id="EMP0002",
        )
        Employee.objects.create(
            user=self.emp_dept3,
            code="EMP003",
            fullname="Employee Three",
            username="emp_dept3",
            email="emp3@branch.com",
            personal_email="emp3@personal.com",
            attendance_code="EMP003",
            position=self.pos_employee,
            department=self.dept3,
            contract_type=self.contract_type,
            start_date=date.today(),
            date_of_birth=date(1992, 1, 1),
            nationality=self.nationality,
            citizen_id="EMP0003",
        )

    def test_branch_director_sees_all_child_department_employees(self):
        """Test branch director with branch-only assignment can see employees in all child departments"""
        # Filter employees by branch director's scope
        qs = User.objects.filter(employee__isnull=False)
        filtered = filter_queryset_by_data_scope(qs, self.branch_director, org_field="employee__department")

        # Branch director should see all employees in the branch
        self.assertIn(self.emp_dept1, filtered)
        self.assertIn(self.emp_dept2, filtered)
        self.assertIn(self.emp_dept3, filtered)
        self.assertIn(self.branch_director, filtered)  # Should also see themselves

        # Verify count (4 users with assignments)
        self.assertEqual(filtered.distinct().count(), 4)

    def test_branch_director_sees_all_department_employees(self):
        """Test branch director can see all Employee records in their branch"""
        qs = Employee.objects.all()
        filtered = filter_queryset_by_data_scope(qs, self.branch_director, org_field="department")

        # Should see all 4 employees in branch (branch director + 3 dept employees)
        self.assertEqual(filtered.count(), 4)

        # Verify specific departments are visible
        dept1_count = filtered.filter(department=self.dept1).count()
        dept2_count = filtered.filter(department=self.dept2).count()
        dept3_count = filtered.filter(department=self.dept3).count()

        # Branch director is in dept1, so dept1 should have 2 (director + 1 employee)
        self.assertEqual(dept1_count, 2)
        self.assertEqual(dept2_count, 1)
        self.assertEqual(dept3_count, 1)

    def test_branch_director_allowed_units_includes_branch(self):
        """Test that branch director's allowed units correctly includes branch ID"""
        allowed = collect_allowed_units(self.branch_director)

        self.assertFalse(allowed.has_all)
        self.assertIn(self.branch.id, allowed.branches)
        self.assertEqual(len(allowed.branches), 1)
        # Should not have block or department level access
        self.assertEqual(len(allowed.blocks), 0)
        self.assertEqual(len(allowed.departments), 0)


class BlockHeadDataScopeTest(TestCase):
    """Test block head with block-only assignment can see all child department employees"""

    def setUp(self):
        """Set up organizational hierarchy with block head"""
        # Create base data
        self.province = Province.objects.create(
            code="02",
            name="Thành phố Hồ Chí Minh",
            english_name="Ho Chi Minh",
            level=Province.ProvinceLevel.CENTRAL_CITY,
            enabled=True,
        )
        self.administrative_unit = AdministrativeUnit.objects.create(
            code="002",
            name="Quận 1",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
            enabled=True,
        )

        # Create branch and block
        self.branch = Branch.objects.create(
            name="Branch HCMC", code="HCM", province=self.province, administrative_unit=self.administrative_unit
        )
        self.block = Block.objects.create(
            name="Support Block", code="SUPP", block_type=Block.BlockType.SUPPORT, branch=self.branch
        )

        # Create multiple departments under the block
        self.dept1 = Department.objects.create(name="IT Department", code="IT", block=self.block, branch=self.branch)
        self.dept2 = Department.objects.create(
            name="Admin Department", code="ADM", block=self.block, branch=self.branch
        )
        self.dept3 = Department.objects.create(
            name="Facilities Department", code="FAC", block=self.block, branch=self.branch
        )

        # Create another block in same branch for negative testing
        self.other_block = Block.objects.create(
            name="Business Block", code="BUS", block_type=Block.BlockType.BUSINESS, branch=self.branch
        )
        self.other_dept = Department.objects.create(
            name="Sales Department", code="SAL", block=self.other_block, branch=self.branch
        )

        # Create positions
        self.pos_block_head = Position.objects.create(
            name="Block Head", code="BLKHD", data_scope=DataScope.BLOCK, is_leadership=True
        )
        self.pos_employee = Position.objects.create(
            name="Staff", code="STF", data_scope=DataScope.SELF, is_leadership=False
        )

        # Create contract type and nationality
        self.contract_type = ContractType.objects.create(name="Full-time")
        self.nationality = Nationality.objects.create(name="Vietnamese")

        # Create users
        self.block_head = User.objects.create_user(
            username="block_head", email="head@block.com", first_name="Block", last_name="Head"
        )
        self.emp_dept1 = User.objects.create_user(
            username="emp_it", email="emp_it@block.com", first_name="IT", last_name="Employee"
        )
        self.emp_dept2 = User.objects.create_user(
            username="emp_admin", email="emp_admin@block.com", first_name="Admin", last_name="Employee"
        )
        self.emp_dept3 = User.objects.create_user(
            username="emp_fac", email="emp_fac@block.com", first_name="Facilities", last_name="Employee"
        )
        self.emp_other_block = User.objects.create_user(
            username="emp_sales", email="emp_sales@block.com", first_name="Sales", last_name="Employee"
        )

        # Create Employee records
        Employee.objects.create(
            user=self.block_head,
            code="BLKHD001",
            fullname="Block Head",
            username="block_head",
            email="head@block.com",
            personal_email="head@personal.com",
            attendance_code="BLKHD001",
            position=self.pos_block_head,
            department=self.dept1,
            contract_type=self.contract_type,
            start_date=date.today(),
            date_of_birth=date(1975, 1, 1),
            nationality=self.nationality,
            citizen_id="BLKHD0001",
        )
        Employee.objects.create(
            user=self.emp_dept1,
            code="IT001",
            fullname="IT Employee",
            username="emp_it",
            email="emp_it@block.com",
            personal_email="emp_it@personal.com",
            attendance_code="IT001",
            position=self.pos_employee,
            department=self.dept1,
            contract_type=self.contract_type,
            start_date=date.today(),
            date_of_birth=date(1990, 1, 1),
            nationality=self.nationality,
            citizen_id="IT0001",
        )
        Employee.objects.create(
            user=self.emp_dept2,
            code="ADM001",
            fullname="Admin Employee",
            username="emp_admin",
            email="emp_admin@block.com",
            personal_email="emp_admin@personal.com",
            attendance_code="ADM001",
            position=self.pos_employee,
            department=self.dept2,
            contract_type=self.contract_type,
            start_date=date.today(),
            date_of_birth=date(1991, 1, 1),
            nationality=self.nationality,
            citizen_id="ADM0001",
        )
        Employee.objects.create(
            user=self.emp_dept3,
            code="FAC001",
            fullname="Facilities Employee",
            username="emp_fac",
            email="emp_fac@block.com",
            personal_email="emp_fac@personal.com",
            attendance_code="FAC001",
            position=self.pos_employee,
            department=self.dept3,
            contract_type=self.contract_type,
            start_date=date.today(),
            date_of_birth=date(1992, 1, 1),
            nationality=self.nationality,
            citizen_id="FAC0001",
        )
        Employee.objects.create(
            user=self.emp_other_block,
            code="SAL001",
            fullname="Sales Employee",
            username="emp_sales",
            email="emp_sales@block.com",
            personal_email="emp_sales@personal.com",
            attendance_code="SAL001",
            position=self.pos_employee,
            department=self.other_dept,
            contract_type=self.contract_type,
            start_date=date.today(),
            date_of_birth=date(1993, 1, 1),
            nationality=self.nationality,
            citizen_id="SAL0001",
        )

    def test_block_head_sees_all_child_department_employees(self):
        """Test block head with block-only assignment can see employees in all child departments"""
        # Filter employees by block head's scope
        qs = User.objects.filter(employee__isnull=False)
        filtered = filter_queryset_by_data_scope(qs, self.block_head, org_field="employee__department")

        # Block head should see employees in their block
        self.assertIn(self.emp_dept1, filtered)
        self.assertIn(self.emp_dept2, filtered)
        self.assertIn(self.emp_dept3, filtered)
        self.assertIn(self.block_head, filtered)  # Should see themselves

        # Should NOT see employee from other block
        self.assertNotIn(self.emp_other_block, filtered)

        # Verify count (4 users in the block)
        self.assertEqual(filtered.distinct().count(), 4)

    def test_block_head_sees_all_department_employees_in_block(self):
        """Test block head can see all Employee records in their block only"""
        qs = Employee.objects.all()
        filtered = filter_queryset_by_data_scope(qs, self.block_head, org_field="department")

        # Should see 4 employees in their block (block head + 3 dept employees)
        self.assertEqual(filtered.count(), 4)

        # Verify specific departments in the block are visible
        dept1_count = filtered.filter(department=self.dept1).count()
        dept2_count = filtered.filter(department=self.dept2).count()
        dept3_count = filtered.filter(department=self.dept3).count()

        # Block head is in dept1, so dept1 should have 2 (head + 1 employee)
        self.assertEqual(dept1_count, 2)
        self.assertEqual(dept2_count, 1)
        self.assertEqual(dept3_count, 1)

        # Should NOT see other block's department
        other_dept_assignments = filtered.filter(department=self.other_dept).count()
        self.assertEqual(other_dept_assignments, 0)

    def test_block_head_allowed_units_includes_block(self):
        """Test that block head's allowed units correctly includes block ID"""
        allowed = collect_allowed_units(self.block_head)

        self.assertFalse(allowed.has_all)
        self.assertIn(self.block.id, allowed.blocks)
        self.assertEqual(len(allowed.blocks), 1)
        # Should not have branch or department level access
        self.assertEqual(len(allowed.branches), 0)
        self.assertEqual(len(allowed.departments), 0)

    def test_block_head_does_not_see_other_blocks_in_same_branch(self):
        """Test block head cannot see employees from other blocks in the same branch"""
        # Create another block head for the other block
        other_block_head = User.objects.create_user(
            username="other_block_head", email="other@block.com", first_name="Other", last_name="Head"
        )
        pos_other_block_head = Position.objects.create(
            name="Business Block Head", code="BBHD", data_scope=DataScope.BLOCK, is_leadership=True
        )
        Employee.objects.create(
            user=other_block_head,
            code="BBHD001",
            fullname="Other Block Head",
            username="other_block_head",
            email="other@block.com",
            personal_email="other@personal.com",
            attendance_code="BBHD001",
            position=pos_other_block_head,
            department=self.other_dept,
            contract_type=self.contract_type,
            start_date=date.today(),
            date_of_birth=date(1976, 1, 1),
            nationality=self.nationality,
            citizen_id="BBHD0001",
        )

        # Original block head should not see the other block head
        qs = User.objects.filter(employee__isnull=False)
        filtered = filter_queryset_by_data_scope(qs, self.block_head, org_field="employee__department")

        self.assertNotIn(other_block_head, filtered)
        self.assertNotIn(self.emp_other_block, filtered)


class EmployeeDataScopeFilterBackendTest(TestCase):
    """Test DataScopeFilterBackend with real Employee model to demonstrate practical application"""

    def setUp(self):
        """Set up organizational hierarchy with employees"""
        # Import Employee model
        from apps.core.models import Nationality
        from apps.hrm.models import ContractType, Employee

        # Create base data
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

        # Create organizational structure
        self.branch_hn = Branch.objects.create(
            name="Branch Hanoi", code="HN", province=self.province, administrative_unit=self.administrative_unit
        )
        self.branch_hcm = Branch.objects.create(
            name="Branch HCMC", code="HCM", province=self.province, administrative_unit=self.administrative_unit
        )

        # Blocks in Hanoi branch
        self.block_support_hn = Block.objects.create(
            name="Support Block HN", code="SUP-HN", block_type=Block.BlockType.SUPPORT, branch=self.branch_hn
        )
        self.block_business_hn = Block.objects.create(
            name="Business Block HN", code="BIZ-HN", block_type=Block.BlockType.BUSINESS, branch=self.branch_hn
        )

        # Block in HCMC branch
        self.block_support_hcm = Block.objects.create(
            name="Support Block HCM", code="SUP-HCM", block_type=Block.BlockType.SUPPORT, branch=self.branch_hcm
        )

        # Departments in Hanoi Support Block
        self.dept_hr_hn = Department.objects.create(
            name="HR Department HN", code="HR-HN", block=self.block_support_hn, branch=self.branch_hn
        )
        self.dept_it_hn = Department.objects.create(
            name="IT Department HN", code="IT-HN", block=self.block_support_hn, branch=self.branch_hn
        )

        # Department in Hanoi Business Block
        self.dept_sales_hn = Department.objects.create(
            name="Sales Department HN", code="SALES-HN", block=self.block_business_hn, branch=self.branch_hn
        )

        # Department in HCMC
        self.dept_hr_hcm = Department.objects.create(
            name="HR Department HCM", code="HR-HCM", block=self.block_support_hcm, branch=self.branch_hcm
        )

        # Create positions
        self.pos_branch_director = Position.objects.create(
            name="Branch Director", code="BRDIR", data_scope=DataScope.BRANCH, is_leadership=True
        )
        self.pos_block_head = Position.objects.create(
            name="Block Head", code="BLKHD", data_scope=DataScope.BLOCK, is_leadership=True
        )
        self.pos_dept_manager = Position.objects.create(
            name="Department Manager", code="DPTMGR", data_scope=DataScope.DEPARTMENT, is_leadership=True
        )
        self.pos_employee = Position.objects.create(
            name="Employee", code="EMP", data_scope=DataScope.SELF, is_leadership=False
        )

        # Create nationality for employees
        self.nationality = Nationality.objects.create(name="Vietnamese")

        # Create contract type
        self.contract_type = ContractType.objects.create(name="Full-time")

        # Create users for organizational chart
        self.user_branch_director = User.objects.create_user(
            username="branch_director_hn", email="bd_hn@company.com", first_name="Director", last_name="HN"
        )
        self.user_block_head = User.objects.create_user(
            username="block_head_support", email="bh_sup@company.com", first_name="BlockHead", last_name="Support"
        )
        self.user_dept_manager = User.objects.create_user(
            username="dept_mgr_hr", email="mgr_hr@company.com", first_name="Manager", last_name="HR"
        )

        # Create employees in different departments
        self.emp_hr_hn_1 = Employee.objects.create(
            code="MV001",
            fullname="Employee HR HN 1",
            username="emp_hr_hn_1",
            email="emp_hr_hn_1@company.com",
            attendance_code="1001",
            branch=self.branch_hn,
            block=self.block_support_hn,
            department=self.dept_hr_hn,
            position=self.pos_employee,
            contract_type=self.contract_type,
            start_date=date.today(),
            date_of_birth=date(1990, 1, 1),
            personal_email="emp_hr_hn_1_personal@gmail.com",
            nationality=self.nationality,
            citizen_id="000000000001",
        )

        self.emp_hr_hn_2 = Employee.objects.create(
            code="MV002",
            fullname="Employee HR HN 2",
            username="emp_hr_hn_2",
            email="emp_hr_hn_2@company.com",
            personal_email="emp_hr_hn_2_personal@gmail.com",
            attendance_code="1002",
            branch=self.branch_hn,
            block=self.block_support_hn,
            department=self.dept_hr_hn,
            position=self.pos_employee,
            contract_type=self.contract_type,
            start_date=date.today(),
            date_of_birth=date(1991, 1, 1),
            nationality=self.nationality,
            citizen_id="000000000002",
        )

        self.emp_it_hn = Employee.objects.create(
            code="MV003",
            fullname="Employee IT HN",
            username="emp_it_hn",
            email="emp_it_hn@company.com",
            personal_email="emp_it_hn_personal@gmail.com",
            attendance_code="1003",
            branch=self.branch_hn,
            block=self.block_support_hn,
            department=self.dept_it_hn,
            position=self.pos_employee,
            contract_type=self.contract_type,
            start_date=date.today(),
            date_of_birth=date(1992, 1, 1),
            nationality=self.nationality,
            citizen_id="000000000003",
        )

        self.emp_sales_hn = Employee.objects.create(
            code="MV004",
            fullname="Employee Sales HN",
            username="emp_sales_hn",
            email="emp_sales_hn@company.com",
            personal_email="emp_sales_hn_personal@gmail.com",
            attendance_code="1004",
            branch=self.branch_hn,
            block=self.block_business_hn,
            department=self.dept_sales_hn,
            position=self.pos_employee,
            contract_type=self.contract_type,
            start_date=date.today(),
            date_of_birth=date(1993, 1, 1),
            nationality=self.nationality,
            citizen_id="000000000004",
        )

        self.emp_hr_hcm = Employee.objects.create(
            code="MV005",
            fullname="Employee HR HCM",
            username="emp_hr_hcm",
            email="emp_hr_hcm@company.com",
            personal_email="emp_hr_hcm_personal@gmail.com",
            attendance_code="2001",
            branch=self.branch_hcm,
            block=self.block_support_hcm,
            department=self.dept_hr_hcm,
            position=self.pos_employee,
            contract_type=self.contract_type,
            start_date=date.today(),
            date_of_birth=date(1994, 1, 1),
            nationality=self.nationality,
            citizen_id="000000000005",
        )

        # Create Employee records for managers
        Employee.objects.create(
            user=self.user_branch_director,
            code="BRDIR001",
            fullname="Director HN",
            username="branch_director_hn",
            email="bd_hn@company.com",
            personal_email="bd_hn@personal.com",
            attendance_code="BRDIR001",
            position=self.pos_branch_director,
            department=self.dept_hr_hn,
            contract_type=self.contract_type,
            start_date=date.today(),
            date_of_birth=date(1975, 1, 1),
            nationality=self.nationality,
            citizen_id="BRDIR0001",
        )
        Employee.objects.create(
            user=self.user_block_head,
            code="BLKHD001",
            fullname="BlockHead Support",
            username="block_head_support",
            email="bh_sup@company.com",
            personal_email="bh_sup@personal.com",
            attendance_code="BLKHD001",
            position=self.pos_block_head,
            department=self.dept_hr_hn,
            contract_type=self.contract_type,
            start_date=date.today(),
            date_of_birth=date(1980, 1, 1),
            nationality=self.nationality,
            citizen_id="BLKHD0001",
        )
        Employee.objects.create(
            user=self.user_dept_manager,
            code="DPTMGR001",
            fullname="Manager HR",
            username="dept_mgr_hr",
            email="mgr_hr@company.com",
            personal_email="mgr_hr@personal.com",
            attendance_code="DPTMGR001",
            position=self.pos_dept_manager,
            department=self.dept_hr_hn,
            contract_type=self.contract_type,
            start_date=date.today(),
            date_of_birth=date(1985, 1, 1),
            nationality=self.nationality,
            citizen_id="DPTMGR0001",
        )

    def test_branch_director_sees_all_employees_in_branch(self):
        """Test branch director can see all employees across all departments in their branch"""
        from apps.hrm.models import Employee

        # Filter employees using data scope
        qs = Employee.objects.all()
        filtered = filter_queryset_by_data_scope(qs, self.user_branch_director, org_field="department")

        # Branch director should see all employees in Hanoi branch (branch_director + block_head + dept_manager + 4 regular employees = 7)
        self.assertIn(self.emp_hr_hn_1, filtered)
        self.assertIn(self.emp_hr_hn_2, filtered)
        self.assertIn(self.emp_it_hn, filtered)
        self.assertIn(self.emp_sales_hn, filtered)

        # Should NOT see employees in HCMC branch
        self.assertNotIn(self.emp_hr_hcm, filtered)

        # Should see 7 employees in Hanoi branch (3 managers + 4 regular employees)
        self.assertEqual(filtered.count(), 7)

    def test_block_head_sees_employees_in_block_only(self):
        """Test block head can see employees in their block across multiple departments"""
        from apps.hrm.models import Employee

        # Filter employees using data scope
        qs = Employee.objects.all()
        filtered = filter_queryset_by_data_scope(qs, self.user_block_head, org_field="department")

        # Block head should see employees in Support Block (HR and IT departments + block head + dept manager)
        self.assertIn(self.emp_hr_hn_1, filtered)
        self.assertIn(self.emp_hr_hn_2, filtered)
        self.assertIn(self.emp_it_hn, filtered)

        # Should NOT see employees in Business Block (same branch, different block)
        self.assertNotIn(self.emp_sales_hn, filtered)

        # Should NOT see employees in HCMC
        self.assertNotIn(self.emp_hr_hcm, filtered)

        # Should see 6 employees in Support Block (block head + dept manager + 4 regular in HR/IT depts)
        # Actually: block_head(hr), dept_manager(hr), emp_hr_hn_1, emp_hr_hn_2, emp_it_hn = 5
        # But we also have branch_director in HR dept, so 6 total
        self.assertEqual(filtered.count(), 6)

    def test_dept_manager_sees_employees_in_department_only(self):
        """Test department manager can see employees in their department only"""
        from apps.hrm.models import Employee

        # Filter employees using data scope
        qs = Employee.objects.all()
        filtered = filter_queryset_by_data_scope(qs, self.user_dept_manager, org_field="department")

        # Department manager should see only employees in HR department HN
        self.assertIn(self.emp_hr_hn_1, filtered)
        self.assertIn(self.emp_hr_hn_2, filtered)

        # Should NOT see employees in other departments
        self.assertNotIn(self.emp_it_hn, filtered)
        self.assertNotIn(self.emp_sales_hn, filtered)
        self.assertNotIn(self.emp_hr_hcm, filtered)

        # Should see 5 employees in HR department (branch_director + block_head + dept_manager + 2 regular)
        self.assertEqual(filtered.count(), 5)

    def test_data_scope_filter_backend_integration(self):
        """Test DataScopeFilterBackend can be applied to Employee queryset

        This test demonstrates that DataScopeFilterBackend works with real Employee model,
        proving the practical applicability of the data scope feature.
        """
        from apps.hrm.models import Employee

        # Use the filter function directly (which is what the FilterBackend calls internally)
        # This demonstrates the same behavior as using DataScopeFilterBackend in a ViewSet
        qs = Employee.objects.all()
        filtered = filter_queryset_by_data_scope(qs, self.user_branch_director, org_field="department")

        # Branch director should see all employees in their branch (Hanoi)
        # Including: branch_director, block_head, dept_manager + 4 regular employees = 7 total
        self.assertEqual(filtered.count(), 7, "Branch director should see 7 employees in Hanoi branch")
        self.assertIn(self.emp_hr_hn_1, filtered, "Should see HR employee 1")
        self.assertIn(self.emp_hr_hn_2, filtered, "Should see HR employee 2")
        self.assertIn(self.emp_it_hn, filtered, "Should see IT employee")
        self.assertIn(self.emp_sales_hn, filtered, "Should see Sales employee")
        self.assertNotIn(self.emp_hr_hcm, filtered, "Should NOT see HCMC employee")

    def test_employee_filtering_across_multiple_branches(self):
        """Test that employees are properly scoped when multiple branches exist"""
        from apps.hrm.models import Employee

        # Create a second branch director for HCMC
        user_branch_director_hcm = User.objects.create_user(
            username="branch_director_hcm", email="bd_hcm@company.com", first_name="Director", last_name="HCM"
        )

        Employee.objects.create(
            user=user_branch_director_hcm,
            code="BRDIR002",
            fullname="Director HCM",
            username="branch_director_hcm",
            email="bd_hcm@company.com",
            personal_email="bd_hcm@personal.com",
            attendance_code="BRDIR002",
            position=self.pos_branch_director,
            department=self.dept_hr_hcm,
            contract_type=self.contract_type,
            start_date=date.today(),
            date_of_birth=date(1976, 1, 1),
            nationality=self.nationality,
            citizen_id="BRDIR0002",
        )

        # HN branch director should only see HN employees
        qs_hn = Employee.objects.all()
        filtered_hn = filter_queryset_by_data_scope(qs_hn, self.user_branch_director, org_field="department")
        self.assertEqual(filtered_hn.count(), 7)
        self.assertNotIn(self.emp_hr_hcm, filtered_hn)

        # HCM branch director should only see HCM employees
        qs_hcm = Employee.objects.all()
        filtered_hcm = filter_queryset_by_data_scope(qs_hcm, user_branch_director_hcm, org_field="department")
        self.assertEqual(filtered_hcm.count(), 2)  # HCM director + 1 HR employee
        self.assertIn(self.emp_hr_hcm, filtered_hcm)
        self.assertNotIn(self.emp_hr_hn_1, filtered_hcm)

    def test_employee_queryset_with_leadership_filter(self):
        """Test combining data scope with leadership filter on Employee queryset"""
        from apps.hrm.models import Employee

        # Create a manager employee with leadership position
        manager_emp = Employee.objects.create(
            code="MV006",
            fullname="Manager Employee",
            username="emp_manager",
            email="emp_manager@company.com",
            personal_email="emp_manager_personal@gmail.com",
            attendance_code="1005",
            branch=self.branch_hn,
            block=self.block_support_hn,
            department=self.dept_hr_hn,
            position=self.pos_dept_manager,  # Leadership position
            contract_type=self.contract_type,
            start_date=date.today(),
            date_of_birth=date(1985, 1, 1),
            nationality=self.nationality,
        )

        # Filter by data scope first
        qs = Employee.objects.all()
        filtered = filter_queryset_by_data_scope(qs, self.user_branch_director, org_field="department")

        # Then filter by leadership using Employee's position field
        leadership_filtered = filtered.filter(position__is_leadership=True)

        # Should only see employees with leadership positions
        self.assertIn(manager_emp, leadership_filtered)
        self.assertNotIn(self.emp_hr_hn_1, leadership_filtered)
        self.assertNotIn(self.emp_hr_hn_2, leadership_filtered)
