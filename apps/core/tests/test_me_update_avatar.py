"""Tests for /me/update-avatar/ endpoint."""

import json
from datetime import date
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.files.constants import CACHE_KEY_PREFIX
from apps.files.models import FileModel
from apps.hrm.models import Block, Branch, Department, Employee

User = get_user_model()


@override_settings(
    AWS_ACCESS_KEY_ID="test-key",
    AWS_SECRET_ACCESS_KEY="test-secret",
    AWS_REGION_NAME="us-east-1",
    AWS_STORAGE_BUCKET_NAME="test-bucket",
    AWS_LOCATION="",
)
class MeUpdateAvatarTest(TestCase):
    """Test cases for /me/update-avatar/ endpoint"""

    def setUp(self):
        """Set up test data"""
        from apps.core.models import AdministrativeUnit, Province

        # Clear cache and file records
        cache.clear()
        FileModel.objects.all().delete()

        # Create organizational structure
        self.province = Province.objects.create(code="01", name="Test Province")
        self.admin_unit = AdministrativeUnit.objects.create(
            code="01",
            name="Test Admin Unit",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )

        self.branch = Branch.objects.create(
            code="CN001",
            name="Test Branch",
            province=self.province,
            administrative_unit=self.admin_unit,
        )
        self.block = Block.objects.create(
            code="KH001",
            name="Test Block",
            branch=self.branch,
            block_type=Block.BlockType.BUSINESS,
        )
        self.department = Department.objects.create(
            code="PB001",
            name="Test Department",
            branch=self.branch,
            block=self.block,
        )

        # Create user with employee
        # Changed to superuser to bypass RoleBasedPermission for API tests
        self.user = User.objects.create_superuser(
            username="testuser",
            email="testuser@example.com",
            password="testpass123",
        )
        self.employee = Employee.objects.create(
            fullname="Test User",
            username="testuser",
            email="testuser@example.com",
            phone="1234567890",
            attendance_code="USR001",
            date_of_birth=date(1990, 1, 1),
            start_date=date(2024, 1, 1),
            branch=self.branch,
            block=self.block,
            department=self.department,
            status=Employee.Status.ACTIVE,
            citizen_id="000000010001",
            user=self.user,
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Set up file token in cache
        self.file_token = "test-avatar-token-me-001"
        cache_key = f"{CACHE_KEY_PREFIX}{self.file_token}"
        cache_data = {
            "file_name": "my_avatar.jpg",
            "file_type": "image/jpeg",
            "purpose": "employee_avatar",
            "file_path": "uploads/tmp/test-avatar-token-me-001/my_avatar.jpg",
        }
        cache.set(cache_key, json.dumps(cache_data), 3600)

    def tearDown(self):
        """Clean up after tests"""
        cache.clear()

    @patch("apps.files.utils.S3FileUploadService")
    def test_me_update_avatar_success(self, mock_s3_service_class):
        """Test successful avatar upload for current user"""
        # Mock S3FileUploadService instance
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance

        # Mock S3 methods used by the file confirmation mixin
        mock_s3_instance.check_file_exists.return_value = True
        mock_s3_instance.get_file_metadata.return_value = {
            "content_type": "image/jpeg",
            "size": 50000,
        }
        mock_s3_instance.move_file.return_value = None
        mock_s3_instance.generate_permanent_path.return_value = "uploads/employee_avatar/1/my_avatar.jpg"
        mock_s3_instance.generate_view_url.return_value = "https://example.com/view/my_avatar.jpg"
        mock_s3_instance.generate_download_url.return_value = "https://example.com/download/my_avatar.jpg"

        # Make request
        url = reverse("core:me_update_avatar")
        payload = {
            "files": {
                "avatar": self.file_token,
            }
        }
        response = self.client.post(url, payload, format="json")

        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify employee was updated with avatar
        self.employee.refresh_from_db()
        self.assertIsNotNone(self.employee.avatar)
        self.assertEqual(self.employee.avatar.purpose, "employee_avatar")
        self.assertEqual(self.employee.avatar.file_name, "my_avatar.jpg")
        self.assertTrue(self.employee.avatar.is_confirmed)

        # Verify response contains avatar data in employee
        response_data = response.json()
        self.assertIn("data", response_data)
        self.assertIn("employee", response_data["data"])
        self.assertIn("avatar", response_data["data"]["employee"])
        self.assertIsNotNone(response_data["data"]["employee"]["avatar"])
        self.assertEqual(
            response_data["data"]["employee"]["avatar"]["file_name"],
            "my_avatar.jpg",
        )

        # Verify cache was cleared
        cache_key = f"{CACHE_KEY_PREFIX}{self.file_token}"
        self.assertIsNone(cache.get(cache_key))

    def test_me_update_avatar_unauthenticated(self):
        """Test that unauthenticated users cannot upload avatars"""
        # Create unauthenticated client
        unauthenticated_client = APIClient()

        url = reverse("core:me_update_avatar")
        payload = {
            "files": {
                "avatar": self.file_token,
            }
        }
        response = unauthenticated_client.post(url, payload, format="json")

        # Should return 401 Unauthorized
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_update_avatar_no_employee(self):
        """Test that users without employee record get 404"""
        # Create user without employee
        user_no_employee = User.objects.create_superuser(
            username="noemployee",
            email="noemployee@example.com",
            password="testpass123",
        )
        client = APIClient()
        client.force_authenticate(user=user_no_employee)

        url = reverse("core:me_update_avatar")
        payload = {
            "files": {
                "avatar": self.file_token,
            }
        }
        response = client.post(url, payload, format="json")

        # Should return 404 Not Found
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch("apps.files.utils.S3FileUploadService")
    def test_me_update_avatar_invalid_token(self, mock_s3_service_class):
        """Test avatar upload with invalid file token"""
        # Mock S3FileUploadService instance (though it won't be used for invalid token)
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance

        url = reverse("core:me_update_avatar")
        payload = {
            "files": {
                "avatar": "invalid-token",
            }
        }
        response = self.client.post(url, payload, format="json")

        # Should return 400 Bad Request
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Employee avatar should remain None
        self.employee.refresh_from_db()
        self.assertIsNone(self.employee.avatar)
