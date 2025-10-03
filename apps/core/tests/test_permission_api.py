import json

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import Permission

User = get_user_model()


class APITestMixin:
    """Mixin to handle wrapped API responses and data extraction"""

    def get_response_data(self, response):
        """Extract data from wrapped API response"""
        content = json.loads(response.content.decode())
        if "data" in content:
            return content["data"]
        return content


class PermissionAPITest(TransactionTestCase, APITestMixin):
    """Test cases for Permission API endpoints"""

    def setUp(self):
        # Clear all existing data for clean tests
        Permission.objects.all().delete()
        User.objects.all().delete()

        # Create test permissions
        self.perm1 = Permission.objects.create(code="view_users", description="View users")
        self.perm2 = Permission.objects.create(code="edit_users", description="Edit users")
        self.perm3 = Permission.objects.create(code="delete_users", description="Delete users")
        self.perm4 = Permission.objects.create(code="view_reports", description="View reports")

        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_list_permissions(self):
        """Test listing permissions via API"""
        url = reverse("core:permission-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 4)

    def test_retrieve_permission(self):
        """Test retrieving a permission via API"""
        url = reverse("core:permission-detail", kwargs={"pk": self.perm1.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(response_data["code"], self.perm1.code)
        self.assertEqual(response_data["description"], self.perm1.description)

    def test_search_permission_by_code(self):
        """Test searching permissions by code"""
        url = reverse("core:permission-list")
        response = self.client.get(url, {"search": "view"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        codes = [p["code"] for p in response_data]
        self.assertIn("view_users", codes)
        self.assertIn("view_reports", codes)
        self.assertNotIn("edit_users", codes)
        self.assertNotIn("delete_users", codes)

    def test_filter_permission_by_code(self):
        """Test filtering permissions by code (case-insensitive)"""
        url = reverse("core:permission-list")
        response = self.client.get(url, {"code": "edit"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]["code"], "edit_users")

    def test_filter_permission_by_description(self):
        """Test filtering permissions by description"""
        url = reverse("core:permission-list")
        response = self.client.get(url, {"description": "users"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        self.assertEqual(len(response_data), 3)  # view_users, edit_users, delete_users

    def test_ordering_permissions(self):
        """Test ordering permissions by code"""
        url = reverse("core:permission-list")
        response = self.client.get(url, {"ordering": "code"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = self.get_response_data(response)
        codes = [p["code"] for p in response_data]
        self.assertEqual(codes, sorted(codes))

    def test_permission_api_readonly(self):
        """Test that permission API is read-only (no create/update/delete)"""
        url = reverse("core:permission-list")

        # Try to create
        create_response = self.client.post(
            url, {"code": "new_permission", "description": "New permission"}, format="json"
        )
        self.assertEqual(create_response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # Try to update
        update_url = reverse("core:permission-detail", kwargs={"pk": self.perm1.pk})
        update_response = self.client.patch(update_url, {"description": "Updated"}, format="json")
        self.assertEqual(update_response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # Try to delete
        delete_response = self.client.delete(update_url)
        self.assertEqual(delete_response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
