
import pytest
from django.urls import reverse
from rest_framework import status
from apps.hrm.models import AttendanceRecord
from apps.hrm.constants import AttendanceType

@pytest.mark.django_db
class TestOtherAttendanceAndBulkApprove:

    @pytest.fixture
    def make_user(self, db):
        from apps.core.models import User
        def _make_user(username="testuser", is_staff=False, is_superuser=False):
            return User.objects.create_user(
                username=username,
                password="password",
                email=f"{username}@example.com",
                is_staff=is_staff,
                is_superuser=is_superuser
            )
        return _make_user

    @pytest.fixture
    def make_employee(self, db):
        from apps.hrm.models import Employee, Branch, Block, Department
        from apps.core.models import Province, AdministrativeUnit
        from datetime import date
        from django.utils import timezone

        def _make_employee(user):
            province, _ = Province.objects.get_or_create(name="Province 1", defaults={"code": "P01"})
            unit, _ = AdministrativeUnit.objects.get_or_create(
                name="Unit 1",
                defaults={
                    "level": "level",
                    "parent_province": province,
                    "code": "AU01"
                }
            )

            branch, _ = Branch.objects.get_or_create(
                code="BR01",
                defaults={
                    "name": "Branch 1",
                    "administrative_unit": unit,
                    "province": province
                }
            )
            block, _ = Block.objects.get_or_create(
                code="BL01",
                branch=branch,
                defaults={
                    "name": "Block 1",
                    "block_type": Block.BlockType.BUSINESS
                }
            )
            dept, _ = Department.objects.get_or_create(
                code="DP01",
                block=block,
                defaults={
                    "name": "Dept 1",
                    "branch": branch,
                    "function": Department.DepartmentFunction.BUSINESS
                }
            )

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
                attendance_code="12345"
            )
        return _make_employee

    @pytest.fixture
    def employee(self, db, make_employee, make_user):
        user = make_user()
        employee = make_employee(user=user)
        return employee

    @pytest.fixture
    def admin_employee(self, db, make_employee, make_user):
        user = make_user(username="admin", is_staff=True, is_superuser=True)
        from apps.hrm.models import Employee, Branch, Block, Department
        from apps.core.models import Province, AdministrativeUnit
        from datetime import date

        province, _ = Province.objects.get_or_create(name="Province 1", defaults={"code": "P01"})
        unit, _ = AdministrativeUnit.objects.get_or_create(
            name="Unit 1",
            defaults={
                "level": "level",
                "parent_province": province,
                "code": "AU01"
            }
        )

        branch, _ = Branch.objects.get_or_create(
            code="BR01",
            defaults={
                "name": "Branch 1",
                "administrative_unit": unit,
                "province": province
            }
        )
        block, _ = Block.objects.get_or_create(
            code="BL01",
            defaults={
                "name": "Block 1",
                "branch": branch,
                "block_type": Block.BlockType.BUSINESS
            }
        )
        dept, _ = Department.objects.get_or_create(
            code="DP01",
            defaults={
                "name": "Dept 1",
                "branch": branch,
                "block": block,
                "function": Department.DepartmentFunction.BUSINESS
            }
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
            attendance_code="99999"
        )

    def test_create_other_attendance(self, api_client, employee):
        api_client.force_authenticate(user=employee.user)
        url = reverse("hrm:attendance-record-other-attendance")
        data = {
            "timestamp": "2023-10-27T10:00:00Z",
            "notes": "Remote work",
            "latitude": "10.123",
            "longitude": "106.456"
        }

        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED

        record_id = response.data["id"]
        record = AttendanceRecord.objects.get(id=record_id)

        assert record.attendance_type == AttendanceType.OTHER
        assert record.is_pending is True
        assert record.is_valid is None
        assert record.employee == employee
        assert record.notes == "Remote work"

    def test_bulk_approve_attendance(self, api_client, admin_employee, employee):
        from django.utils import timezone
        # Create pending records
        r1 = AttendanceRecord.objects.create(
            employee=employee,
            timestamp=timezone.now(),
            attendance_type=AttendanceType.OTHER,
            is_pending=True,
            is_valid=None
        )
        r2 = AttendanceRecord.objects.create(
            employee=employee,
            timestamp=timezone.now(),
            attendance_type=AttendanceType.OTHER,
            is_pending=True,
            is_valid=None
        )

        api_client.force_authenticate(user=admin_employee.user)
        url = reverse("hrm:attendance-record-bulk-approve")

        # Approve
        data = {
            "ids": [r1.id, r2.id],
            "is_approve": True,
            "note": "Approved by admin"
        }

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

    def test_bulk_reject_attendance(self, api_client, admin_employee, employee):
        from django.utils import timezone
        # Create pending records
        r1 = AttendanceRecord.objects.create(
            employee=employee,
            timestamp=timezone.now(),
            attendance_type=AttendanceType.OTHER,
            is_pending=True,
            is_valid=None
        )

        api_client.force_authenticate(user=admin_employee.user)
        url = reverse("hrm:attendance-record-bulk-approve")

        # Reject
        data = {
            "ids": [r1.id],
            "is_approve": False,
            "note": "Rejected"
        }

        response = api_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_200_OK

        r1.refresh_from_db()

        assert r1.is_valid is False
        assert r1.is_pending is False
        assert r1.approved_by == admin_employee
