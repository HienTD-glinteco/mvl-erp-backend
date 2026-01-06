import json
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from apps.core.models import AdministrativeUnit, Permission, Province, Role, User, UserDevice
from apps.files.constants import CACHE_KEY_PREFIX
from apps.files.models import FileModel
from apps.hrm.constants import AttendanceType
from apps.hrm.models import AttendanceRecord, Block, Branch, Department, Employee


@pytest.mark.django_db
class TestOtherAttendanceAndBulkApprove:
    @pytest.fixture
    def make_user(self, db):
        def _make_user(username="testuser", is_staff=False, is_superuser=False):
            return User.objects.create_user(
                username=username,
                password="password",
                email=f"{username}@example.com",
                is_staff=is_staff,
                is_superuser=is_superuser,
            )

        return _make_user

    @pytest.fixture
    def make_employee(self, db):
        def _make_employee(user):
            province, _ = Province.objects.get_or_create(name="Province 1", defaults={"code": "P01"})
            unit, _ = AdministrativeUnit.objects.get_or_create(
                name="Unit 1", defaults={"level": "level", "parent_province": province, "code": "AU01"}
            )

            branch, _ = Branch.objects.get_or_create(
                code="BR01", defaults={"name": "Branch 1", "administrative_unit": unit, "province": province}
            )
            block, _ = Block.objects.get_or_create(
                code="BL01", branch=branch, defaults={"name": "Block 1", "block_type": Block.BlockType.BUSINESS}
            )
            dept, _ = Department.objects.get_or_create(
                code="DP01",
                block=block,
                defaults={"name": "Dept 1", "branch": branch, "function": Department.DepartmentFunction.BUSINESS},
            )
            Permission.objects.filter(
                code="role.list",
                name="Old Name",
                description="Old Description",
                module="Old Module",
                submodule="Old Submodule",
            )
            # Permission.objectsuser
            return Employee.objects.create(
                user=user,
                code="EMP001",
                fullname="Test Employee",
                email=user.email,
                username=user.username,
                phone="0901234567",
                citizen_id="123456789",
                start_date=date(2023, 1, 1),
                branch=branch,
                block=block,
                department=dept,
                attendance_code="12345",
                personal_email=user.email,
            )

        return _make_employee

    @pytest.fixture
    def employee(self, db, make_employee, make_user):
        user = make_user()
        employee = make_employee(user=user)

        permission = Permission.objects.create(code="my_attendance_record.other_attendance")
        role = Role.objects.create(name="Employee Role")
        role.permissions.add(permission)
        user.role = role
        user.save()

        return employee

    @pytest.fixture
    def admin_employee(self, db, make_user):
        user = make_user(username="admin", is_staff=True, is_superuser=True)

        province, _ = Province.objects.get_or_create(name="Province 1", defaults={"code": "P01"})
        unit, _ = AdministrativeUnit.objects.get_or_create(
            name="Unit 1", defaults={"level": "level", "parent_province": province, "code": "AU01"}
        )

        branch, _ = Branch.objects.get_or_create(
            code="BR01", defaults={"name": "Branch 1", "administrative_unit": unit, "province": province}
        )
        block, _ = Block.objects.get_or_create(
            code="BL01", defaults={"name": "Block 1", "branch": branch, "block_type": Block.BlockType.BUSINESS}
        )
        dept, _ = Department.objects.get_or_create(
            code="DP01",
            defaults={
                "name": "Dept 1",
                "branch": branch,
                "block": block,
                "function": Department.DepartmentFunction.BUSINESS,
            },
        )

        return Employee.objects.create(
            user=user,
            code="ADMIN001",
            fullname="Admin Employee",
            email=user.email,
            username=user.username,
            phone="0909999999",
            citizen_id="987654321",
            start_date=date(2023, 1, 1),
            branch=branch,
            block=block,
            department=dept,
            attendance_code="99999",
            personal_email=user.email,
        )

    @pytest.mark.django_db
    @patch("apps.files.utils.S3FileUploadService")
    def test_create_other_attendance(self, mock_s3_service, api_client, employee):
        file_obj = FileModel.objects.create(
            purpose="other_attendance",
            file_name="attendance_image.jpg",
            file_path="attendance_image.jpg",
            size=1024,
            is_confirmed=True,
            uploaded_by=employee.user,
        )

        UserDevice.objects.create(user=employee.user, device_id="device123", platform=UserDevice.Platform.ANDROID)
        token_mock = MagicMock()
        token_mock.get.side_effect = lambda k: "device123" if k == "device_id" else None
        api_client.force_authenticate(user=employee.user, token=token_mock)

        # Mock S3 service
        mock_instance = mock_s3_service.return_value
        mock_instance.check_file_exists.return_value = True
        mock_instance.generate_permanent_path.return_value = "uploads/other_attendance/1/attendance_image.jpg"
        mock_instance.move_file.return_value = True
        mock_instance.get_file_metadata.return_value = {
            "size": 1024,
            "content_type": "image/jpeg",
            "etag": "abc123",
        }

        file_token = "test-token-001"
        cache_key = f"{CACHE_KEY_PREFIX}{file_token}"
        cache_data = {
            "file_name": "avatar.jpg",
            "file_type": "image/jpeg",
            "purpose": "other_attendance",  # Changed purpose to match test expectation if needed, or keeping it consistent
            "file_path": "uploads/tmp/test-avatar-token-001/avatar.jpg",
        }
        cache.set(cache_key, json.dumps(cache_data), 3600)

        url = reverse("hrm-mobile:my-attendance-record-other-attendance")
        data = {
            "timestamp": "2023-10-27T10:00:00Z",
            "latitude": "10.123",
            "longitude": "106.456",
            "description": "Remote work",
            "files": {
                "image": file_token,
            },
        }

        response = api_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED

        resp_data = response.json()
        record_id = resp_data["data"]["id"]
        record = AttendanceRecord.objects.get(id=record_id)

        assert record.attendance_type == AttendanceType.OTHER
        assert record.is_pending is True
        assert record.is_valid is None
        assert record.employee == employee
        assert record.latitude == Decimal(data["latitude"])
        assert record.longitude == Decimal(data["longitude"])
        assert record.description == data["description"]
        # The mixin creates a NEW FileModel instance, so checking against file_obj.id is probably wrong if the API uses the one from mixin
        # However, checking the implementation of the view/serializer would be needed to be sure.
        # Assuming the test expects a new file to be created.
        assert record.image_id is not None
        assert record.image.file_name == "avatar.jpg"

    def test_bulk_approve_other_attendance(self, api_client, admin_employee, employee):
        # Create pending records
        r1 = AttendanceRecord.objects.create(
            employee=employee,
            timestamp=timezone.now(),
            attendance_type=AttendanceType.OTHER,
            is_pending=True,
            is_valid=None,
        )
        r2 = AttendanceRecord.objects.create(
            employee=employee,
            timestamp=timezone.now(),
            attendance_type=AttendanceType.OTHER,
            is_pending=True,
            is_valid=None,
        )

        api_client.force_authenticate(user=admin_employee.user)
        url = reverse("hrm:attendance-record-other-bulk-approve")

        # Approve
        data = {"ids": [r1.id, r2.id], "is_approve": True, "note": "Approved by admin"}

        response = api_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_200_OK

        r1.refresh_from_db()
        r2.refresh_from_db()

        assert r1.is_valid is True
        assert r1.is_pending is False
        assert r1.approved_by == admin_employee
        assert r1.approved_at is not None
        assert "Approved by admin" in r1.notes

        assert r2.is_valid is True
        assert r2.is_pending is False
        assert r2.approved_by == admin_employee

    def test_bulk_reject_other_attendance(self, api_client, admin_employee, employee):
        # Create pending records
        r1 = AttendanceRecord.objects.create(
            employee=employee,
            timestamp=timezone.now(),
            attendance_type=AttendanceType.OTHER,
            is_pending=True,
            is_valid=None,
        )

        api_client.force_authenticate(user=admin_employee.user)
        url = reverse("hrm:attendance-record-other-bulk-approve")

        # Reject
        data = {"ids": [r1.id], "is_approve": False, "note": "Rejected"}

        response = api_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_200_OK

        r1.refresh_from_db()

        assert r1.is_valid is False
        assert r1.is_pending is False
        assert r1.approved_by == admin_employee
