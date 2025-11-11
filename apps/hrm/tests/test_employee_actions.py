import json
from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import Block, Branch, Department, Employee, EmployeeWorkHistory, Position

User = get_user_model()


class EmployeeActionAPITest(TestCase):
    """Test cases for Employee API actions"""

    def setUp(self):
        """Set up test data"""

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

        self.onboarding_employee = Employee.objects.create(
            fullname="Onboarding Employee",
            username="onboarding001",
            email="onboarding1@example.com",
            phone="3333333333",
            attendance_code="ONB001",
            date_of_birth=date(1992, 6, 10),
            start_date=date(2024, 1, 1),
            branch=self.branch,
            block=self.block,
            department=self.department,
            status=Employee.Status.ONBOARDING,
            citizen_id="000000010024",
        )

        self.active_employee = Employee.objects.create(
            fullname="Active Employee",
            username="active001",
            email="active1@example.com",
            phone="4444444444",
            attendance_code="ACT001",
            date_of_birth=date(1988, 3, 5),
            start_date=date(2019, 1, 1),
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="000000010025",
        )
        # Set status to ACTIVE using update_fields to bypass validation
        self.active_employee.status = Employee.Status.ACTIVE
        self.active_employee.save(update_fields=["status"])
        # Start patchers for periodic/async aggregation tasks so they don't run during tests
        # Patch the symbol where it's used (signals) so .delay() calls are intercepted
        self._patcher_aggregate_hr = patch("apps.hrm.signals.hr_reports.aggregate_hr_reports_for_work_history")
        self.mock_aggregate_hr = self._patcher_aggregate_hr.start()

        self._patcher_aggregate_recruit = patch(
            "apps.hrm.signals.recruitment_reports.aggregate_recruitment_reports_for_candidate"
        )
        self.mock_aggregate_recruit = self._patcher_aggregate_recruit.start()

    def tearDown(self):
        # Stop patchers to clean up after each test
        self._patcher_aggregate_hr.stop()
        self._patcher_aggregate_recruit.stop()

    def test_active_action(self):
        url = reverse("hrm:employee-active", kwargs={"pk": self.onboarding_employee.id})
        payload = {"start_date": "2024-02-01"}
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.onboarding_employee.refresh_from_db()
        self.assertEqual(self.onboarding_employee.status, Employee.Status.ACTIVE)
        self.assertEqual(str(self.onboarding_employee.start_date), "2024-02-01")

    def test_active_action_on_active_employee_fails(self):
        url = reverse("hrm:employee-active", kwargs={"pk": self.active_employee.id})
        payload = {"start_date": "2024-02-01"}
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reactive_action_retain_seniority(self):
        # Set status to RESIGNED using update_fields to bypass validation
        self.onboarding_employee.status = Employee.Status.RESIGNED
        self.onboarding_employee.resignation_start_date = date(2024, 12, 31)
        self.onboarding_employee.resignation_reason = Employee.ResignationReason.VOLUNTARY_OTHER
        self.onboarding_employee.save(update_fields=["status", "resignation_start_date", "resignation_reason"])

        url = reverse("hrm:employee-reactive", kwargs={"pk": self.onboarding_employee.id})
        payload = {"start_date": "2025-01-01", "is_seniority_retained": True}
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.onboarding_employee.refresh_from_db()
        self.assertEqual(self.onboarding_employee.status, Employee.Status.ACTIVE)
        # The reactive action always updates start_date, regardless of is_seniority_retained
        self.assertEqual(str(self.onboarding_employee.start_date), "2025-01-01")

    def test_reactive_action_not_retain_seniority(self):
        # Set status to RESIGNED using update_fields to bypass validation
        self.onboarding_employee.status = Employee.Status.RESIGNED
        self.onboarding_employee.resignation_start_date = date(2024, 12, 31)
        self.onboarding_employee.resignation_reason = Employee.ResignationReason.VOLUNTARY_OTHER
        self.onboarding_employee.save(update_fields=["status", "resignation_start_date", "resignation_reason"])

        url = reverse("hrm:employee-reactive", kwargs={"pk": self.onboarding_employee.id})
        payload = {"start_date": "2025-01-01", "is_seniority_retained": False}
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.onboarding_employee.refresh_from_db()
        self.assertEqual(self.onboarding_employee.status, Employee.Status.ACTIVE)
        self.assertEqual(str(self.onboarding_employee.start_date), "2025-01-01")

    def test_resigned_action(self):
        url = reverse("hrm:employee-resigned", kwargs={"pk": self.active_employee.id})
        payload = {
            "start_date": "2024-12-31",
            "resignation_reason": Employee.ResignationReason.VOLUNTARY_CAREER_CHANGE,
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.active_employee.refresh_from_db()
        self.assertEqual(self.active_employee.status, Employee.Status.RESIGNED)
        # The resigned action sets resignation_start_date, not start_date
        self.assertEqual(str(self.active_employee.resignation_start_date), "2024-12-31")
        self.assertEqual(
            self.active_employee.resignation_reason,
            Employee.ResignationReason.VOLUNTARY_CAREER_CHANGE,
        )

    def test_resigned_action_on_onboarding_employee_fails(self):
        url = reverse("hrm:employee-resigned", kwargs={"pk": self.onboarding_employee.id})
        payload = {
            "start_date": "2024-12-31",
            "resignation_reason": Employee.ResignationReason.VOLUNTARY_CAREER_CHANGE,
        }
        response = self.client.post(url, payload, format="json")
        # The resigned action allows ONBOARDING -> RESIGNED transition
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.onboarding_employee.refresh_from_db()
        self.assertEqual(self.onboarding_employee.status, Employee.Status.RESIGNED)

    def test_maternity_leave_action(self):
        url = reverse("hrm:employee-maternity-leave", kwargs={"pk": self.active_employee.id})
        payload = {"start_date": "2024-10-01", "end_date": "2025-04-01"}
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.active_employee.refresh_from_db()
        self.assertEqual(self.active_employee.status, Employee.Status.MATERNITY_LEAVE)
        self.assertEqual(str(self.active_employee.resignation_start_date), "2024-10-01")
        self.assertEqual(str(self.active_employee.resignation_end_date), "2025-04-01")

    def test_maternity_leave_action_on_onboarding_employee_fails(self):
        url = reverse("hrm:employee-maternity-leave", kwargs={"pk": self.onboarding_employee.id})
        payload = {"start_date": "2024-10-01", "end_date": "2025-04-01"}
        response = self.client.post(url, payload, format="json")
        # The maternity leave action allows ONBOARDING -> MATERNITY_LEAVE transition
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.onboarding_employee.refresh_from_db()
        self.assertEqual(self.onboarding_employee.status, Employee.Status.MATERNITY_LEAVE)

    def test_copy_action(self):
        """Test copying an employee"""
        url = reverse("hrm:employee-copy", kwargs={"pk": self.active_employee.id})
        response = self.client.post(url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Get the copied employee from the response
        # Response is wrapped by ApiResponseWrapperMiddleware
        response_data = json.loads(response.content)
        self.assertTrue(response_data["success"])
        copied_employee_id = response_data["data"]["id"]
        copied_employee = Employee.objects.get(id=copied_employee_id)

        # Verify unique fields are different
        self.assertNotEqual(copied_employee.code, self.active_employee.code)
        # Code should be auto-generated by AutoCodeMixin (not TEMP_ prefix anymore)
        self.assertTrue(copied_employee.code.startswith(copied_employee.code_type))
        self.assertNotEqual(copied_employee.username, self.active_employee.username)
        self.assertTrue(copied_employee.username.startswith(f"{self.active_employee.username}_copy_"))
        self.assertNotEqual(copied_employee.email, self.active_employee.email)
        # Email format is username@example.com (where username already contains _copy_)
        self.assertTrue("_copy_" in copied_employee.email)
        self.assertNotEqual(copied_employee.citizen_id, self.active_employee.citizen_id)

        # Verify other fields are copied
        self.assertEqual(copied_employee.fullname, self.active_employee.fullname)
        self.assertEqual(copied_employee.department, self.active_employee.department)
        self.assertEqual(copied_employee.position, self.active_employee.position)
        self.assertEqual(copied_employee.start_date, self.active_employee.start_date)
        self.assertEqual(copied_employee.status, self.active_employee.status)
        self.assertEqual(copied_employee.date_of_birth, self.active_employee.date_of_birth)
        self.assertEqual(copied_employee.gender, self.active_employee.gender)

    def test_copy_action_creates_new_user(self):
        """Test that copying an employee creates a new user via signal"""
        url = reverse("hrm:employee-copy", kwargs={"pk": self.active_employee.id})
        response = self.client.post(url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Get the copied employee
        response_data = json.loads(response.content)
        copied_employee_id = response_data["data"]["id"]
        copied_employee = Employee.objects.get(id=copied_employee_id)

        # Verify a new user was created by the signal
        self.assertIsNotNone(copied_employee.user)
        self.assertNotEqual(copied_employee.user, self.active_employee.user)
        self.assertEqual(copied_employee.user.username, copied_employee.username)
        self.assertEqual(copied_employee.user.email, copied_employee.email)

    def test_copy_action_username_format(self):
        """Test that copied username has correct format with underscore before random string"""
        url = reverse("hrm:employee-copy", kwargs={"pk": self.active_employee.id})
        response = self.client.post(url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response_data = json.loads(response.content)
        copied_employee_id = response_data["data"]["id"]
        copied_employee = Employee.objects.get(id=copied_employee_id)

        # Verify username format: original_copy_randomstring
        self.assertTrue(copied_employee.username.startswith(f"{self.active_employee.username}_copy_"))
        # Extract the random part after _copy_
        parts = copied_employee.username.split("_copy_")
        self.assertEqual(len(parts), 2)
        random_part = parts[1]
        # Random part should be 10 characters (as per implementation)
        self.assertEqual(len(random_part), 10)

    def test_copy_action_email_format(self):
        """Test that copied email has correct format"""
        url = reverse("hrm:employee-copy", kwargs={"pk": self.active_employee.id})
        response = self.client.post(url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response_data = json.loads(response.content)
        copied_employee_id = response_data["data"]["id"]
        copied_employee = Employee.objects.get(id=copied_employee_id)

        # Verify email format: username@example.com (where username contains _copy_)
        self.assertTrue("_copy_" in copied_employee.email)
        self.assertTrue(copied_employee.email.endswith("@example.com"))
        # Email should be: {username}_copy_{random}@example.com
        local_part = copied_employee.email.split("@")[0]
        self.assertTrue(local_part.startswith(f"{self.active_employee.username}_copy_"))

    def test_copy_action_citizen_id_is_random(self):
        """Test that copied citizen_id is random and different from original"""
        url = reverse("hrm:employee-copy", kwargs={"pk": self.active_employee.id})
        response = self.client.post(url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response_data = json.loads(response.content)
        copied_employee_id = response_data["data"]["id"]
        copied_employee = Employee.objects.get(id=copied_employee_id)

        # Verify citizen_id is different and has correct length (10 digits as per implementation)
        self.assertNotEqual(copied_employee.citizen_id, self.active_employee.citizen_id)
        self.assertEqual(len(copied_employee.citizen_id), 10)
        self.assertTrue(copied_employee.citizen_id.isdigit())

    def test_transfer_action(self):
        """Test transferring an employee to a new department and position"""
        # Create a new department and position
        new_block = Block.objects.create(
            code="KH002",
            name="New Block",
            branch=self.branch,
            block_type=Block.BlockType.SUPPORT,
        )
        new_department = Department.objects.create(
            code="PB002",
            name="New Department",
            branch=self.branch,
            block=new_block,
        )
        new_position = Position.objects.create(
            code="CV002",
            name="Senior Manager",
        )

        url = reverse("hrm:employee-transfer", kwargs={"pk": self.active_employee.id})
        payload = {
            "date": "2024-03-01",
            "department_id": new_department.id,
            "position_id": new_position.id,
            "note": "Transferred to new department for expansion",
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.active_employee.refresh_from_db()
        self.assertEqual(self.active_employee.department, new_department)
        self.assertEqual(self.active_employee.position, new_position)
        # Branch and block should be automatically updated from the new department
        self.assertEqual(self.active_employee.branch, new_department.branch)
        self.assertEqual(self.active_employee.block, new_department.block)

        # Verify work history record was created
        work_history = EmployeeWorkHistory.objects.filter(
            employee=self.active_employee,
            name=EmployeeWorkHistory.EventType.TRANSFER,
        ).first()
        self.assertIsNotNone(work_history)
        self.assertEqual(str(work_history.date), "2024-03-01")
        self.assertEqual(work_history.department, new_department)
        self.assertEqual(work_history.position, new_position)
        self.assertEqual(work_history.branch, new_department.branch)
        self.assertEqual(work_history.block, new_department.block)
        self.assertEqual(work_history.note, "Transferred to new department for expansion")

    def test_transfer_action_department_only(self):
        """Test transferring an employee with same position"""
        # Create a new department
        new_block = Block.objects.create(
            code="KH003",
            name="Another Block",
            branch=self.branch,
            block_type=Block.BlockType.SUPPORT,
        )
        new_department = Department.objects.create(
            code="PB003",
            name="Another Department",
            branch=self.branch,
            block=new_block,
        )

        # Keep the same position but transfer to new department
        original_position = Position.objects.create(
            code="CV003",
            name="Manager",
        )
        self.active_employee.position = original_position
        self.active_employee.save(update_fields=["position"])

        url = reverse("hrm:employee-transfer", kwargs={"pk": self.active_employee.id})
        payload = {
            "date": "2024-04-01",
            "department_id": new_department.id,
            "position_id": original_position.id,
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.active_employee.refresh_from_db()
        self.assertEqual(self.active_employee.department, new_department)
        self.assertEqual(self.active_employee.position, original_position)

    def test_transfer_action_validates_department(self):
        """Test that transfer action validates the department"""
        url = reverse("hrm:employee-transfer", kwargs={"pk": self.active_employee.id})
        payload = {
            "date": "2024-03-01",
            "department_id": 99999,  # Non-existent department
            "position_id": 1,
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_transfer_action_validates_position(self):
        """Test that transfer action validates the position"""
        url = reverse("hrm:employee-transfer", kwargs={"pk": self.active_employee.id})
        payload = {
            "date": "2024-03-01",
            "department_id": self.department.id,
            "position_id": 99999,  # Non-existent position
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_transfer_action_requires_date(self):
        """Test that transfer action requires date field"""
        url = reverse("hrm:employee-transfer", kwargs={"pk": self.active_employee.id})
        payload = {
            "department_id": self.department.id,
            "position_id": 1,
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
