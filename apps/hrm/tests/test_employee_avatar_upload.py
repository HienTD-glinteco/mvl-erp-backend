"""Tests for employee avatar upload feature."""

import json
from datetime import date
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.files.constants import CACHE_KEY_PREFIX
from apps.files.models import FileModel
from apps.hrm.models import Block, Branch, Department, Employee

User = get_user_model()


class EmployeeAvatarUploadTest(TestCase):
    """Test cases for employee avatar upload endpoint"""

    def setUp(self):
        """Set up test data"""
        from apps.core.models import AdministrativeUnit, Province

        # Clear cache and file records
        cache.clear()
        FileModel.objects.all().delete()

        # Changed to superuser to bypass RoleBasedPermission for API tests
        self.admin_user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="testpass123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin_user)

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

        # Create test employee
        self.employee = Employee.objects.create(
            fullname="Test Employee",
            username="testemployee",
            email="employee@example.com",
            phone="1234567890",
            attendance_code="EMP001",
            date_of_birth=date(1990, 1, 1),
            start_date=date(2024, 1, 1),
            branch=self.branch,
            block=self.block,
            department=self.department,
            status=Employee.Status.ACTIVE,
            citizen_id="000000010001",
        )

        # Set up file token in cache
        self.file_token = "test-avatar-token-001"
        cache_key = f"{CACHE_KEY_PREFIX}{self.file_token}"
        cache_data = {
            "file_name": "avatar.jpg",
            "file_type": "image/jpeg",
            "purpose": "employee_avatar",
            "file_path": "uploads/tmp/test-avatar-token-001/avatar.jpg",
        }
        cache.set(cache_key, json.dumps(cache_data), 3600)

    def tearDown(self):
        """Clean up after tests"""
        cache.clear()

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    @patch("apps.files.utils.S3FileUploadService")
    def test_update_avatar_success(self, mock_s3_service_class, mock_s3_utils):
        """Test successful avatar upload"""
        # Mock S3FileUploadService instance
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance
        mock_s3_utils.return_value = mock_s3_instance

        # Mock S3 methods used by the file confirmation mixin
        mock_s3_instance.check_file_exists.return_value = True
        mock_s3_instance.get_file_metadata.return_value = {
            "content_type": "image/jpeg",
            "size": 50000,
        }
        mock_s3_instance.move_file.return_value = None
        mock_s3_instance.generate_permanent_path.return_value = "uploads/employee_avatar/1/avatar.jpg"
        mock_s3_instance.generate_view_url.return_value = "https://example.com/view/avatar.jpg"
        mock_s3_instance.generate_download_url.return_value = "https://example.com/download/avatar.jpg"

        # Make request
        url = reverse("hrm:employee-update-avatar", kwargs={"pk": self.employee.id})
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
        self.assertEqual(self.employee.avatar.file_name, "avatar.jpg")
        self.assertTrue(self.employee.avatar.is_confirmed)

        # Verify response contains avatar data
        response_data = response.json()
        self.assertIn("data", response_data)
        self.assertIn("avatar", response_data["data"])
        # Avatar can be returned as full object or just ID depending on serializer
        # We verify the database has the correct data
        if isinstance(response_data["data"]["avatar"], dict):
            self.assertEqual(response_data["data"]["avatar"]["id"], self.employee.avatar.id)
        else:
            self.assertEqual(response_data["data"]["avatar"], self.employee.avatar.id)

        # Verify cache was cleared
        cache_key = f"{CACHE_KEY_PREFIX}{self.file_token}"
        self.assertIsNone(cache.get(cache_key))

    def test_update_avatar_invalid_token(self):
        """Test avatar upload with invalid file token"""
        # No need to mock S3 - should fail at validation before S3 calls
        url = reverse("hrm:employee-update-avatar", kwargs={"pk": self.employee.id})
        payload = {
            "files": {
                "avatar": "invalid-token",
            }
        }

        # Patch S3 service to avoid initialization errors
        with patch("apps.files.utils.S3FileUploadService"):
            response = self.client.post(url, payload, format="json")

        # Should return 400 Bad Request
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Employee avatar should remain None
        self.employee.refresh_from_db()
        self.assertIsNone(self.employee.avatar)

    @patch("apps.files.utils.S3FileUploadService")
    def test_update_avatar_file_not_found_in_s3(self, mock_s3_service_class):
        """Test avatar upload when file doesn't exist in S3"""
        # Mock S3FileUploadService instance
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance

        # Mock that file doesn't exist in S3
        mock_s3_instance.check_file_exists.return_value = False

        url = reverse("hrm:employee-update-avatar", kwargs={"pk": self.employee.id})
        payload = {
            "files": {
                "avatar": self.file_token,
            }
        }
        response = self.client.post(url, payload, format="json")

        # Should return 400 Bad Request
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Employee avatar should remain None
        self.employee.refresh_from_db()
        self.assertIsNone(self.employee.avatar)

    @patch("apps.files.utils.S3FileUploadService")
    def test_update_avatar_wrong_content_type(self, mock_s3_service_class):
        """Test avatar upload with wrong content type (e.g., PDF instead of image)"""
        # Mock S3FileUploadService instance
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance

        # Mock S3 operations - file exists but has wrong content type
        mock_s3_instance.check_file_exists.return_value = True
        mock_s3_instance.get_file_metadata.return_value = {
            "content_type": "application/pdf",  # Wrong type
            "size": 50000,
        }

        url = reverse("hrm:employee-update-avatar", kwargs={"pk": self.employee.id})
        payload = {
            "files": {
                "avatar": self.file_token,
            }
        }
        response = self.client.post(url, payload, format="json")

        # Should return 400 Bad Request
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Employee avatar should remain None
        self.employee.refresh_from_db()
        self.assertIsNone(self.employee.avatar)

        # Verify file was deleted from S3
        mock_s3_instance.delete_file.assert_called_once()

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    @patch("apps.files.utils.S3FileUploadService")
    def test_update_avatar_replaces_existing(self, mock_s3_service_class, mock_s3_utils):
        """Test that uploading a new avatar replaces the old one"""
        # Create an existing avatar
        old_avatar = FileModel.objects.create(
            purpose="employee_avatar",
            file_name="old_avatar.jpg",
            file_path="uploads/employee_avatar/1/old_avatar.jpg",
            size=40000,
            is_confirmed=True,
            uploaded_by=self.admin_user,
        )
        self.employee.avatar = old_avatar
        self.employee.save(update_fields=["avatar"])

        # Mock S3FileUploadService instance
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance
        mock_s3_utils.return_value = mock_s3_instance

        # Mock S3 methods
        mock_s3_instance.check_file_exists.return_value = True
        mock_s3_instance.get_file_metadata.return_value = {
            "content_type": "image/jpeg",
            "size": 50000,
        }
        mock_s3_instance.move_file.return_value = None
        mock_s3_instance.generate_permanent_path.return_value = "uploads/employee_avatar/1/avatar.jpg"
        mock_s3_instance.generate_view_url.return_value = "https://example.com/view/avatar.jpg"
        mock_s3_instance.generate_download_url.return_value = "https://example.com/download/avatar.jpg"

        # Upload new avatar
        url = reverse("hrm:employee-update-avatar", kwargs={"pk": self.employee.id})
        payload = {
            "files": {
                "avatar": self.file_token,
            }
        }
        response = self.client.post(url, payload, format="json")

        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify employee has new avatar
        self.employee.refresh_from_db()
        self.assertIsNotNone(self.employee.avatar)
        self.assertNotEqual(self.employee.avatar.id, old_avatar.id)
        self.assertEqual(self.employee.avatar.file_name, "avatar.jpg")

    def test_update_avatar_employee_not_found(self):
        """Test avatar upload for non-existent employee"""
        url = reverse("hrm:employee-update-avatar", kwargs={"pk": 99999})
        payload = {
            "files": {
                "avatar": self.file_token,
            }
        }
        response = self.client.post(url, payload, format="json")

        # Should return 404 Not Found
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_avatar_unauthenticated(self):
        """Test that unauthenticated users cannot upload avatars"""
        # Create unauthenticated client
        unauthenticated_client = APIClient()

        url = reverse("hrm:employee-update-avatar", kwargs={"pk": self.employee.id})
        payload = {
            "files": {
                "avatar": self.file_token,
            }
        }
        response = unauthenticated_client.post(url, payload, format="json")

        # Should return 401 Unauthorized
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
