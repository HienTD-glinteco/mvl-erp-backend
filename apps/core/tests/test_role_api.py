import pytest
from django.urls import reverse
from django.utils.translation import gettext as _
from rest_framework import status

from apps.core.models import Permission, Role


class APITestMixin:
    """Mixin to handle wrapped API responses and data extraction"""

    def get_response_data(self, response):
        """Extract data from wrapped API response"""
        content = response.json()
        if "data" in content:
            data = content["data"]
            # Handle paginated responses - extract results list
            if isinstance(data, dict) and "results" in data:
                return data["results"]
            return data
        return content


@pytest.mark.django_db
class TestRoleAPI(APITestMixin):
    """Test cases for Role API endpoints"""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client):
        self.client = api_client

    @pytest.fixture
    def permissions(self, db):
        """Create test permissions."""
        perm1 = Permission.objects.create(code="view_users", description="View users")
        perm2 = Permission.objects.create(code="edit_users", description="Edit users")
        perm3 = Permission.objects.create(code="delete_users", description="Delete users")
        return [perm1, perm2, perm3]

    @pytest.fixture
    def system_roles(self, db):
        """Create system roles for tests."""
        system_role_admin = Role.objects.create(
            code="VT001",
            name="Admin hệ thống",
            description="Vai trò có tất cả các quyền của hệ thống",
            is_system_role=True,
        )
        system_role_basic = Role.objects.create(
            code="VT002",
            name="Vai trò cơ bản",
            description="Vai trò mặc định của tài khoản nhân viên khi được tạo mới",
            is_system_role=True,
        )
        return system_role_admin, system_role_basic

    def test_list_roles(self, permissions, system_roles):
        """Test listing roles via API"""
        role1 = Role.objects.create(code="VT003", name="Test Role 1", description="Test description 1")
        role2 = Role.objects.create(code="VT004", name="Test Role 2", description="Test description 2")
        role1.permissions.set(permissions[:2])
        role2.permissions.set(permissions)

        url = reverse("core:role-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        # Should have at least 4 roles (2 system + 2 custom)
        assert len(response_data) >= 4

    def test_create_role(self, permissions, system_roles):
        """Test creating a role via API"""
        url = reverse("core:role-list")
        role_data = {
            "name": "New Test Role",
            "description": "New test role description",
            "permission_ids": [p.id for p in permissions],
        }

        response = self.client.post(url, role_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        response_data = self.get_response_data(response)

        # Verify code was auto-generated
        assert response_data["code"].startswith("VT")
        assert response_data["name"] == role_data["name"]
        assert response_data["description"] == role_data["description"]
        assert response_data["is_system_role"] is False

        # Verify role was created in database
        role = Role.objects.get(code=response_data["code"])
        assert role.permissions.count() == len(permissions)

    def test_create_role_without_permissions(self, permissions, system_roles):
        """Test creating a role without permissions should fail"""
        url = reverse("core:role-list")
        role_data = {
            "name": "Invalid Role",
            "description": "Role without permissions",
            "permission_ids": [],
        }

        response = self.client.post(url, role_data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_role_duplicate_name(self, permissions, system_roles):
        """Test creating a role with duplicate name should fail"""
        Role.objects.create(code="VT003", name="Existing Role", description="Test")

        url = reverse("core:role-list")
        role_data = {
            "name": "Existing Role",
            "description": "Duplicate name",
            "permission_ids": [p.id for p in permissions],
        }

        response = self.client.post(url, role_data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_clone_role_creates_new_role(self, permissions, system_roles):
        """Test cloning a role duplicates its data and permissions"""
        role = Role.objects.create(code="VT003", name="Clone Source", description="Source role")
        role.permissions.set(permissions[:2])

        url = reverse("core:role-clone", kwargs={"pk": role.pk})
        response = self.client.post(url)

        assert response.status_code == status.HTTP_201_CREATED
        cloned_data = self.get_response_data(response)
        assert cloned_data["name"] == "Clone Source-copy"
        assert cloned_data["id"] != role.id
        assert cloned_data["code"] != role.code
        assert cloned_data["is_system_role"] is False
        assert len(cloned_data["permissions_detail"]) == 2

        cloned_role = Role.objects.get(pk=cloned_data["id"])
        assert cloned_role.is_system_role is False
        assert cloned_role.permissions.count() == 2

    def test_clone_role_generates_unique_name(self, permissions, system_roles):
        """Test cloning a role when '-copy' already exists appends a numeric suffix"""
        role = Role.objects.create(code="VT003", name="Approval Role", description="Source role")
        role.permissions.set(permissions[:1])
        existing_clone = Role.objects.create(code="VT004", name="Approval Role-copy", description="Existing clone")
        existing_clone.permissions.set(permissions[:1])

        url = reverse("core:role-clone", kwargs={"pk": role.pk})
        response = self.client.post(url)

        assert response.status_code == status.HTTP_201_CREATED
        cloned_data = self.get_response_data(response)
        assert cloned_data["name"] == "Approval Role-copy-2"

    def test_retrieve_role(self, permissions, system_roles):
        """Test retrieving a role via API"""
        role = Role.objects.create(code="VT003", name="Test Role", description="Test description")
        role.permissions.set(permissions)

        url = reverse("core:role-detail", kwargs={"pk": role.pk})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        assert response_data["code"] == role.code
        assert response_data["name"] == role.name
        assert len(response_data["permissions_detail"]) == len(permissions)

    def test_update_role(self, permissions, system_roles):
        """Test updating a role via API"""
        role = Role.objects.create(code="VT003", name="Test Role", description="Test description")
        role.permissions.set(permissions[:1])

        update_data = {
            "name": "Updated Role Name",
            "description": "Updated description",
            "permission_ids": [p.id for p in permissions],
        }
        url = reverse("core:role-detail", kwargs={"pk": role.pk})
        response = self.client.patch(url, update_data, format="json")

        assert response.status_code == status.HTTP_200_OK
        role.refresh_from_db()
        assert role.name == update_data["name"]
        assert role.description == update_data["description"]
        assert role.permissions.count() == len(permissions)

    def test_update_system_role_other_fields_should_fail(self, permissions, system_roles):
        """Test updating non-permission fields of system role should fail"""
        role = system_roles[0]  # VT001

        update_data = {"name": "Trying to update system role"}
        url = reverse("core:role-detail", kwargs={"pk": role.pk})
        response = self.client.patch(url, update_data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_update_system_role_permissions_should_succeed(self, permissions, system_roles):
        """Test updating permissions of system role should succeed"""
        role = system_roles[0]  # VT001

        # Update only permissions
        update_data = {"permission_ids": [p.id for p in permissions[:2]]}
        url = reverse("core:role-detail", kwargs={"pk": role.pk})
        response = self.client.patch(url, update_data, format="json")

        assert response.status_code == status.HTTP_200_OK
        role.refresh_from_db()
        assert role.permissions.count() == 2

    def test_delete_role(self, permissions, system_roles):
        """Test deleting a role via API"""
        role = Role.objects.create(code="VT003", name="Test Role", description="Test description")

        url = reverse("core:role-detail", kwargs={"pk": role.pk})
        response = self.client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Role.objects.filter(pk=role.pk).exists()

    def test_delete_system_role_should_fail(self, permissions, system_roles):
        """Test deleting a system role should fail"""
        role = system_roles[0]  # VT001

        url = reverse("core:role-detail", kwargs={"pk": role.pk})
        response = self.client.delete(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        # Role should still exist
        assert Role.objects.filter(pk=role.pk).exists()

    def test_delete_role_in_use_should_fail(self, superuser, permissions, system_roles):
        """Test deleting a role that is in use by users should fail"""
        from django.contrib.auth import get_user_model

        User = get_user_model()

        role = Role.objects.create(code="VT003", name="Test Role", description="Test description")
        # Assign role to a user
        user = User.objects.create_superuser(username="roleuser", email="roleuser@example.com", password="testpass123")
        user.role = role
        user.save()

        url = reverse("core:role-detail", kwargs={"pk": role.pk})
        response = self.client.delete(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        # Role should still exist
        assert Role.objects.filter(pk=role.pk).exists()

    def test_search_role_by_name(self, permissions, system_roles):
        """Test searching roles by name"""
        Role.objects.create(code="VT003", name="Quản trị viên", description="Test")
        Role.objects.create(code="VT004", name="Nhân viên", description="Test")

        # Search for "Quản trị" - should find the role
        url = reverse("core:role-list")
        response = self.client.get(url, {"search": "Quản trị"})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        role_names = [r["name"] for r in response_data]
        assert "Quản trị viên" in role_names
        assert "Nhân viên" not in role_names

    def test_filter_role_by_name_icontains(self, permissions, system_roles):
        """Test filtering roles by name (case-insensitive)"""
        Role.objects.create(code="VT003", name="Quản trị viên", description="Test")
        Role.objects.create(code="VT004", name="Nhân viên", description="Test")

        # Filter by name containing "quản" (lowercase)
        url = reverse("core:role-list")
        response = self.client.get(url, {"name": "quản"})

        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        role_names = [r["name"] for r in response_data]
        assert "Quản trị viên" in role_names

    def test_created_by_display(self, permissions, system_roles):
        """Test created_by field displays correctly"""
        system_role = system_roles[0]  # VT001
        user_role = Role.objects.create(code="VT003", name="User Role", description="Test")

        url = reverse("core:role-detail", kwargs={"pk": system_role.pk})
        response = self.client.get(url)
        response_data = self.get_response_data(response)
        assert response_data["created_by"] == _("System")

        url = reverse("core:role-detail", kwargs={"pk": user_role.pk})
        response = self.client.get(url)
        response_data = self.get_response_data(response)
        assert response_data["created_by"] == _("User")

    def test_code_auto_increment(self, permissions, system_roles):
        """Test that role codes are auto-incremented"""
        url = reverse("core:role-list")

        # Create first role
        role_data1 = {
            "name": "Role 1",
            "description": "First role",
            "permission_ids": [p.id for p in permissions],
        }
        response1 = self.client.post(url, role_data1, format="json")
        assert response1.status_code == status.HTTP_201_CREATED
        code1 = self.get_response_data(response1)["code"]

        # Create second role
        role_data2 = {
            "name": "Role 2",
            "description": "Second role",
            "permission_ids": [p.id for p in permissions],
        }
        response2 = self.client.post(url, role_data2, format="json")
        assert response2.status_code == status.HTTP_201_CREATED
        code2 = self.get_response_data(response2)["code"]

        # Extract numbers and verify increment
        num1 = int(code1[2:])
        num2 = int(code2[2:])
        assert num2 == num1 + 1

    def test_pagination_with_page_size(self, permissions, system_roles):
        """Test that page_size query parameter works correctly"""
        # Create multiple roles for pagination testing
        for i in range(15):
            Role.objects.create(
                code=f"VTP{i:03d}",
                name=f"Test Role {i}",
                description=f"Test role {i} for pagination",
            )

        url = reverse("core:role-list")

        # Test with default page size (25)
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        # Should return all roles (2 system + 15 test = 17 total, less than default 25)
        assert len(response_data) == 17

        # Test with custom page_size=5
        response = self.client.get(url, {"page_size": 5})
        assert response.status_code == status.HTTP_200_OK
        content = response.json()
        data = content["data"]
        assert len(data["results"]) == 5
        assert data["count"] == 17
        assert data["next"] is not None
        assert data["previous"] is None

        # Test with page_size=10 and page=2
        response = self.client.get(url, {"page_size": 10, "page": 2})
        assert response.status_code == status.HTTP_200_OK
        content = response.json()
        data = content["data"]
        assert len(data["results"]) == 7  # 17 total - 10 on page 1 = 7 on page 2
        assert data["next"] is None
        assert data["previous"] is not None

        # Test with page_size exceeding max (100)
        response = self.client.get(url, {"page_size": 200})
        assert response.status_code == status.HTTP_200_OK
        response_data = self.get_response_data(response)
        # Should be capped at 100, but we only have 17 items
        assert len(response_data) == 17
