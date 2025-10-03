import json

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import Permission, Role

User = get_user_model()


class APITestMixin:
    """Mixin to handle wrapped API responses and data extraction"""

    def get_response_data(self, response):
        """Extract data from wrapped API response"""
        content = json.loads(response.content.decode())
        if "data" in content:
            return content["data"]
        return content


class RoleAPITest(TransactionTestCase, APITestMixin):
    """Test cases for Role API endpoints"""

    def setUp(self):
        # Clear all existing data for clean tests
        Role.objects.all().delete()
        User.objects.all().delete()
        Permission.objects.all().delete()

        # Create test permissions
        self.perm1 = Permission.objects.create(code="view_users", description="View users")
        self.perm2 = Permission.objects.create(code="edit_users", description="Edit users")
        self.perm3 = Permission.objects.create(code="delete_users", description="Delete users")
        self.permissions = [self.perm1, self.perm2, self.perm3]

        # Create system roles manually for tests
        self.system_role_admin = Role.objects.create(
            code="VT001",
            name="Admin hệ thống",
            description="Vai trò có tất cả các quyền của hệ thống",
            is_system_role=True,
        )
        self.system_role_basic = Role.objects.create(
            code="VT002",
            name="Vai trò cơ bản",
            description="Vai trò mặc định của tài khoản nhân viên khi được tạo mới",
            is_system_role=True,
        )

        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_list_roles(self):
        """Test listing roles via API"""
        # Create test roles
        role1 = Role.objects.create(code="VT003", name="Test Role 1", description="Test description 1")
        role2 = Role.objects.create(code="VT004", name="Test Role 2", description="Test description 2")
        role1.permissions.set(self.permissions[:2])
        role2.permissions.set(self.permissions)

        url = reverse("core:role-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        # Should have at least 2 roles (VT001, VT002 are created by migration)
        self.assertGreaterEqual(len(response_data), 2)

    def test_create_role(self):
        """Test creating a role via API"""
        url = reverse("core:role-list")
        role_data = {
            "name": "New Test Role",
            "description": "New test role description",
            "permission_ids": [p.id for p in self.permissions],
        }

        response = self.client.post(url, role_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = self.get_response_data(response)

        # Verify code was auto-generated
        self.assertTrue(response_data["code"].startswith("VT"))
        self.assertEqual(response_data["name"], role_data["name"])
        self.assertEqual(response_data["description"], role_data["description"])
        self.assertFalse(response_data["is_system_role"])

        # Verify role was created in database
        role = Role.objects.get(code=response_data["code"])
        self.assertEqual(role.permissions.count(), len(self.permissions))

    def test_create_role_without_permissions(self):
        """Test creating a role without permissions should fail"""
        url = reverse("core:role-list")
        role_data = {
            "name": "Invalid Role",
            "description": "Role without permissions",
            "permission_ids": [],
        }

        response = self.client.post(url, role_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_role_duplicate_name(self):
        """Test creating a role with duplicate name should fail"""
        Role.objects.create(code="VT003", name="Existing Role", description="Test")

        url = reverse("core:role-list")
        role_data = {
            "name": "Existing Role",
            "description": "Duplicate name",
            "permission_ids": [p.id for p in self.permissions],
        }

        response = self.client.post(url, role_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retrieve_role(self):
        """Test retrieving a role via API"""
        role = Role.objects.create(code="VT003", name="Test Role", description="Test description")
        role.permissions.set(self.permissions)

        url = reverse("core:role-detail", kwargs={"pk": role.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["code"], role.code)
        self.assertEqual(response_data["name"], role.name)
        self.assertEqual(len(response_data["permissions_detail"]), len(self.permissions))

    def test_update_role(self):
        """Test updating a role via API"""
        role = Role.objects.create(code="VT003", name="Test Role", description="Test description")
        role.permissions.set(self.permissions[:1])

        update_data = {
            "name": "Updated Role Name",
            "description": "Updated description",
            "permission_ids": [p.id for p in self.permissions],
        }
        url = reverse("core:role-detail", kwargs={"pk": role.pk})
        response = self.client.patch(url, update_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        role.refresh_from_db()
        self.assertEqual(role.name, update_data["name"])
        self.assertEqual(role.description, update_data["description"])
        self.assertEqual(role.permissions.count(), len(self.permissions))

    def test_update_system_role_should_fail(self):
        """Test updating a system role should fail"""
        # Get VT001 system role
        role = Role.objects.get(code="VT001")

        update_data = {"name": "Trying to update system role"}
        url = reverse("core:role-detail", kwargs={"pk": role.pk})
        response = self.client.patch(url, update_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_role(self):
        """Test deleting a role via API"""
        role = Role.objects.create(code="VT003", name="Test Role", description="Test description")

        url = reverse("core:role-detail", kwargs={"pk": role.pk})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Role.objects.filter(pk=role.pk).exists())

    def test_delete_system_role_should_fail(self):
        """Test deleting a system role should fail"""
        # Get VT001 system role
        role = Role.objects.get(code="VT001")

        url = reverse("core:role-detail", kwargs={"pk": role.pk})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Role should still exist
        self.assertTrue(Role.objects.filter(pk=role.pk).exists())

    def test_delete_role_in_use_should_fail(self):
        """Test deleting a role that is in use by users should fail"""
        role = Role.objects.create(code="VT003", name="Test Role", description="Test description")
        # Assign role to a user
        user = User.objects.create_user(username="roleuser", email="roleuser@example.com", password="testpass123")
        user.role = role
        user.save()

        url = reverse("core:role-detail", kwargs={"pk": role.pk})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Role should still exist
        self.assertTrue(Role.objects.filter(pk=role.pk).exists())

    def test_search_role_by_name(self):
        """Test searching roles by name"""
        Role.objects.create(code="VT003", name="Quản trị viên", description="Test")
        Role.objects.create(code="VT004", name="Nhân viên", description="Test")

        # Search for "Quản trị" - should find the role
        url = reverse("core:role-list")
        response = self.client.get(url, {"search": "Quản trị"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        role_names = [r["name"] for r in response_data]
        self.assertIn("Quản trị viên", role_names)
        self.assertNotIn("Nhân viên", role_names)

    def test_filter_role_by_name_icontains(self):
        """Test filtering roles by name (case-insensitive)"""
        Role.objects.create(code="VT003", name="Quản trị viên", description="Test")
        Role.objects.create(code="VT004", name="Nhân viên", description="Test")

        # Filter by name containing "quản" (lowercase)
        url = reverse("core:role-list")
        response = self.client.get(url, {"name": "quản"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        role_names = [r["name"] for r in response_data]
        self.assertIn("Quản trị viên", role_names)

    def test_created_by_display(self):
        """Test created_by field displays correctly"""
        system_role = Role.objects.get(code="VT001")
        user_role = Role.objects.create(code="VT003", name="User Role", description="Test")

        url = reverse("core:role-detail", kwargs={"pk": system_role.pk})
        response = self.client.get(url)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["created_by"], "Hệ thống")

        url = reverse("core:role-detail", kwargs={"pk": user_role.pk})
        response = self.client.get(url)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["created_by"], "Người dùng")

    def test_code_auto_increment(self):
        """Test that role codes are auto-incremented"""
        url = reverse("core:role-list")

        # Create first role
        role_data1 = {
            "name": "Role 1",
            "description": "First role",
            "permission_ids": [p.id for p in self.permissions],
        }
        response1 = self.client.post(url, role_data1, format="json")
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        code1 = self.get_response_data(response1)["code"]

        # Create second role
        role_data2 = {
            "name": "Role 2",
            "description": "Second role",
            "permission_ids": [p.id for p in self.permissions],
        }
        response2 = self.client.post(url, role_data2, format="json")
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)
        code2 = self.get_response_data(response2)["code"]

        # Extract numbers and verify increment
        num1 = int(code1[2:])
        num2 = int(code2[2:])
        self.assertEqual(num2, num1 + 1)
