"""Tests for data scope functionality on Position and OrganizationChart models."""

from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.constants import DataScope
from apps.hrm.models import Block, Branch, Department, OrganizationChart, Position
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


class OrganizationChartEnhancedTest(TestCase):
    """Test OrganizationChart model with block and branch fields"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", first_name="Test", last_name="User"
        )

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

        self.branch = Branch.objects.create(
            name="Chi nhánh Hà Nội",
            code="HN",
            province=self.province,
            administrative_unit=self.administrative_unit,
        )
        self.block = Block.objects.create(
            name="Khối Hỗ trợ", code="HT", block_type=Block.BlockType.SUPPORT, branch=self.branch
        )
        self.department = Department.objects.create(
            name="Phòng Nhân sự", code="NS", block=self.block, branch=self.branch
        )
        self.position = Position.objects.create(name="Manager", code="MGR", data_scope=DataScope.DEPARTMENT)

    def test_create_org_chart_with_department_autofills_block_branch(self):
        """Test that creating an org chart with department auto-fills block and branch"""
        org_chart = OrganizationChart.objects.create(
            employee=self.user,
            position=self.position,
            department=self.department,
            start_date=date.today(),
            is_primary=True,
        )

        # Block and branch should be auto-filled
        self.assertEqual(org_chart.block, self.department.block)
        self.assertEqual(org_chart.branch, self.department.block.branch)

    def test_create_org_chart_with_block_autofills_branch(self):
        """Test that creating an org chart with block auto-fills branch"""
        org_chart = OrganizationChart.objects.create(
            employee=self.user,
            position=self.position,
            block=self.block,
            start_date=date.today(),
            is_primary=True,
        )

        # Branch should be auto-filled
        self.assertEqual(org_chart.branch, self.block.branch)
        # Department should be None
        self.assertIsNone(org_chart.department)

    def test_create_org_chart_with_branch_only(self):
        """Test creating an org chart with only branch"""
        org_chart = OrganizationChart.objects.create(
            employee=self.user,
            position=self.position,
            branch=self.branch,
            start_date=date.today(),
            is_primary=True,
        )

        # Only branch should be set
        self.assertEqual(org_chart.branch, self.branch)
        self.assertIsNone(org_chart.block)
        self.assertIsNone(org_chart.department)

    def test_org_chart_validation_requires_at_least_one_unit(self):
        """Test that org chart validation requires at least one organizational unit"""
        org_chart = OrganizationChart(
            employee=self.user, position=self.position, start_date=date.today(), is_primary=True
        )

        with self.assertRaises(ValidationError) as context:
            org_chart.clean()

        self.assertIn("__all__", context.exception.message_dict)

    def test_org_chart_validation_block_must_match_department(self):
        """Test that block must match department's block"""
        # Create another block in the same branch
        other_block = Block.objects.create(
            name="Khối Kinh doanh", code="KD", block_type=Block.BlockType.BUSINESS, branch=self.branch
        )

        org_chart = OrganizationChart(
            employee=self.user,
            position=self.position,
            department=self.department,
            block=other_block,  # Wrong block
            start_date=date.today(),
        )

        with self.assertRaises(ValidationError) as context:
            org_chart.clean()

        self.assertIn("block", context.exception.message_dict)

    def test_org_chart_validation_branch_must_match_department(self):
        """Test that branch must match department's branch"""
        # Create another branch
        other_branch = Branch.objects.create(
            name="Chi nhánh TP.HCM",
            code="HCM",
            province=self.province,
            administrative_unit=self.administrative_unit,
        )

        org_chart = OrganizationChart(
            employee=self.user,
            position=self.position,
            department=self.department,
            branch=other_branch,  # Wrong branch
            start_date=date.today(),
        )

        with self.assertRaises(ValidationError) as context:
            org_chart.clean()

        self.assertIn("branch", context.exception.message_dict)

    def test_org_chart_validation_branch_must_match_block(self):
        """Test that branch must match block's branch"""
        # Create another branch
        other_branch = Branch.objects.create(
            name="Chi nhánh TP.HCM",
            code="HCM",
            province=self.province,
            administrative_unit=self.administrative_unit,
        )

        org_chart = OrganizationChart(
            employee=self.user,
            position=self.position,
            block=self.block,
            branch=other_branch,  # Wrong branch
            start_date=date.today(),
        )

        with self.assertRaises(ValidationError) as context:
            org_chart.clean()

        self.assertIn("branch", context.exception.message_dict)


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

        # Users with different assignments
        self.user_ceo = User.objects.create_user(username="ceo", email="ceo@test.com")
        self.user_bd1 = User.objects.create_user(username="bd1", email="bd1@test.com")
        self.user_bh1 = User.objects.create_user(username="bh1", email="bh1@test.com")
        self.user_dm1 = User.objects.create_user(username="dm1", email="dm1@test.com")
        self.user_emp1 = User.objects.create_user(username="emp1", email="emp1@test.com")
        self.user_emp2 = User.objects.create_user(username="emp2", email="emp2@test.com")

        # Assignments
        OrganizationChart.objects.create(
            employee=self.user_ceo,
            position=self.pos_all,
            department=self.dept1,
            start_date=date.today(),
            is_active=True,
        )
        OrganizationChart.objects.create(
            employee=self.user_bd1,
            position=self.pos_branch,
            branch=self.branch1,
            start_date=date.today(),
            is_active=True,
        )
        OrganizationChart.objects.create(
            employee=self.user_bh1,
            position=self.pos_block,
            block=self.block1,
            start_date=date.today(),
            is_active=True,
        )
        OrganizationChart.objects.create(
            employee=self.user_dm1,
            position=self.pos_dept,
            department=self.dept1,
            start_date=date.today(),
            is_active=True,
        )
        OrganizationChart.objects.create(
            employee=self.user_emp1,
            position=self.pos_self,
            department=self.dept1,
            start_date=date.today(),
            is_active=True,
        )
        OrganizationChart.objects.create(
            employee=self.user_emp2,
            position=self.pos_self,
            department=self.dept2,
            start_date=date.today(),
            is_active=True,
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
        qs = User.objects.filter(organization_positions__isnull=False)
        filtered = filter_queryset_by_data_scope(qs, self.user_ceo, org_field="organization_positions__department")
        # CEO should see all users with assignments
        self.assertEqual(filtered.distinct().count(), 6)

    def test_filter_queryset_by_data_scope_dept_manager_sees_dept_only(self):
        """Test that department manager sees only their department"""
        # Create a queryset of OrganizationChart
        qs = OrganizationChart.objects.all()
        filtered = filter_queryset_by_data_scope(qs, self.user_dm1, org_field="department")

        # Should see only assignments in dept1
        dept1_assignments = filtered.filter(department=self.dept1).count()
        self.assertGreater(dept1_assignments, 0)

        # Should not see dept2 assignments
        dept2_assignments = filtered.filter(department=self.dept2).count()
        self.assertEqual(dept2_assignments, 0)

    def test_filter_queryset_by_data_scope_branch_director_sees_branch(self):
        """Test that branch director sees their entire branch"""
        qs = OrganizationChart.objects.all()
        filtered = filter_queryset_by_data_scope(qs, self.user_bd1, org_field="department")

        # Should see all assignments in branch1
        branch1_assignments = (
            filtered.filter(department__block__branch=self.branch1).count()
            + filtered.filter(block__branch=self.branch1).count()
            + filtered.filter(branch=self.branch1).count()
        )
        self.assertGreater(branch1_assignments, 0)

    def test_superuser_bypasses_filtering(self):
        """Test that superuser bypasses all filtering"""
        superuser = User.objects.create_superuser(username="admin", email="admin@test.com", password="admin")
        qs = User.objects.all()
        filtered = filter_queryset_by_data_scope(qs, superuser, org_field="organization_positions__department")
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

        # Users
        self.leader = User.objects.create_user(username="leader", email="leader@test.com")
        self.staff = User.objects.create_user(username="staff", email="staff@test.com")

        # Assignments
        OrganizationChart.objects.create(
            employee=self.leader,
            position=self.pos_leader,
            department=self.dept,
            start_date=date.today(),
            is_active=True,
        )
        OrganizationChart.objects.create(
            employee=self.staff,
            position=self.pos_staff,
            department=self.dept,
            start_date=date.today(),
            is_active=True,
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
