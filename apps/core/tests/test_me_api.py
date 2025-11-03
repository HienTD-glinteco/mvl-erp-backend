import json

from django.contrib.auth import get_user_model
from django.test import TestCase
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


class MeAPITest(TestCase, APITestMixin):
    """Test cases for /api/me endpoint"""

    def setUp(self):
        """Set up test fixtures"""
        # Create test role
        self.role = Role.objects.create(
            code="VT_TEST",
            name="Test Role",
            description="Test role description",
            is_system_role=False,
        )

        # Create test user with role
        self.user_with_role = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User",
            phone_number="+84901234567",
            role=self.role,
        )

        # Create test user without role
        self.user_without_role = User.objects.create_user(
            username="norole",
            email="norole@example.com",
            password="testpass123",
            first_name="No",
            last_name="Role",
        )

        # Create superuser
        self.superuser = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
            first_name="Admin",
            last_name="User",
        )

        self.client = APIClient()

    def test_get_me_authenticated_returns_user_profile(self):
        """Test GET /api/me returns authenticated user's profile"""
        self.client.force_authenticate(user=self.user_with_role)
        url = reverse("core:me")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        # Check user fields
        self.assertEqual(data["id"], self.user_with_role.id)
        self.assertEqual(data["username"], "testuser")
        self.assertEqual(data["email"], "test@example.com")
        self.assertEqual(data["phone_number"], "+84901234567")
        self.assertEqual(data["first_name"], "Test")
        self.assertEqual(data["last_name"], "User")
        self.assertEqual(data["full_name"], "User Test")
        self.assertTrue(data["is_active"])
        self.assertFalse(data["is_staff"])

        # Check role information
        self.assertIsNotNone(data["role"])
        self.assertEqual(data["role"]["code"], "VT_TEST")
        self.assertEqual(data["role"]["name"], "Test Role")

        # Check links
        self.assertIn("links", data)
        self.assertEqual(data["links"]["self"], "/api/me")

    def test_get_me_user_without_role(self):
        """Test GET /api/me for user without role"""
        self.client.force_authenticate(user=self.user_without_role)
        url = reverse("core:me")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        # Check basic user fields
        self.assertEqual(data["username"], "norole")
        self.assertEqual(data["email"], "norole@example.com")

        # Role should be None
        self.assertIsNone(data["role"])

        # Employee should be None
        self.assertIsNone(data["employee"])

    def test_get_me_unauthenticated_returns_401(self):
        """Test GET /api/me without authentication returns 401"""
        url = reverse("core:me")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_me_no_sensitive_fields(self):
        """Test that sensitive fields are not included in response"""
        self.client.force_authenticate(user=self.user_with_role)
        url = reverse("core:me")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        # Ensure sensitive fields are not exposed
        self.assertNotIn("password", data)
        self.assertNotIn("otp_code", data)
        self.assertNotIn("otp_expires_at", data)
        self.assertNotIn("active_session_key", data)
        self.assertNotIn("failed_login_attempts", data)
        self.assertNotIn("locked_until", data)


class MePermissionsAPITest(TestCase, APITestMixin):
    """Test cases for /api/me/permissions endpoint"""

    def setUp(self):
        """Set up test fixtures"""
        # Create test permissions
        self.perm1 = Permission.objects.create(
            code="document.create",
            description="Create documents",
        )
        self.perm2 = Permission.objects.create(
            code="document.update",
            description="Update documents",
        )
        self.perm3 = Permission.objects.create(
            code="document.delete",
            description="Delete documents",
        )

        # Create test role with permissions
        self.role = Role.objects.create(
            code="VT_EDITOR",
            name="Editor",
            description="Editor role",
            is_system_role=False,
        )
        self.role.permissions.set([self.perm1, self.perm2])

        # Create test user with role
        self.user_with_role = User.objects.create_user(
            username="editor",
            email="editor@example.com",
            password="testpass123",
            role=self.role,
        )

        # Create test user without role
        self.user_without_role = User.objects.create_user(
            username="norole",
            email="norole@example.com",
            password="testpass123",
        )

        # Create superuser
        self.superuser = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
        )

        self.client = APIClient()

    def test_get_me_permissions_user_with_role_returns_role_permissions(self):
        """Test GET /api/me/permissions returns permissions from user's role"""
        self.client.force_authenticate(user=self.user_with_role)
        url = reverse("core:me_permissions")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        # Check basic structure
        self.assertEqual(data["user_id"], self.user_with_role.id)
        self.assertEqual(data["username"], "editor")

        # Check role information
        self.assertIsNotNone(data["role"])
        self.assertEqual(data["role"]["code"], "VT_EDITOR")

        # Check permissions
        self.assertEqual(len(data["permissions"]), 2)
        permission_codes = [p["code"] for p in data["permissions"]]
        self.assertIn("document.create", permission_codes)
        self.assertIn("document.update", permission_codes)

        # Check metadata
        self.assertIn("meta", data)
        self.assertEqual(data["meta"]["count"], 2)
        self.assertIn("generated_at", data["meta"])

        # Check links
        self.assertIn("links", data)
        self.assertEqual(data["links"]["self"], "/api/me/permissions")

    def test_get_me_permissions_user_without_role_returns_empty(self):
        """Test GET /api/me/permissions for user without role returns empty list"""
        self.client.force_authenticate(user=self.user_without_role)
        url = reverse("core:me_permissions")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        # Check basic structure
        self.assertEqual(data["user_id"], self.user_without_role.id)
        self.assertEqual(data["username"], "norole")

        # Role should be None
        self.assertIsNone(data["role"])

        # Permissions should be empty
        self.assertEqual(len(data["permissions"]), 0)
        self.assertEqual(data["meta"]["count"], 0)

    def test_get_me_permissions_superuser_returns_all_permissions(self):
        """Test GET /api/me/permissions for superuser returns all permissions"""
        self.client.force_authenticate(user=self.superuser)
        url = reverse("core:me_permissions")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        # Check basic structure
        self.assertEqual(data["user_id"], self.superuser.id)
        self.assertEqual(data["username"], "admin")

        # Superuser should get all permissions
        all_permissions_count = Permission.objects.count()
        self.assertEqual(len(data["permissions"]), all_permissions_count)
        self.assertEqual(data["meta"]["count"], all_permissions_count)

        # Check all permission codes are present
        permission_codes = [p["code"] for p in data["permissions"]]
        self.assertIn("document.create", permission_codes)
        self.assertIn("document.update", permission_codes)
        self.assertIn("document.delete", permission_codes)

    def test_get_me_permissions_unauthenticated_returns_401(self):
        """Test GET /api/me/permissions without authentication returns 401"""
        url = reverse("core:me_permissions")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_me_permissions_with_query_params(self):
        """Test GET /api/me/permissions with query parameters"""
        self.client.force_authenticate(user=self.user_with_role)

        # Test include_role=false
        url = reverse("core:me_permissions") + "?include_role=false"
        response = self.client.get(url)
        data = self.get_response_data(response)
        self.assertIsNone(data["role"])

        # Test include_permission_meta=false
        url = reverse("core:me_permissions") + "?include_permission_meta=false"
        response = self.client.get(url)
        data = self.get_response_data(response)
        # Should have minimal permission info
        self.assertIn("permissions", data)
        if data["permissions"]:
            # Check that permissions have only id and code, not description
            self.assertIn("id", data["permissions"][0])
            self.assertIn("code", data["permissions"][0])
            self.assertNotIn("description", data["permissions"][0])

    def test_get_me_permissions_ordered_by_code(self):
        """Test that permissions are returned in alphabetical order by code"""
        self.client.force_authenticate(user=self.user_with_role)
        url = reverse("core:me_permissions")
        response = self.client.get(url)

        data = self.get_response_data(response)
        permission_codes = [p["code"] for p in data["permissions"]]

        # Check that permissions are sorted
        self.assertEqual(permission_codes, sorted(permission_codes))

    def test_query_count_optimization(self):
        """Test that the endpoint uses optimal number of queries"""
        self.client.force_authenticate(user=self.user_with_role)
        url = reverse("core:me_permissions")

        # Count queries
        with self.assertNumQueries(2):  # Should be just 2 query for permissions
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
