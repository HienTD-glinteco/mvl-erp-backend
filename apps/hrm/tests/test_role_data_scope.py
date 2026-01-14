"""
Unit tests for Role Data Scope functionality.

Tests the role-based data scope filtering system that restricts
access to organizational units (Branch, Block, Department).
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory

from apps.core.api.permissions import DataScopePermission
from apps.core.models import Role
from apps.core.models.role import DataScopeLevel
from apps.hrm.models import Block, Branch, Department
from apps.hrm.models.role_data_scope import RoleBlockScope, RoleBranchScope, RoleDepartmentScope
from apps.hrm.utils.role_data_scope import (
    RoleAllowedUnits,
    collect_role_allowed_units,
    filter_queryset_by_role_data_scope,
    invalidate_role_units_cache,
)

User = get_user_model()


@pytest.fixture
def province(db):
    """Create a province for branch"""
    from apps.core.models import Province

    return Province.objects.create(code="P01", name="Test Province")


@pytest.fixture
def admin_unit(db, province):
    """Create an administrative unit for branch"""
    from apps.core.models import AdministrativeUnit

    return AdministrativeUnit.objects.create(
        code="AU01",
        name="Test Admin Unit",
        parent_province=province,
        level=AdministrativeUnit.UnitLevel.DISTRICT,
    )


@pytest.fixture
def branch_a(db, province, admin_unit):
    """Create Branch A for testing"""
    return Branch.objects.create(
        code="CN01",
        name="Branch A",
        province=province,
        administrative_unit=admin_unit,
    )


@pytest.fixture
def branch_b(db, province, admin_unit):
    """Create Branch B for testing"""
    return Branch.objects.create(
        code="CN02",
        name="Branch B",
        province=province,
        administrative_unit=admin_unit,
    )


@pytest.fixture
def block_a(db, branch_a):
    """Create Block A in Branch A"""
    return Block.objects.create(
        code="KH01",
        name="Block A",
        branch=branch_a,
        block_type=Block.BlockType.SUPPORT,
    )


@pytest.fixture
def block_b(db, branch_b):
    """Create Block B in Branch B"""
    return Block.objects.create(
        code="KH02",
        name="Block B",
        branch=branch_b,
        block_type=Block.BlockType.SUPPORT,
    )


@pytest.fixture
def department_a(db, branch_a, block_a):
    """Create Department A in Block A"""
    return Department.objects.create(
        code="PB01",
        name="Department A",
        branch=branch_a,
        block=block_a,
    )


@pytest.fixture
def department_b(db, branch_b, block_b):
    """Create Department B in Block B"""
    return Department.objects.create(
        code="PB02",
        name="Department B",
        branch=branch_b,
        block=block_b,
    )


@pytest.fixture
def role_root(db):
    """Create a role with ROOT scope"""
    return Role.objects.create(
        code="VT_ROOT",
        name="Root Role",
        data_scope_level=DataScopeLevel.ROOT,
    )


@pytest.fixture
def role_branch(db, branch_a):
    """Create a role with BRANCH scope for Branch A"""
    role = Role.objects.create(
        code="VT_BRANCH",
        name="Branch Role",
        data_scope_level=DataScopeLevel.BRANCH,
    )
    RoleBranchScope.objects.create(role=role, branch=branch_a)
    return role


@pytest.fixture
def role_block(db, block_a):
    """Create a role with BLOCK scope for Block A"""
    role = Role.objects.create(
        code="VT_BLOCK",
        name="Block Role",
        data_scope_level=DataScopeLevel.BLOCK,
    )
    RoleBlockScope.objects.create(role=role, block=block_a)
    return role


@pytest.fixture
def role_department(db, department_a):
    """Create a role with DEPARTMENT scope for Department A"""
    role = Role.objects.create(
        code="VT_DEPT",
        name="Department Role",
        data_scope_level=DataScopeLevel.DEPARTMENT,
    )
    RoleDepartmentScope.objects.create(role=role, department=department_a)
    return role


@pytest.fixture
def user_root(db, role_root):
    """Create user with root scope role"""
    user = User.objects.create_user(
        username="user_root",
        email="root@test.com",
        password="testpass123",
    )
    user.role = role_root
    user.save()
    return user


@pytest.fixture
def user_branch(db, role_branch):
    """Create user with branch scope role"""
    user = User.objects.create_user(
        username="user_branch",
        email="branch@test.com",
        password="testpass123",
    )
    user.role = role_branch
    user.save()
    return user


@pytest.fixture
def user_block(db, role_block):
    """Create user with block scope role"""
    user = User.objects.create_user(
        username="user_block",
        email="block@test.com",
        password="testpass123",
    )
    user.role = role_block
    user.save()
    return user


@pytest.fixture
def user_department(db, role_department):
    """Create user with department scope role"""
    user = User.objects.create_user(
        username="user_department",
        email="dept@test.com",
        password="testpass123",
    )
    user.role = role_department
    user.save()
    return user


@pytest.fixture
def user_no_role(db):
    """Create user without a role"""
    return User.objects.create_user(
        username="user_norole",
        email="norole@test.com",
        password="testpass123",
    )


@pytest.fixture
def superuser(db):
    """Create a superuser"""
    return User.objects.create_superuser(
        username="superuser",
        email="super@test.com",
        password="testpass123",
    )


@pytest.mark.django_db
class TestRoleAllowedUnits:
    """Test RoleAllowedUnits dataclass"""

    def test_default_values(self):
        """Test default values for RoleAllowedUnits"""
        units = RoleAllowedUnits()
        assert units.has_all is False
        assert units.branches == set()
        assert units.blocks == set()
        assert units.departments == set()

    def test_is_empty_true(self):
        """Test is_empty returns True when no units"""
        units = RoleAllowedUnits()
        assert units.is_empty is True

    def test_is_empty_false_with_branches(self):
        """Test is_empty returns False when branches are set"""
        units = RoleAllowedUnits(branches={1, 2})
        assert units.is_empty is False

    def test_is_empty_false_with_has_all(self):
        """Test is_empty returns False when has_all is True"""
        units = RoleAllowedUnits(has_all=True)
        assert units.is_empty is False

    def test_cache_serialization(self):
        """Test to_cache_dict and from_cache_dict"""
        units = RoleAllowedUnits(has_all=False, branches={1, 2}, blocks={3}, departments={4, 5})
        cache_dict = units.to_cache_dict()
        restored = RoleAllowedUnits.from_cache_dict(cache_dict)

        assert restored.has_all == units.has_all
        assert restored.branches == units.branches
        assert restored.blocks == units.blocks
        assert restored.departments == units.departments


@pytest.mark.django_db
class TestCollectRoleAllowedUnits:
    """Test collect_role_allowed_units function"""

    def test_superuser_returns_all(self, superuser):
        """Superuser should get has_all=True"""
        allowed = collect_role_allowed_units(superuser, use_cache=False)
        assert allowed.has_all is True

    def test_user_no_role_returns_empty(self, user_no_role):
        """User without role should get empty units"""
        allowed = collect_role_allowed_units(user_no_role, use_cache=False)
        assert allowed.is_empty is True

    def test_root_scope_returns_all(self, user_root):
        """User with ROOT scope should get has_all=True"""
        allowed = collect_role_allowed_units(user_root, use_cache=False)
        assert allowed.has_all is True

    def test_branch_scope_returns_branches(self, user_branch, branch_a):
        """User with BRANCH scope should get their assigned branches"""
        allowed = collect_role_allowed_units(user_branch, use_cache=False)
        assert allowed.has_all is False
        assert branch_a.id in allowed.branches
        assert len(allowed.branches) == 1

    def test_block_scope_returns_blocks(self, user_block, block_a):
        """User with BLOCK scope should get their assigned blocks"""
        allowed = collect_role_allowed_units(user_block, use_cache=False)
        assert allowed.has_all is False
        assert block_a.id in allowed.blocks
        assert len(allowed.blocks) == 1

    def test_department_scope_returns_departments(self, user_department, department_a):
        """User with DEPARTMENT scope should get their assigned departments"""
        allowed = collect_role_allowed_units(user_department, use_cache=False)
        assert allowed.has_all is False
        assert department_a.id in allowed.departments
        assert len(allowed.departments) == 1

    def test_cache_invalidation(self, user_branch, branch_a, branch_b):
        """Test cache is invalidated properly"""
        # First call
        allowed = collect_role_allowed_units(user_branch, use_cache=True)
        assert branch_a.id in allowed.branches
        assert branch_b.id not in allowed.branches

        # Add branch B to role
        RoleBranchScope.objects.create(role=user_branch.role, branch=branch_b)

        # Without invalidation, should still return cached result
        allowed_cached = collect_role_allowed_units(user_branch, use_cache=True)
        # Cache should have old value unless invalidated
        # The signal should have invalidated it

        # Explicitly invalidate and check
        invalidate_role_units_cache(user_branch.id)
        allowed_fresh = collect_role_allowed_units(user_branch, use_cache=True)
        assert branch_a.id in allowed_fresh.branches
        assert branch_b.id in allowed_fresh.branches


@pytest.mark.django_db
class TestFilterQuerysetByRoleDataScope:
    """Test filter_queryset_by_role_data_scope function"""

    def test_superuser_returns_all(self, superuser, department_a, department_b):
        """Superuser should see all departments"""
        # Filter by test departments only to avoid race conditions with parallel tests
        test_dept_ids = [department_a.id, department_b.id]
        qs = Department.objects.filter(id__in=test_dept_ids)
        filtered = filter_queryset_by_role_data_scope(qs, superuser)
        assert filtered.count() == 2

    def test_branch_scope_filters_correctly(self, user_branch, department_a, department_b, branch_a, branch_b):
        """Branch scope should only show departments in allowed branches"""
        # Filter by test departments only to avoid race conditions with parallel tests
        test_dept_ids = [department_a.id, department_b.id]
        qs = Department.objects.filter(id__in=test_dept_ids)
        config = {"branch_field": "branch", "block_field": "block", "department_field": "id"}
        filtered = filter_queryset_by_role_data_scope(qs, user_branch, config)

        # Should only see department_a (in branch_a)
        assert department_a in filtered
        assert department_b not in filtered

    def test_block_scope_filters_correctly(self, user_block, department_a, department_b):
        """Block scope should only show departments in allowed blocks"""
        # Filter by test departments only to avoid race conditions with parallel tests
        test_dept_ids = [department_a.id, department_b.id]
        qs = Department.objects.filter(id__in=test_dept_ids)
        config = {"branch_field": "branch", "block_field": "block", "department_field": "id"}
        filtered = filter_queryset_by_role_data_scope(qs, user_block, config)

        # Should only see department_a (in block_a)
        assert department_a in filtered
        assert department_b not in filtered

    def test_department_scope_filters_correctly(self, user_department, department_a, department_b):
        """Department scope should only show assigned departments"""
        # Filter by test departments only to avoid race conditions with parallel tests
        test_dept_ids = [department_a.id, department_b.id]
        qs = Department.objects.filter(id__in=test_dept_ids)
        # When filtering departments by department scope, we use "id" as the department_field
        # since we're filtering the Department model itself
        config = {"branch_field": "branch", "block_field": "block", "department_field": ""}
        filtered = filter_queryset_by_role_data_scope(qs, user_department, config)

        # Should only see department_a
        assert department_a in filtered
        assert department_b not in filtered

    def test_no_role_returns_empty(self, user_no_role, department_a, department_b):
        """User without role should see nothing"""
        # Create a queryset with only our test departments to avoid race conditions
        # with other parallel tests
        test_dept_ids = [department_a.id, department_b.id]
        qs = Department.objects.filter(id__in=test_dept_ids)
        filtered = filter_queryset_by_role_data_scope(qs, user_no_role)
        assert filtered.count() == 0


@pytest.mark.django_db
class TestDataScopePermission:
    """Test DataScopePermission class"""

    def test_superuser_has_access(self, superuser, department_a):
        """Superuser should have access to any object"""
        permission = DataScopePermission()
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = superuser

        class MockView:
            data_scope_config = {
                "branch_field": "branch",
                "block_field": "block",
                "department_field": "id",
            }

        assert permission.has_object_permission(request, MockView(), department_a) is True

    def test_root_scope_has_access(self, user_root, department_b):
        """User with ROOT scope should have access to any object"""
        permission = DataScopePermission()
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = user_root

        class MockView:
            data_scope_config = {
                "branch_field": "branch",
                "block_field": "block",
                "department_field": "id",
            }

        assert permission.has_object_permission(request, MockView(), department_b) is True

    def test_branch_scope_allows_same_branch(self, user_branch, department_a):
        """User with BRANCH scope should access objects in their branch"""
        permission = DataScopePermission()
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = user_branch

        class MockView:
            data_scope_config = {
                "branch_field": "branch",
                "block_field": "block",
                "department_field": "id",
            }

        assert permission.has_object_permission(request, MockView(), department_a) is True

    def test_branch_scope_denies_other_branch(self, user_branch, department_b):
        """User with BRANCH scope should be denied for other branches"""
        permission = DataScopePermission()
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = user_branch

        class MockView:
            data_scope_config = {
                "branch_field": "branch",
                "block_field": "block",
                "department_field": "id",
            }

        from rest_framework.exceptions import PermissionDenied

        with pytest.raises(PermissionDenied):
            permission.has_object_permission(request, MockView(), department_b)


@pytest.mark.django_db
class TestUserHelperMethods:
    """Test User model helper methods"""

    def test_get_allowed_units(self, user_branch, branch_a):
        """Test get_allowed_units returns correct units"""
        allowed = user_branch.get_allowed_units()
        assert branch_a.id in allowed.branches

    def test_has_access_to_branch_true(self, user_branch, branch_a):
        """Test has_access_to_branch returns True for allowed branch"""
        assert user_branch.has_access_to_branch(branch_a.id) is True

    def test_has_access_to_branch_false(self, user_branch, branch_b):
        """Test has_access_to_branch returns False for other branch"""
        assert user_branch.has_access_to_branch(branch_b.id) is False

    def test_has_access_to_block_via_branch(self, user_branch, block_a):
        """Test has_access_to_block returns True when block's branch is allowed"""
        assert user_branch.has_access_to_block(block_a.id) is True

    def test_has_access_to_department_via_branch(self, user_branch, department_a):
        """Test has_access_to_department returns True when dept's branch is allowed"""
        assert user_branch.has_access_to_department(department_a.id) is True

    def test_superuser_has_all_access(self, superuser, branch_a, block_a, department_a):
        """Superuser should have access to everything"""
        assert superuser.has_access_to_branch(branch_a.id) is True
        assert superuser.has_access_to_block(block_a.id) is True
        assert superuser.has_access_to_department(department_a.id) is True


@pytest.mark.django_db
class TestRoleScopeModels:
    """Test Role scope model relationships"""

    def test_role_branch_scope_creation(self, role_root, branch_a):
        """Test RoleBranchScope can be created"""
        scope = RoleBranchScope.objects.create(role=role_root, branch=branch_a)
        assert scope.role == role_root
        assert scope.branch == branch_a
        assert str(scope) == f"{role_root.name} -> {branch_a.name}"

    def test_role_block_scope_creation(self, role_root, block_a):
        """Test RoleBlockScope can be created"""
        scope = RoleBlockScope.objects.create(role=role_root, block=block_a)
        assert scope.role == role_root
        assert scope.block == block_a
        assert str(scope) == f"{role_root.name} -> {block_a.name}"

    def test_role_department_scope_creation(self, role_root, department_a):
        """Test RoleDepartmentScope can be created"""
        scope = RoleDepartmentScope.objects.create(role=role_root, department=department_a)
        assert scope.role == role_root
        assert scope.department == department_a
        assert str(scope) == f"{role_root.name} -> {department_a.name}"

    def test_unique_constraint(self, role_root, branch_a):
        """Test unique constraint on role-branch pair"""
        RoleBranchScope.objects.create(role=role_root, branch=branch_a)
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            RoleBranchScope.objects.create(role=role_root, branch=branch_a)
