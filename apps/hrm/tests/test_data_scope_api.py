"""
Integration tests for Data Scope API filtering and create validation.

Tests the role-based data scope system at the API level for:
- List filtering (RoleDataScopeFilterBackend)
- Object-level permissions (DataScopePermission)
- Create validation (DataScopeCreateValidationMixin)
"""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import AdministrativeUnit, Permission, Province, Role
from apps.core.models.role import DataScopeLevel
from apps.hrm.models import (
    Block,
    Branch,
    Department,
    Employee,
    JobDescription,
    Position,
    RecruitmentRequest,
)
from apps.hrm.models.role_data_scope import RoleBlockScope, RoleBranchScope, RoleDepartmentScope

User = get_user_model()


# ==============================================================================
# Fixtures - Permissions
# ==============================================================================


@pytest.fixture
def recruitment_request_permissions(db):
    """Create all permissions needed for RecruitmentRequest API"""
    permissions = []
    actions = ["list", "retrieve", "create", "update", "partial_update", "destroy"]
    for action in actions:
        perm, _ = Permission.objects.get_or_create(
            code=f"recruitment_request.{action}",
            defaults={
                "name": f"Recruitment Request {action.title()}",
                "description": f"Can {action} recruitment requests",
                "module": "HRM",
                "submodule": "Recruitment Request",
            },
        )
        permissions.append(perm)
    return permissions


# ==============================================================================
# Fixtures - Organizational Structure
# ==============================================================================


@pytest.fixture
def province_ds(db):
    """Create a province for data scope tests"""
    return Province.objects.create(code="DS01", name="Data Scope Province")


@pytest.fixture
def admin_unit_ds(db, province_ds):
    """Create an administrative unit for data scope tests"""
    return AdministrativeUnit.objects.create(
        code="AUDS01",
        name="Data Scope Admin Unit",
        parent_province=province_ds,
        level=AdministrativeUnit.UnitLevel.DISTRICT,
    )


@pytest.fixture
def branch_alpha(db, province_ds, admin_unit_ds):
    """Create Branch Alpha for testing"""
    return Branch.objects.create(
        code="CNALPHA",
        name="Branch Alpha",
        province=province_ds,
        administrative_unit=admin_unit_ds,
    )


@pytest.fixture
def branch_beta(db, province_ds, admin_unit_ds):
    """Create Branch Beta for testing"""
    return Branch.objects.create(
        code="CNBETA",
        name="Branch Beta",
        province=province_ds,
        administrative_unit=admin_unit_ds,
    )


@pytest.fixture
def block_alpha(db, branch_alpha):
    """Create Block Alpha in Branch Alpha"""
    return Block.objects.create(
        code="KHALPHA",
        name="Block Alpha",
        branch=branch_alpha,
        block_type=Block.BlockType.SUPPORT,
    )


@pytest.fixture
def block_beta(db, branch_beta):
    """Create Block Beta in Branch Beta"""
    return Block.objects.create(
        code="KHBETA",
        name="Block Beta",
        branch=branch_beta,
        block_type=Block.BlockType.SUPPORT,
    )


@pytest.fixture
def department_alpha(db, branch_alpha, block_alpha):
    """Create Department Alpha in Block Alpha"""
    return Department.objects.create(
        code="PBALPHA",
        name="Department Alpha",
        branch=branch_alpha,
        block=block_alpha,
    )


@pytest.fixture
def department_beta(db, branch_beta, block_beta):
    """Create Department Beta in Block Beta"""
    return Department.objects.create(
        code="PBBETA",
        name="Department Beta",
        branch=branch_beta,
        block=block_beta,
    )


@pytest.fixture
def position_ds(db):
    """Create a position for data scope tests"""
    return Position.objects.create(name="Test Position DS", code="CVDS01")


@pytest.fixture
def job_description_ds(db):
    """Create a job description for testing"""
    return JobDescription.objects.create(
        title="Data Scope Test Developer",
        position_title="Developer",
        responsibility="Test responsibilities",
        requirement="Test requirements",
        benefit="Test benefits",
        proposed_salary="1000-2000 USD",
    )


# ==============================================================================
# Fixtures - Users and Roles
# ==============================================================================


@pytest.fixture
def role_root_ds(db, recruitment_request_permissions):
    """Create a role with ROOT scope"""
    role = Role.objects.create(
        code="VT_ROOT_DS",
        name="Root Role DS",
        data_scope_level=DataScopeLevel.ROOT,
    )
    role.permissions.set(recruitment_request_permissions)
    return role


@pytest.fixture
def role_branch_alpha(db, branch_alpha, recruitment_request_permissions):
    """Create a role with BRANCH scope for Branch Alpha"""
    role = Role.objects.create(
        code="VT_BRANCH_ALPHA",
        name="Branch Alpha Role",
        data_scope_level=DataScopeLevel.BRANCH,
    )
    role.permissions.set(recruitment_request_permissions)
    RoleBranchScope.objects.create(role=role, branch=branch_alpha)
    return role


@pytest.fixture
def role_branch_beta(db, branch_beta, recruitment_request_permissions):
    """Create a role with BRANCH scope for Branch Beta"""
    role = Role.objects.create(
        code="VT_BRANCH_BETA",
        name="Branch Beta Role",
        data_scope_level=DataScopeLevel.BRANCH,
    )
    role.permissions.set(recruitment_request_permissions)
    RoleBranchScope.objects.create(role=role, branch=branch_beta)
    return role


@pytest.fixture
def role_block_alpha(db, block_alpha, recruitment_request_permissions):
    """Create a role with BLOCK scope for Block Alpha"""
    role = Role.objects.create(
        code="VT_BLOCK_ALPHA",
        name="Block Alpha Role",
        data_scope_level=DataScopeLevel.BLOCK,
    )
    role.permissions.set(recruitment_request_permissions)
    RoleBlockScope.objects.create(role=role, block=block_alpha)
    return role


@pytest.fixture
def role_department_alpha(db, department_alpha, recruitment_request_permissions):
    """Create a role with DEPARTMENT scope for Department Alpha"""
    role = Role.objects.create(
        code="VT_DEPT_ALPHA",
        name="Department Alpha Role",
        data_scope_level=DataScopeLevel.DEPARTMENT,
    )
    role.permissions.set(recruitment_request_permissions)
    RoleDepartmentScope.objects.create(role=role, department=department_alpha)
    return role


@pytest.fixture
def role_no_permissions(db):
    """Create a role without any permissions"""
    return Role.objects.create(
        code="VT_NO_PERMS",
        name="No Permissions Role",
        data_scope_level=DataScopeLevel.ROOT,
    )


@pytest.fixture
def user_root_ds(db, role_root_ds):
    """Create user with ROOT scope"""
    user = User.objects.create_user(
        username="user_root_ds",
        email="root_ds@test.com",
        password="testpass123",
    )
    user.role = role_root_ds
    user.save()
    return user


@pytest.fixture
def user_branch_alpha(db, role_branch_alpha):
    """Create user with BRANCH scope for Branch Alpha"""
    user = User.objects.create_user(
        username="user_branch_alpha",
        email="branch_alpha@test.com",
        password="testpass123",
    )
    user.role = role_branch_alpha
    user.save()
    return user


@pytest.fixture
def user_branch_beta(db, role_branch_beta):
    """Create user with BRANCH scope for Branch Beta"""
    user = User.objects.create_user(
        username="user_branch_beta",
        email="branch_beta@test.com",
        password="testpass123",
    )
    user.role = role_branch_beta
    user.save()
    return user


@pytest.fixture
def user_block_alpha(db, role_block_alpha):
    """Create user with BLOCK scope for Block Alpha"""
    user = User.objects.create_user(
        username="user_block_alpha",
        email="block_alpha@test.com",
        password="testpass123",
    )
    user.role = role_block_alpha
    user.save()
    return user


@pytest.fixture
def user_department_alpha(db, role_department_alpha):
    """Create user with DEPARTMENT scope for Department Alpha"""
    user = User.objects.create_user(
        username="user_dept_alpha",
        email="dept_alpha@test.com",
        password="testpass123",
    )
    user.role = role_department_alpha
    user.save()
    return user


@pytest.fixture
def user_no_role_ds(db):
    """Create user without any role"""
    return User.objects.create_user(
        username="user_no_role_ds",
        email="norole_ds@test.com",
        password="testpass123",
    )


@pytest.fixture
def superuser_ds(db):
    """Create superuser for data scope tests"""
    return User.objects.create_superuser(
        username="superuser_ds",
        email="super_ds@test.com",
        password="testpass123",
    )


# ==============================================================================
# Fixtures - Employees for Testing
# ==============================================================================


@pytest.fixture
def employee_alpha(db, branch_alpha, block_alpha, department_alpha, position_ds, user_branch_alpha):
    """Create employee in Branch Alpha org structure"""
    return Employee.objects.create(
        user=user_branch_alpha,
        code="MVALPHA01",
        fullname="Employee Alpha",
        username="emp_alpha",
        email="emp_alpha@test.com",
        personal_email="emp_alpha_personal@test.com",
        phone="0111111111",
        attendance_code="11111",
        start_date="2024-01-01",
        branch=branch_alpha,
        block=block_alpha,
        department=department_alpha,
        position=position_ds,
        citizen_id="111111111111",
    )


@pytest.fixture
def employee_beta(db, branch_beta, block_beta, department_beta, position_ds, user_branch_beta):
    """Create employee in Branch Beta org structure"""
    return Employee.objects.create(
        user=user_branch_beta,
        code="MVBETA01",
        fullname="Employee Beta",
        username="emp_beta",
        email="emp_beta@test.com",
        personal_email="emp_beta_personal@test.com",
        phone="0222222222",
        attendance_code="22222",
        start_date="2024-01-01",
        branch=branch_beta,
        block=block_beta,
        department=department_beta,
        position=position_ds,
        citizen_id="222222222222",
    )


# ==============================================================================
# Fixtures - Test Data
# ==============================================================================


@pytest.fixture
def recruitment_request_alpha(db, job_description_ds, department_alpha, employee_alpha):
    """Create recruitment request in Branch Alpha"""
    return RecruitmentRequest.objects.create(
        name="Alpha Developer Position",
        job_description=job_description_ds,
        branch=department_alpha.branch,
        block=department_alpha.block,
        department=department_alpha,
        proposer=employee_alpha,
        recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
        status=RecruitmentRequest.Status.OPEN,
        proposed_salary="2000-3000 USD",
        number_of_positions=2,
    )


@pytest.fixture
def recruitment_request_beta(db, job_description_ds, department_beta, employee_beta):
    """Create recruitment request in Branch Beta"""
    return RecruitmentRequest.objects.create(
        name="Beta Developer Position",
        job_description=job_description_ds,
        branch=department_beta.branch,
        block=department_beta.block,
        department=department_beta,
        proposer=employee_beta,
        recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
        status=RecruitmentRequest.Status.OPEN,
        proposed_salary="2000-3000 USD",
        number_of_positions=1,
    )


# ==============================================================================
# API Client Fixtures
# ==============================================================================


@pytest.fixture
def api_client_root(user_root_ds):
    """API client authenticated as ROOT user"""
    client = APIClient()
    client.force_authenticate(user=user_root_ds)
    return client


@pytest.fixture
def api_client_branch_alpha(user_branch_alpha):
    """API client authenticated as Branch Alpha user"""
    client = APIClient()
    client.force_authenticate(user=user_branch_alpha)
    return client


@pytest.fixture
def api_client_branch_beta(user_branch_beta):
    """API client authenticated as Branch Beta user"""
    client = APIClient()
    client.force_authenticate(user=user_branch_beta)
    return client


@pytest.fixture
def api_client_block_alpha(user_block_alpha):
    """API client authenticated as Block Alpha user"""
    client = APIClient()
    client.force_authenticate(user=user_block_alpha)
    return client


@pytest.fixture
def api_client_department_alpha(user_department_alpha):
    """API client authenticated as Department Alpha user"""
    client = APIClient()
    client.force_authenticate(user=user_department_alpha)
    return client


@pytest.fixture
def api_client_no_role(user_no_role_ds):
    """API client authenticated as user without role"""
    client = APIClient()
    client.force_authenticate(user=user_no_role_ds)
    return client


@pytest.fixture
def api_client_superuser(superuser_ds):
    """API client authenticated as superuser"""
    client = APIClient()
    client.force_authenticate(user=superuser_ds)
    return client


# ==============================================================================
# Helper Functions
# ==============================================================================


def get_response_data(response):
    """Extract data from wrapped API response"""
    content = response.json()
    if "data" in content:
        data = content["data"]
        if isinstance(data, dict) and "results" in data:
            return data["results"]
        return data
    return content


def get_response_count(response):
    """Get count from paginated response"""
    content = response.json()
    if "data" in content and isinstance(content["data"], dict):
        return content["data"].get("count", len(content["data"].get("results", [])))
    return 0


# ==============================================================================
# Test Classes - RecruitmentRequest List Filtering
# ==============================================================================


@pytest.mark.django_db
class TestRecruitmentRequestListFiltering:
    """Test data scope filtering on list endpoint"""

    def test_root_user_sees_all_requests(self, api_client_root, recruitment_request_alpha, recruitment_request_beta):
        """ROOT scope user should see all recruitment requests"""
        url = reverse("hrm:recruitment-request-list")
        response = api_client_root.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = get_response_data(response)
        assert len(data) == 2
        request_names = [r["name"] for r in data]
        assert "Alpha Developer Position" in request_names
        assert "Beta Developer Position" in request_names

    def test_superuser_sees_all_requests(
        self, api_client_superuser, recruitment_request_alpha, recruitment_request_beta
    ):
        """Superuser should see all recruitment requests"""
        url = reverse("hrm:recruitment-request-list")
        response = api_client_superuser.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = get_response_data(response)
        assert len(data) == 2

    def test_branch_user_sees_only_own_branch(
        self, api_client_branch_alpha, recruitment_request_alpha, recruitment_request_beta
    ):
        """BRANCH scope user should only see requests in their branch"""
        url = reverse("hrm:recruitment-request-list")
        response = api_client_branch_alpha.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = get_response_data(response)
        assert len(data) == 1
        assert data[0]["name"] == "Alpha Developer Position"

    def test_branch_beta_user_sees_only_own_branch(
        self, api_client_branch_beta, recruitment_request_alpha, recruitment_request_beta
    ):
        """BRANCH scope user (Beta) should only see requests in their branch"""
        url = reverse("hrm:recruitment-request-list")
        response = api_client_branch_beta.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = get_response_data(response)
        assert len(data) == 1
        assert data[0]["name"] == "Beta Developer Position"

    def test_block_user_sees_only_own_block(
        self, api_client_block_alpha, recruitment_request_alpha, recruitment_request_beta
    ):
        """BLOCK scope user should only see requests in their block"""
        url = reverse("hrm:recruitment-request-list")
        response = api_client_block_alpha.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = get_response_data(response)
        assert len(data) == 1
        assert data[0]["name"] == "Alpha Developer Position"

    def test_department_user_sees_only_own_department(
        self, api_client_department_alpha, recruitment_request_alpha, recruitment_request_beta
    ):
        """DEPARTMENT scope user should only see requests in their department"""
        url = reverse("hrm:recruitment-request-list")
        response = api_client_department_alpha.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = get_response_data(response)
        assert len(data) == 1
        assert data[0]["name"] == "Alpha Developer Position"

    def test_no_role_user_is_denied_access(
        self, api_client_no_role, recruitment_request_alpha, recruitment_request_beta
    ):
        """User without role should be denied by RoleBasedPermission"""
        url = reverse("hrm:recruitment-request-list")
        response = api_client_no_role.get(url)

        # User without role is denied by RoleBasedPermission before data scope filtering
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ==============================================================================
# Test Classes - RecruitmentRequest Retrieve Permissions
# ==============================================================================


@pytest.mark.django_db
class TestRecruitmentRequestRetrievePermission:
    """Test data scope object-level permissions on retrieve endpoint"""

    def test_root_user_can_retrieve_any_request(
        self, api_client_root, recruitment_request_alpha, recruitment_request_beta
    ):
        """ROOT scope user should retrieve any request"""
        url = reverse("hrm:recruitment-request-detail", kwargs={"pk": recruitment_request_beta.id})
        response = api_client_root.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = get_response_data(response)
        assert data["name"] == "Beta Developer Position"

    def test_branch_user_can_retrieve_own_branch_request(self, api_client_branch_alpha, recruitment_request_alpha):
        """BRANCH scope user should retrieve request in their branch"""
        url = reverse("hrm:recruitment-request-detail", kwargs={"pk": recruitment_request_alpha.id})
        response = api_client_branch_alpha.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = get_response_data(response)
        assert data["name"] == "Alpha Developer Position"

    def test_branch_user_cannot_retrieve_other_branch_request(self, api_client_branch_alpha, recruitment_request_beta):
        """BRANCH scope user should NOT retrieve request in other branch

        Note: Returns 404 because the object is filtered out by RoleDataScopeFilterBackend
        before the object-level permission check (get_object uses get_queryset).
        """
        url = reverse("hrm:recruitment-request-detail", kwargs={"pk": recruitment_request_beta.id})
        response = api_client_branch_alpha.get(url)

        # Object is filtered out, so it appears as "not found" rather than "forbidden"
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_block_user_cannot_retrieve_other_block_request(self, api_client_block_alpha, recruitment_request_beta):
        """BLOCK scope user should NOT retrieve request in other block"""
        url = reverse("hrm:recruitment-request-detail", kwargs={"pk": recruitment_request_beta.id})
        response = api_client_block_alpha.get(url)

        # Object is filtered out, so it appears as "not found" rather than "forbidden"
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ==============================================================================
# Test Classes - RecruitmentRequest Create Validation
# ==============================================================================


@pytest.mark.django_db
class TestRecruitmentRequestCreateValidation:
    """Test DataScopeCreateValidationMixin on create endpoint"""

    def test_root_user_can_create_in_any_branch(
        self, api_client_root, job_description_ds, department_beta, employee_beta
    ):
        """ROOT scope user should create request in any branch"""
        url = reverse("hrm:recruitment-request-list")
        data = {
            "name": "Root Created Request",
            "job_description_id": job_description_ds.id,
            "department_id": department_beta.id,
            "proposer_id": employee_beta.id,
            "recruitment_type": "NEW_HIRE",
            "proposed_salary": "1000-2000 USD",
        }
        response = api_client_root.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        response_data = get_response_data(response)
        assert response_data["name"] == "Root Created Request"

    def test_superuser_can_create_in_any_branch(
        self, api_client_superuser, job_description_ds, department_beta, employee_beta
    ):
        """Superuser should create request in any branch"""
        url = reverse("hrm:recruitment-request-list")
        data = {
            "name": "Superuser Created Request",
            "job_description_id": job_description_ds.id,
            "department_id": department_beta.id,
            "proposer_id": employee_beta.id,
            "recruitment_type": "NEW_HIRE",
            "proposed_salary": "1000-2000 USD",
        }
        response = api_client_superuser.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED

    def test_branch_user_can_create_in_own_branch(
        self, api_client_branch_alpha, job_description_ds, department_alpha, employee_alpha
    ):
        """BRANCH scope user should create request in their branch"""
        url = reverse("hrm:recruitment-request-list")
        data = {
            "name": "Branch Alpha Created Request",
            "job_description_id": job_description_ds.id,
            "department_id": department_alpha.id,
            "proposer_id": employee_alpha.id,
            "recruitment_type": "NEW_HIRE",
            "proposed_salary": "1000-2000 USD",
        }
        response = api_client_branch_alpha.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        response_data = get_response_data(response)
        assert response_data["name"] == "Branch Alpha Created Request"

    def test_branch_user_cannot_create_in_other_branch(
        self, api_client_branch_alpha, job_description_ds, department_beta, employee_beta
    ):
        """BRANCH scope user should NOT create request in other branch"""
        url = reverse("hrm:recruitment-request-list")
        data = {
            "name": "Should Fail",
            "job_description_id": job_description_ds.id,
            "department_id": department_beta.id,
            "proposer_id": employee_beta.id,
            "recruitment_type": "NEW_HIRE",
            "proposed_salary": "1000-2000 USD",
        }
        response = api_client_branch_alpha.post(url, data, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_block_user_can_create_in_own_block(
        self, api_client_block_alpha, job_description_ds, department_alpha, employee_alpha
    ):
        """BLOCK scope user should create request in their block"""
        url = reverse("hrm:recruitment-request-list")
        data = {
            "name": "Block Alpha Created Request",
            "job_description_id": job_description_ds.id,
            "department_id": department_alpha.id,
            "proposer_id": employee_alpha.id,
            "recruitment_type": "NEW_HIRE",
            "proposed_salary": "1000-2000 USD",
        }
        response = api_client_block_alpha.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED

    def test_block_user_cannot_create_in_other_block(
        self, api_client_block_alpha, job_description_ds, department_beta, employee_beta
    ):
        """BLOCK scope user should NOT create request in other block"""
        url = reverse("hrm:recruitment-request-list")
        data = {
            "name": "Should Fail",
            "job_description_id": job_description_ds.id,
            "department_id": department_beta.id,
            "proposer_id": employee_beta.id,
            "recruitment_type": "NEW_HIRE",
            "proposed_salary": "1000-2000 USD",
        }
        response = api_client_block_alpha.post(url, data, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_department_user_can_create_in_own_department(
        self, api_client_department_alpha, job_description_ds, department_alpha, employee_alpha
    ):
        """DEPARTMENT scope user should create request in their department"""
        url = reverse("hrm:recruitment-request-list")
        data = {
            "name": "Department Alpha Created Request",
            "job_description_id": job_description_ds.id,
            "department_id": department_alpha.id,
            "proposer_id": employee_alpha.id,
            "recruitment_type": "NEW_HIRE",
            "proposed_salary": "1000-2000 USD",
        }
        response = api_client_department_alpha.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED

    def test_department_user_cannot_create_in_other_department(
        self, api_client_department_alpha, job_description_ds, department_beta, employee_beta
    ):
        """DEPARTMENT scope user should NOT create request in other department"""
        url = reverse("hrm:recruitment-request-list")
        data = {
            "name": "Should Fail",
            "job_description_id": job_description_ds.id,
            "department_id": department_beta.id,
            "proposer_id": employee_beta.id,
            "recruitment_type": "NEW_HIRE",
            "proposed_salary": "1000-2000 USD",
        }
        response = api_client_department_alpha.post(url, data, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_no_role_user_cannot_create(
        self, api_client_no_role, job_description_ds, department_alpha, employee_alpha
    ):
        """User without role should NOT create any request"""
        url = reverse("hrm:recruitment-request-list")
        data = {
            "name": "Should Fail",
            "job_description_id": job_description_ds.id,
            "department_id": department_alpha.id,
            "proposer_id": employee_alpha.id,
            "recruitment_type": "NEW_HIRE",
            "proposed_salary": "1000-2000 USD",
        }
        response = api_client_no_role.post(url, data, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN


# ==============================================================================
# Test Classes - RecruitmentRequest Update Permissions
# ==============================================================================


@pytest.mark.django_db
class TestRecruitmentRequestUpdatePermission:
    """Test data scope permissions on update endpoint"""

    def test_branch_user_can_update_own_branch_request(
        self, api_client_branch_alpha, recruitment_request_alpha, job_description_ds, department_alpha, employee_alpha
    ):
        """BRANCH scope user should update request in their branch"""
        url = reverse("hrm:recruitment-request-detail", kwargs={"pk": recruitment_request_alpha.id})
        data = {
            "name": "Updated Alpha Request",
            "job_description_id": job_description_ds.id,
            "department_id": department_alpha.id,
            "proposer_id": employee_alpha.id,
            "recruitment_type": "NEW_HIRE",
            "proposed_salary": "3000-4000 USD",
        }
        response = api_client_branch_alpha.put(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        response_data = get_response_data(response)
        assert response_data["name"] == "Updated Alpha Request"

    def test_branch_user_cannot_update_other_branch_request(
        self, api_client_branch_alpha, recruitment_request_beta, job_description_ds, department_beta, employee_beta
    ):
        """BRANCH scope user should NOT update request in other branch"""
        url = reverse("hrm:recruitment-request-detail", kwargs={"pk": recruitment_request_beta.id})
        data = {
            "name": "Should Fail Update",
            "job_description_id": job_description_ds.id,
            "department_id": department_beta.id,
            "proposer_id": employee_beta.id,
            "recruitment_type": "NEW_HIRE",
            "proposed_salary": "3000-4000 USD",
        }
        response = api_client_branch_alpha.put(url, data, format="json")

        # Object is filtered out, so it appears as "not found" rather than "forbidden"
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ==============================================================================
# Test Classes - RecruitmentRequest Delete Permissions
# ==============================================================================


@pytest.mark.django_db
class TestRecruitmentRequestDeletePermission:
    """Test data scope permissions on delete endpoint"""

    def test_branch_user_can_delete_own_branch_request(
        self, api_client_branch_alpha, job_description_ds, department_alpha, employee_alpha
    ):
        """BRANCH scope user should delete request in their branch"""
        # Create a fresh request without related objects for clean deletion
        request = RecruitmentRequest.objects.create(
            name="Deletable Request",
            job_description=job_description_ds,
            branch=department_alpha.branch,
            block=department_alpha.block,
            department=department_alpha,
            proposer=employee_alpha,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            status=RecruitmentRequest.Status.DRAFT,
            proposed_salary="1000-2000 USD",
            number_of_positions=1,
        )
        url = reverse("hrm:recruitment-request-detail", kwargs={"pk": request.id})
        response = api_client_branch_alpha.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not RecruitmentRequest.objects.filter(id=request.id).exists()

    def test_branch_user_cannot_delete_other_branch_request(self, api_client_branch_alpha, recruitment_request_beta):
        """BRANCH scope user should NOT delete request in other branch"""
        url = reverse("hrm:recruitment-request-detail", kwargs={"pk": recruitment_request_beta.id})
        response = api_client_branch_alpha.delete(url)

        # Object is filtered out, so it appears as "not found" rather than "forbidden"
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert RecruitmentRequest.objects.filter(id=recruitment_request_beta.id).exists()


# ==============================================================================
# Test Classes - Multiple Scope Assignment
# ==============================================================================


@pytest.mark.django_db
class TestMultipleBranchScope:
    """Test user with multiple branches assigned"""

    def test_user_with_multiple_branches_sees_both(
        self,
        db,
        branch_alpha,
        branch_beta,
        recruitment_request_alpha,
        recruitment_request_beta,
        recruitment_request_permissions,
    ):
        """User with multiple branch scopes should see requests from all assigned branches"""
        # Create role with both branches and permissions
        role = Role.objects.create(
            code="VT_MULTI_BRANCH",
            name="Multi Branch Role",
            data_scope_level=DataScopeLevel.BRANCH,
        )
        role.permissions.set(recruitment_request_permissions)
        RoleBranchScope.objects.create(role=role, branch=branch_alpha)
        RoleBranchScope.objects.create(role=role, branch=branch_beta)

        # Create user with multi-branch role
        user = User.objects.create_user(
            username="user_multi_branch",
            email="multi@test.com",
            password="testpass123",
        )
        user.role = role
        user.save()

        # Create API client
        client = APIClient()
        client.force_authenticate(user=user)

        url = reverse("hrm:recruitment-request-list")
        response = client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = get_response_data(response)
        assert len(data) == 2
        request_names = [r["name"] for r in data]
        assert "Alpha Developer Position" in request_names
        assert "Beta Developer Position" in request_names


# ==============================================================================
# Test Classes - DataScopeReportFilterMixin Unit Tests
# ==============================================================================


@pytest.mark.django_db
class TestDataScopeReportFilterMixin:
    """Unit tests for DataScopeReportFilterMixin helper methods"""

    def test_apply_branch_scope_with_allowed_branch_id(self, user_branch_alpha, branch_alpha):
        """When user specifies their own branch_id, it should be kept"""
        from apps.hrm.api.mixins import DataScopeReportFilterMixin
        from apps.hrm.utils.role_data_scope import collect_role_allowed_units

        mixin = DataScopeReportFilterMixin()
        allowed = collect_role_allowed_units(user_branch_alpha)
        filters = {"branch_id": branch_alpha.id}

        result = mixin._apply_branch_scope(filters, allowed)

        assert result["branch_id"] == branch_alpha.id
        assert "branch_id__in" not in result

    def test_apply_branch_scope_with_disallowed_branch_id(self, user_branch_alpha, branch_beta):
        """When user specifies disallowed branch_id, it should be set to -1"""
        from apps.hrm.api.mixins import DataScopeReportFilterMixin
        from apps.hrm.utils.role_data_scope import collect_role_allowed_units

        mixin = DataScopeReportFilterMixin()
        allowed = collect_role_allowed_units(user_branch_alpha)
        filters = {"branch_id": branch_beta.id}

        result = mixin._apply_branch_scope(filters, allowed)

        # Disallowed branch should force no results
        assert result["branch_id"] == -1

    def test_apply_branch_scope_without_branch_id(self, user_branch_alpha, branch_alpha):
        """When user doesn't specify branch_id, allowed branches should be added"""
        from apps.hrm.api.mixins import DataScopeReportFilterMixin
        from apps.hrm.utils.role_data_scope import collect_role_allowed_units

        mixin = DataScopeReportFilterMixin()
        allowed = collect_role_allowed_units(user_branch_alpha)
        filters = {}

        result = mixin._apply_branch_scope(filters, allowed)

        assert "branch_id__in" in result
        assert branch_alpha.id in result["branch_id__in"]

    def test_apply_data_scope_to_filters_root_user(self, user_root_ds):
        """ROOT user should pass through filters unchanged"""
        from unittest.mock import Mock

        from apps.hrm.api.mixins import DataScopeReportFilterMixin

        mixin = DataScopeReportFilterMixin()
        request = Mock()
        request.user = user_root_ds
        filters = {"branch_id": 999, "custom_filter": "value"}

        result = mixin._apply_data_scope_to_filters(request, filters)

        # ROOT user filters should be unchanged
        assert result == filters

    def test_apply_data_scope_to_filters_branch_user(self, user_branch_alpha, branch_alpha):
        """BRANCH user without org filters should get allowed units added"""
        from unittest.mock import Mock

        from apps.hrm.api.mixins import DataScopeReportFilterMixin

        mixin = DataScopeReportFilterMixin()
        request = Mock()
        request.user = user_branch_alpha
        filters = {"date_from": "2025-01-01"}

        result = mixin._apply_data_scope_to_filters(request, filters)

        assert "branch_id__in" in result
        assert branch_alpha.id in result["branch_id__in"]
        assert result["date_from"] == "2025-01-01"  # Other filters preserved

    def test_apply_data_scope_to_filters_department_user(self, user_department_alpha, department_alpha):
        """DEPARTMENT user should get department_id__in filter"""
        from unittest.mock import Mock

        from apps.hrm.api.mixins import DataScopeReportFilterMixin

        mixin = DataScopeReportFilterMixin()
        request = Mock()
        request.user = user_department_alpha
        filters = {}

        result = mixin._apply_data_scope_to_filters(request, filters)

        assert "department_id__in" in result
        assert department_alpha.id in result["department_id__in"]


# ==============================================================================
# Test Classes - HRM Dashboard Data Scope Tests
# ==============================================================================


@pytest.fixture
def dashboard_permissions(db):
    """Create permission for HRM dashboard"""
    perm, _ = Permission.objects.get_or_create(
        code="hrm.dashboard.common.realtime",
        defaults={
            "name": "View HRM Dashboard",
            "description": "View HRM dashboard realtime stats",
            "module": "HRM",
            "submodule": "Dashboard",
        },
    )
    return [perm]


@pytest.fixture
def role_root_with_dashboard(db, recruitment_request_permissions, dashboard_permissions):
    """Create ROOT role with dashboard permission"""
    role = Role.objects.create(
        code="VT_ROOT_DASH",
        name="Root Dashboard Role",
        data_scope_level=DataScopeLevel.ROOT,
    )
    role.permissions.set(recruitment_request_permissions + dashboard_permissions)
    return role


@pytest.fixture
def role_branch_alpha_with_dashboard(db, branch_alpha, recruitment_request_permissions, dashboard_permissions):
    """Create BRANCH Alpha role with dashboard permission"""
    role = Role.objects.create(
        code="VT_BRANCH_ALPHA_DASH",
        name="Branch Alpha Dashboard Role",
        data_scope_level=DataScopeLevel.BRANCH,
    )
    role.permissions.set(recruitment_request_permissions + dashboard_permissions)
    RoleBranchScope.objects.create(role=role, branch=branch_alpha)
    return role


@pytest.fixture
def user_root_dashboard(db, role_root_with_dashboard):
    """User with ROOT scope and dashboard permission"""
    user = User.objects.create_user(
        username="user_root_dash",
        email="root_dash@test.com",
        password="testpass123",
    )
    user.role = role_root_with_dashboard
    user.save()
    return user


@pytest.fixture
def user_branch_alpha_dashboard(db, role_branch_alpha_with_dashboard):
    """User with BRANCH Alpha scope and dashboard permission"""
    user = User.objects.create_user(
        username="user_branch_alpha_dash",
        email="branch_alpha_dash@test.com",
        password="testpass123",
    )
    user.role = role_branch_alpha_with_dashboard
    user.save()
    return user


@pytest.mark.django_db
class TestHRMDashboardDataScope:
    """Test HRM Dashboard with data scope filtering"""

    def test_root_user_sees_all_proposals(
        self,
        user_root_dashboard,
        employee_alpha,
        employee_beta,
    ):
        """ROOT user should see pending proposals from all branches"""
        from django.core.cache import cache

        from apps.hrm.constants import ProposalStatus, ProposalType
        from apps.hrm.models import Proposal
        from apps.hrm.utils.dashboard_cache import HRM_DASHBOARD_CACHE_KEY

        # Clear cache
        cache.delete(HRM_DASHBOARD_CACHE_KEY)

        # Create proposals in different branches
        Proposal.objects.create(
            code="DX-PL-ALPHA-001",
            created_by=employee_alpha,
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.PENDING,
        )
        Proposal.objects.create(
            code="DX-PL-BETA-001",
            created_by=employee_beta,
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.PENDING,
        )

        # Create API client
        client = APIClient()
        client.force_authenticate(user=user_root_dashboard)

        url = reverse("hrm:hrm-common-dashboard-realtime")
        response = client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = get_response_data(response)

        # Find paid leave count
        proposal_items = {item["key"]: item for item in data["proposals_pending"]["items"]}
        assert proposal_items["proposals_paid_leave"]["count"] == 2

    def test_branch_user_sees_only_own_branch_proposals(
        self,
        user_branch_alpha_dashboard,
        employee_alpha,
        employee_beta,
    ):
        """BRANCH user should only see proposals from their branch"""
        from django.core.cache import cache

        from apps.hrm.constants import ProposalStatus, ProposalType
        from apps.hrm.models import Proposal
        from apps.hrm.utils.dashboard_cache import HRM_DASHBOARD_CACHE_KEY

        # Clear cache
        cache.delete(HRM_DASHBOARD_CACHE_KEY)

        # Create proposals in different branches
        Proposal.objects.create(
            code="DX-PL-ALPHA-002",
            created_by=employee_alpha,
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.PENDING,
        )
        Proposal.objects.create(
            code="DX-PL-BETA-002",
            created_by=employee_beta,
            proposal_type=ProposalType.PAID_LEAVE,
            proposal_status=ProposalStatus.PENDING,
        )

        # Create API client
        client = APIClient()
        client.force_authenticate(user=user_branch_alpha_dashboard)

        url = reverse("hrm:hrm-common-dashboard-realtime")
        response = client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = get_response_data(response)

        # Should only see 1 proposal (from Alpha branch)
        proposal_items = {item["key"]: item for item in data["proposals_pending"]["items"]}
        assert proposal_items["proposals_paid_leave"]["count"] == 1

    def test_branch_user_sees_only_own_branch_penalty_tickets(
        self,
        user_branch_alpha_dashboard,
        employee_alpha,
        employee_beta,
    ):
        """BRANCH user should only see penalty tickets from their branch"""
        from datetime import date

        from django.core.cache import cache

        from apps.hrm.utils.dashboard_cache import HRM_DASHBOARD_CACHE_KEY
        from apps.payroll.models import PenaltyTicket

        # Clear cache
        cache.delete(HRM_DASHBOARD_CACHE_KEY)

        # Create penalty tickets in different branches
        PenaltyTicket.objects.create(
            employee=employee_alpha,
            employee_code=employee_alpha.code,
            employee_name=employee_alpha.fullname,
            violation_count=1,
            amount=100000,
            month=date(2025, 1, 1),
            status=PenaltyTicket.Status.UNPAID,
        )
        PenaltyTicket.objects.create(
            employee=employee_beta,
            employee_code=employee_beta.code,
            employee_name=employee_beta.fullname,
            violation_count=1,
            amount=50000,
            month=date(2025, 1, 1),
            status=PenaltyTicket.Status.UNPAID,
        )

        # Create API client
        client = APIClient()
        client.force_authenticate(user=user_branch_alpha_dashboard)

        url = reverse("hrm:hrm-common-dashboard-realtime")
        response = client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = get_response_data(response)

        # Should only see 1 penalty ticket (from Alpha branch)
        assert data["penalty_tickets_unpaid"]["count"] == 1

    def test_branch_user_sees_only_own_branch_attendance(
        self,
        user_branch_alpha_dashboard,
        employee_alpha,
        employee_beta,
    ):
        """BRANCH user should only see attendance records from their branch"""
        from django.core.cache import cache
        from django.utils import timezone

        from apps.hrm.constants import AttendanceType
        from apps.hrm.models import AttendanceRecord
        from apps.hrm.utils.dashboard_cache import HRM_DASHBOARD_CACHE_KEY

        # Clear cache
        cache.delete(HRM_DASHBOARD_CACHE_KEY)

        # Create attendance records in different branches
        AttendanceRecord.objects.create(
            code="DD-OTHER-ALPHA-001",
            attendance_type=AttendanceType.OTHER,
            attendance_code=employee_alpha.attendance_code,
            timestamp=timezone.now(),
            employee=employee_alpha,
            is_pending=True,
            is_valid=False,
        )
        AttendanceRecord.objects.create(
            code="DD-OTHER-BETA-001",
            attendance_type=AttendanceType.OTHER,
            attendance_code=employee_beta.attendance_code,
            timestamp=timezone.now(),
            employee=employee_beta,
            is_pending=True,
            is_valid=False,
        )

        # Create API client
        client = APIClient()
        client.force_authenticate(user=user_branch_alpha_dashboard)

        url = reverse("hrm:hrm-common-dashboard-realtime")
        response = client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = get_response_data(response)

        # Should only see 1 attendance record (from Alpha branch)
        assert data["attendance_other_pending"]["count"] == 1


# ==============================================================================
# Test Classes - Attendance Report Data Scope Tests
# ==============================================================================


@pytest.fixture
def attendance_report_permissions(db):
    """Create permissions for attendance report endpoints"""
    permissions = []
    for action in ["by_method", "by_project", "by_project_organization"]:
        perm, _ = Permission.objects.get_or_create(
            code=f"recruitment_reports.{action}",
            defaults={
                "name": f"Attendance Report {action.title()}",
                "description": f"Can view attendance {action} report",
                "module": "Report",
                "submodule": "Attendance",
            },
        )
        permissions.append(perm)
    return permissions


@pytest.fixture
def role_root_with_reports(db, recruitment_request_permissions, attendance_report_permissions):
    """Create ROOT role with report permissions"""
    role = Role.objects.create(
        code="VT_ROOT_RPT",
        name="Root Report Role",
        data_scope_level=DataScopeLevel.ROOT,
    )
    role.permissions.set(recruitment_request_permissions + attendance_report_permissions)
    return role


@pytest.fixture
def role_branch_alpha_with_reports(db, branch_alpha, recruitment_request_permissions, attendance_report_permissions):
    """Create BRANCH Alpha role with report permissions"""
    role = Role.objects.create(
        code="VT_BRANCH_ALPHA_RPT",
        name="Branch Alpha Report Role",
        data_scope_level=DataScopeLevel.BRANCH,
    )
    role.permissions.set(recruitment_request_permissions + attendance_report_permissions)
    RoleBranchScope.objects.create(role=role, branch=branch_alpha)
    return role


@pytest.fixture
def user_root_reports(db, role_root_with_reports):
    """User with ROOT scope and report permissions"""
    user = User.objects.create_user(
        username="user_root_rpt",
        email="root_rpt@test.com",
        password="testpass123",
    )
    user.role = role_root_with_reports
    user.save()
    return user


@pytest.fixture
def user_branch_alpha_reports(db, role_branch_alpha_with_reports):
    """User with BRANCH Alpha scope and report permissions"""
    user = User.objects.create_user(
        username="user_branch_alpha_rpt",
        email="branch_alpha_rpt@test.com",
        password="testpass123",
    )
    user.role = role_branch_alpha_with_reports
    user.save()
    return user


@pytest.mark.django_db
class TestAttendanceReportDataScope:
    """Test Attendance Report ViewSet with data scope filtering"""

    def test_root_user_sees_all_branches_in_report(
        self,
        user_root_reports,
        branch_alpha,
        branch_beta,
        department_alpha,
        department_beta,
        employee_alpha,
        employee_beta,
    ):
        """ROOT user should see report data from all branches"""
        from django.utils import timezone

        from apps.hrm.constants import AttendanceType
        from apps.hrm.models import AttendanceDailyReport

        today = timezone.localdate()

        # Create attendance reports in different branches
        AttendanceDailyReport.objects.create(
            report_date=today,
            employee=employee_alpha,
            branch=branch_alpha,
            block=department_alpha.block,
            department=department_alpha,
            attendance_method=AttendanceType.BIOMETRIC_DEVICE,
        )
        AttendanceDailyReport.objects.create(
            report_date=today,
            employee=employee_beta,
            branch=branch_beta,
            block=department_beta.block,
            department=department_beta,
            attendance_method=AttendanceType.WIFI,
        )

        # Create API client
        client = APIClient()
        client.force_authenticate(user=user_root_reports)

        url = reverse("hrm:attendance-report-by-method")
        response = client.get(url, {"attendance_date": today.isoformat()})

        assert response.status_code == status.HTTP_200_OK
        data = get_response_data(response)

        # ROOT should see both reports (API returns string)
        assert int(float(data["absolute"]["has_attendance"])) == 2

    def test_branch_user_sees_only_own_branch_in_report(
        self,
        user_branch_alpha_reports,
        branch_alpha,
        branch_beta,
        department_alpha,
        department_beta,
        employee_alpha,
        employee_beta,
    ):
        """BRANCH user should only see report data from their branch"""
        from django.utils import timezone

        from apps.hrm.constants import AttendanceType
        from apps.hrm.models import AttendanceDailyReport

        today = timezone.localdate()

        # Create attendance reports in different branches
        AttendanceDailyReport.objects.create(
            report_date=today,
            employee=employee_alpha,
            branch=branch_alpha,
            block=department_alpha.block,
            department=department_alpha,
            attendance_method=AttendanceType.BIOMETRIC_DEVICE,
        )
        AttendanceDailyReport.objects.create(
            report_date=today,
            employee=employee_beta,
            branch=branch_beta,
            block=department_beta.block,
            department=department_beta,
            attendance_method=AttendanceType.WIFI,
        )

        # Create API client
        client = APIClient()
        client.force_authenticate(user=user_branch_alpha_reports)

        url = reverse("hrm:attendance-report-by-method")
        response = client.get(url, {"attendance_date": today.isoformat()})

        assert response.status_code == status.HTTP_200_OK
        data = get_response_data(response)

        # BRANCH user should only see 1 report (from Alpha branch, API returns string)
        assert int(float(data["absolute"]["has_attendance"])) == 1

    def test_branch_user_cannot_access_other_branch_explicitly(
        self,
        user_branch_alpha_reports,
        branch_alpha,
        branch_beta,
        department_alpha,
        department_beta,
        employee_beta,
    ):
        """BRANCH user explicitly filtering for other branch should get no results"""
        from django.utils import timezone

        from apps.hrm.constants import AttendanceType
        from apps.hrm.models import AttendanceDailyReport

        today = timezone.localdate()

        # Create attendance report only in beta branch
        AttendanceDailyReport.objects.create(
            report_date=today,
            employee=employee_beta,
            branch=branch_beta,
            block=department_beta.block,
            department=department_beta,
            attendance_method=AttendanceType.BIOMETRIC_DEVICE,
        )

        # Create API client
        client = APIClient()
        client.force_authenticate(user=user_branch_alpha_reports)

        # Try to filter by beta branch
        url = reverse("hrm:attendance-report-by-method")
        response = client.get(
            url,
            {
                "attendance_date": today.isoformat(),
                "branch_id": branch_beta.id,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = get_response_data(response)

        # Should get 0 results because branch_beta is not allowed (API returns string)
        assert int(float(data["absolute"]["has_attendance"])) == 0

    def test_branch_user_can_filter_own_branch(
        self,
        user_branch_alpha_reports,
        branch_alpha,
        department_alpha,
        employee_alpha,
    ):
        """BRANCH user can explicitly filter for their own branch"""
        from django.utils import timezone

        from apps.hrm.constants import AttendanceType
        from apps.hrm.models import AttendanceDailyReport

        today = timezone.localdate()

        # Create attendance report in alpha branch
        AttendanceDailyReport.objects.create(
            report_date=today,
            employee=employee_alpha,
            branch=branch_alpha,
            block=department_alpha.block,
            department=department_alpha,
            attendance_method=AttendanceType.GEOLOCATION,
        )

        # Create API client
        client = APIClient()
        client.force_authenticate(user=user_branch_alpha_reports)

        # Filter by own branch explicitly
        url = reverse("hrm:attendance-report-by-method")
        response = client.get(
            url,
            {
                "attendance_date": today.isoformat(),
                "branch_id": branch_alpha.id,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = get_response_data(response)

        # Should see the report from their own branch (API returns string)
        assert int(float(data["absolute"]["has_attendance"])) == 1
