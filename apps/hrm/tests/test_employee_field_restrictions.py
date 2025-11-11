"""Tests for employee field update restrictions and return to work events."""

import json
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.hrm.models import Block, Branch, Department, Employee, EmployeeWorkHistory, Position

User = get_user_model()


class EmployeeFieldRestrictionsTest(TestCase):
    """Test cases for employee field update restrictions."""

    def setUp(self):
        """Set up test data."""
        from apps.core.models import AdministrativeUnit, Province

        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin_user)

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
        self.department2 = Department.objects.create(
            code="PB002",
            name="Another Department",
            branch=self.branch,
            block=self.block,
        )
        self.position = Position.objects.create(
            code="POS001",
            name="Test Position",
        )

        self.employee = Employee.objects.create(
            fullname="Test Employee",
            username="testuser001",
            email="testuser1@example.com",
            phone="1234567890",
            attendance_code="ATT001",
            date_of_birth=date(1990, 1, 1),
            start_date=date(2024, 1, 1),
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            status=Employee.Status.ACTIVE,
            citizen_id="000000010001",
        )

    def test_update_restricted_field_status_raises_error(self):
        """Test that updating status field raises validation error."""
        url = reverse("hrm:employee-detail", kwargs={"pk": self.employee.id})
        response = self.client.patch(
            url,
            {"status": Employee.Status.RESIGNED},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = json.loads(response.content)
        self.assertFalse(response_data["success"])
        self.assertIn("status", response_data["error"])
        self.assertIn("active/reactive/resigned/maternity_leave", str(response_data["error"]["status"]))

    def test_update_restricted_field_department_raises_error(self):
        """Test that updating department_id raises validation error."""
        url = reverse("hrm:employee-detail", kwargs={"pk": self.employee.id})
        response = self.client.patch(
            url,
            {"department_id": self.department2.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = json.loads(response.content)
        self.assertFalse(response_data["success"])
        self.assertIn("department", response_data["error"])
        self.assertIn("transfer", str(response_data["error"]["department"]))

    def test_update_restricted_field_position_raises_error(self):
        """Test that updating position_id raises validation error."""
        new_position = Position.objects.create(code="POS002", name="New Position")
        url = reverse("hrm:employee-detail", kwargs={"pk": self.employee.id})
        response = self.client.patch(
            url,
            {"position_id": new_position.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = json.loads(response.content)
        self.assertFalse(response_data["success"])
        self.assertIn("position", response_data["error"])
        self.assertIn("transfer", str(response_data["error"]["position"]))

    def test_update_allowed_fields_succeeds(self):
        """Test that updating allowed fields works."""
        url = reverse("hrm:employee-detail", kwargs={"pk": self.employee.id})
        response = self.client.patch(
            url,
            {
                "fullname": "Updated Name",
                "phone": "9876543210",
                "personal_email": "newemail@example.com",
                "note": "Updated note",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = json.loads(response.content)
        self.assertTrue(response_data["success"])
        
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.fullname, "Updated Name")
        self.assertEqual(self.employee.phone, "9876543210")
        self.assertEqual(self.employee.personal_email, "newemail@example.com")
        self.assertEqual(self.employee.note, "Updated note")

    def test_create_employee_with_all_fields_succeeds(self):
        """Test that creating a new employee with all fields works."""
        url = reverse("hrm:employee-list")
        response = self.client.post(
            url,
            {
                "fullname": "New Employee",
                "username": "newuser001",
                "email": "newuser@example.com",
                "phone": "5555555555",
                "attendance_code": "ATT002",
                "date_of_birth": "1995-05-05",
                "start_date": "2025-01-01",
                "department_id": self.department.id,
                "position_id": self.position.id,
                "status": Employee.Status.ONBOARDING,
                "citizen_id": "000000010002",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = json.loads(response.content)
        self.assertTrue(response_data["success"])


class EmployeeReturnToWorkEventTest(TestCase):
    """Test cases for return to work event creation."""

    def setUp(self):
        """Set up test data."""
        from apps.core.models import AdministrativeUnit, Province

        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin_user)

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

    def test_return_to_work_event_type_exists(self):
        """Test that RETURN_TO_WORK event type is available."""
        event_types = [choice[0] for choice in EmployeeWorkHistory.EventType.choices]
        self.assertIn("Return to Work", event_types)

    def test_reactive_resigned_employee_creates_return_to_work_event(self):
        """Test that reactivating resigned employee creates RETURN_TO_WORK event."""
        # Create resigned employee
        employee = Employee.objects.create(
            fullname="Resigned Employee",
            username="resigned001",
            email="resigned@example.com",
            phone="6666666666",
            attendance_code="RES001",
            date_of_birth=date(1988, 8, 8),
            start_date=date(2020, 1, 1),
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="000000010003",
        )
        # Set to resigned status
        employee.status = Employee.Status.RESIGNED
        employee.resignation_start_date = date(2024, 1, 1)
        employee.resignation_reason = Employee.ResignationReason.VOLUNTARY_PERSONAL
        employee.save(update_fields=["status", "resignation_start_date", "resignation_reason"])

        # Reactivate employee
        url = reverse("hrm:employee-reactive", kwargs={"pk": employee.id})
        response = self.client.post(
            url,
            {
                "start_date": "2025-01-15",
                "is_seniority_retained": True,
                "description": "Welcome back to the team",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        employee.refresh_from_db()
        self.assertEqual(employee.status, Employee.Status.ACTIVE)

        # Check for RETURN_TO_WORK event
        work_history = EmployeeWorkHistory.objects.filter(
            employee=employee,
            name=EmployeeWorkHistory.EventType.RETURN_TO_WORK,
        ).first()

        self.assertIsNotNone(work_history, "RETURN_TO_WORK event should be created")
        self.assertEqual(work_history.status, Employee.Status.ACTIVE)
        self.assertTrue(work_history.retain_seniority)
        self.assertEqual(work_history.date, date(2025, 1, 15))
        self.assertEqual(work_history.note, "Welcome back to the team")
        self.assertIn("returned to work", work_history.detail.lower())
        self.assertIn("seniority retained", work_history.detail.lower())
        
        # Check previous_data contains resignation details
        self.assertIsNotNone(work_history.previous_data)
        self.assertEqual(work_history.previous_data["status"], Employee.Status.RESIGNED)
        self.assertEqual(
            work_history.previous_data["resignation_reason"],
            Employee.ResignationReason.VOLUNTARY_PERSONAL,
        )

    def test_reactive_maternity_leave_creates_change_status_event(self):
        """Test that reactivating maternity leave employee creates CHANGE_STATUS event."""
        # Create maternity leave employee
        employee = Employee.objects.create(
            fullname="Maternity Leave Employee",
            username="maternity001",
            email="maternity@example.com",
            phone="7777777777",
            attendance_code="MAT001",
            date_of_birth=date(1990, 3, 15),
            start_date=date(2019, 6, 1),
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="000000010004",
        )
        # Set to maternity leave status
        employee.status = Employee.Status.MATERNITY_LEAVE
        employee.resignation_start_date = date(2024, 6, 1)
        employee.resignation_end_date = date(2024, 12, 1)
        employee.save(update_fields=["status", "resignation_start_date", "resignation_end_date"])

        # Reactivate employee
        url = reverse("hrm:employee-reactive", kwargs={"pk": employee.id})
        response = self.client.post(
            url,
            {
                "start_date": "2024-12-01",
                "is_seniority_retained": True,
                "description": "Returns from maternity leave",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        employee.refresh_from_db()
        self.assertEqual(employee.status, Employee.Status.ACTIVE)

        # Should NOT create RETURN_TO_WORK event
        return_to_work_count = EmployeeWorkHistory.objects.filter(
            employee=employee,
            name=EmployeeWorkHistory.EventType.RETURN_TO_WORK,
        ).count()
        self.assertEqual(return_to_work_count, 0, "Should not create RETURN_TO_WORK event for maternity leave")

        # Should create CHANGE_STATUS event instead
        change_status_event = EmployeeWorkHistory.objects.filter(
            employee=employee,
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            date=date(2024, 12, 1),
        ).first()

        self.assertIsNotNone(change_status_event, "Should create CHANGE_STATUS event")
        self.assertEqual(change_status_event.status, Employee.Status.ACTIVE)
        self.assertTrue(change_status_event.retain_seniority)
        self.assertIn("reactivated", change_status_event.detail.lower())

    def test_reactive_resigned_without_seniority_retained(self):
        """Test reactive resigned employee without seniority retained."""
        employee = Employee.objects.create(
            fullname="Another Resigned Employee",
            username="resigned002",
            email="resigned2@example.com",
            phone="8888888888",
            attendance_code="RES002",
            date_of_birth=date(1985, 5, 5),
            start_date=date(2018, 1, 1),
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="000000010005",
        )
        employee.status = Employee.Status.RESIGNED
        employee.resignation_start_date = date(2023, 12, 31)
        employee.resignation_reason = Employee.ResignationReason.VOLUNTARY_CAREER_CHANGE
        employee.save(update_fields=["status", "resignation_start_date", "resignation_reason"])

        url = reverse("hrm:employee-reactive", kwargs={"pk": employee.id})
        response = self.client.post(
            url,
            {
                "start_date": "2025-02-01",
                "is_seniority_retained": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        work_history = EmployeeWorkHistory.objects.filter(
            employee=employee,
            name=EmployeeWorkHistory.EventType.RETURN_TO_WORK,
        ).first()

        self.assertIsNotNone(work_history)
        self.assertFalse(work_history.retain_seniority)
        self.assertNotIn("seniority retained", work_history.detail.lower())
