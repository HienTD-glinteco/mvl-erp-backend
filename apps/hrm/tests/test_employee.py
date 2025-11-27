import json
from datetime import date
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import AdministrativeUnit, Province
from apps.files.models import FileModel
from apps.hrm.models import Block, Branch, Department, Employee, Position

User = get_user_model()


class APITestMixin:
    """Mixin to handle wrapped API responses and data extraction"""

    def get_response_data(self, response):
        """Extract data from wrapped API response"""
        content = json.loads(response.content.decode())
        if "data" in content:
            data = content["data"]
            # Handle paginated responses - extract results list
            if isinstance(data, dict) and "results" in data:
                return data["results"]
            return data
        return content

    def normalize_list_response(self, data):
        """Normalize list responses that may or may not be paginated"""

        if isinstance(data, dict) and "results" in data:
            results = data["results"]
            count = data.get("count", len(results))
            return results, count

        if isinstance(data, list):
            return data, len(data)

        return [], 0


class EmployeeModelTest(TestCase):
    """Test cases for Employee model"""

    def setUp(self):
        # Create test branch, block, and department
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

        # Patch the Celery task "delay" call used by signal handlers.
        # Keep both the patcher (for stopping) and the mock (for assertions).
        self.hr_report_patcher = patch("apps.hrm.signals.hr_reports.aggregate_hr_reports_for_work_history.delay")
        self.mock_hr_report_delay = self.hr_report_patcher.start()

        self.recruitment_report_patcher = patch(
            "apps.hrm.signals.recruitment_reports.aggregate_recruitment_reports_for_candidate.delay"
        )
        self.mock_recruitment_report_delay = self.recruitment_report_patcher.start()
        # Patch the timesheet prepare task
        self.prepare_timesheet_patcher = patch("apps.hrm.signals.employee.prepare_monthly_timesheets.delay")
        self.mock_prepare_timesheet_delay = self.prepare_timesheet_patcher.start()

    def tearDown(self):
        # Stop patchers
        self.hr_report_patcher.stop()
        self.recruitment_report_patcher.stop()
        self.prepare_timesheet_patcher.stop()
        return super().tearDown()

    def test_create_employee(self):
        """Test creating an employee"""
        employee = Employee.objects.create(
            fullname="John Doe",
            username="johndoe",
            email="john@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="john.personal@example.com",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="123456789",
        )
        self.assertTrue(employee.code.startswith("MV"))
        self.assertEqual(employee.fullname, "John Doe")
        self.assertEqual(employee.username, "johndoe")
        self.assertEqual(employee.email, "john@example.com")
        self.assertIsNotNone(employee.user)
        self.assertEqual(employee.user.username, "johndoe")
        self.assertEqual(employee.user.email, "john@example.com")
        # The prepare_monthly_timesheets task should have been scheduled for new employee
        self.mock_prepare_timesheet_delay.assert_called()
        self.assertIn("John Doe", str(employee))

    def test_delete_employee_with_user(self):
        """Test deleting an employee also deletes the associated User account"""
        # Arrange: Create an employee with an associated user
        employee = Employee.objects.create(
            fullname="John Doe",
            username="johndoe",
            email="john@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="john.personal@example.com",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="123456789",
        )

        # Verify user was created
        self.assertIsNotNone(employee.user)
        user_id = employee.user.id
        self.assertTrue(User.objects.filter(id=user_id).exists())

        # Act: Delete the employee
        employee.delete()

        # Assert: Both employee and user should be deleted
        self.assertFalse(Employee.objects.filter(id=employee.id).exists())
        self.assertFalse(User.objects.filter(id=user_id).exists())

    def test_delete_employee_without_user(self):
        """Test deleting an employee without an associated User account"""
        # Arrange: Create an employee
        employee = Employee.objects.create(
            fullname="Jane Doe",
            username="janedoe",
            email="jane@example.com",
            phone="0987654321",
            attendance_code="54321",
            date_of_birth="1991-01-01",
            personal_email="jane.personal@example.com",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="987654321",
        )

        # Manually remove the user association
        if employee.user:
            user = employee.user
            employee.user = None
            employee.save()
            # Delete the user separately to simulate an employee without a user
            user.delete()

        employee_id = employee.id

        # Act: Delete the employee
        employee.delete()

        # Assert: Employee should be deleted without errors
        self.assertFalse(Employee.objects.filter(id=employee_id).exists())

    def test_resigned_to_active_triggers_timesheet_task(self):
        # Create resigned employee
        employee = Employee.objects.create(
            fullname="Resigned User",
            username="resigned",
            email="resigned@example.com",
            phone="0123456711",
            attendance_code="RES001",
            start_date="2020-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="123456900",
            resignation_start_date=timezone.now(),
            resignation_reason="Personal reasons",
            status=Employee.Status.RESIGNED,
        )

        # Simulate update to Active (return to work)
        old_status = employee.status
        employee.status = Employee.Status.ACTIVE
        employee.save(update_fields=["status"])
        employee.old_status = old_status

        # Handler should have scheduled prepare task
        self.mock_prepare_timesheet_delay.assert_called()

    def test_employee_code_unique(self):
        """Test employee code uniqueness"""
        employee1 = Employee.objects.create(
            fullname="John Doe",
            username="johndoe",
            email="john@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="john.personal@example.com",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="123456789",
        )

        # Cannot create with same code manually
        with self.assertRaises(Exception):
            Employee.objects.create(
                code=employee1.code,
                fullname="Jane Doe",
                username="janedoe",
                email="jane@example.com",
                phone="0987654321",
                attendance_code="54321",
                date_of_birth="1991-01-01",
                personal_email="jane.personal@example.com",
                start_date="2024-01-01",
                branch=self.branch,
                block=self.block,
                department=self.department,
                citizen_id="123456780",
            )

    def test_employee_username_unique(self):
        """Test that username must be unique"""
        Employee.objects.create(
            fullname="John Doe",
            username="johndoe",
            email="john@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="john.personal@example.com",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="123456789",
        )

        with self.assertRaises(Exception):
            Employee.objects.create(
                fullname="Jane Doe",
                username="johndoe",
                email="jane@example.com",
                phone="0987654321",
                attendance_code="54321",
                date_of_birth="1991-01-01",
                personal_email="jane.personal@example.com",
                start_date="2024-01-01",
                branch=self.branch,
                block=self.block,
                department=self.department,
                citizen_id="123456780",
            )

    def test_employee_email_unique(self):
        """Test that email must be unique"""
        Employee.objects.create(
            fullname="John Doe",
            username="johndoe",
            email="john@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="john.personal@example.com",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="123456789",
        )

        with self.assertRaises(Exception):
            Employee.objects.create(
                fullname="Jane Doe",
                username="janedoe",
                email="john@example.com",
                phone="0987654321",
                attendance_code="54321",
                date_of_birth="1991-01-01",
                personal_email="jane.personal@example.com",
                start_date="2024-01-01",
                branch=self.branch,
                block=self.block,
                department=self.department,
                citizen_id="123456780",
            )

    def test_employee_validation_block_branch(self):
        """Test validation that block must belong to branch"""
        branch2 = Branch.objects.create(
            code="CN002",
            name="Test Branch 2",
            province=self.province,
            administrative_unit=self.admin_unit,
        )

        employee = Employee(
            fullname="John Doe",
            username="johndoe",
            email="john@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="john.personal@example.com",
            start_date="2024-01-01",
            branch=branch2,
            block=self.block,  # This block belongs to self.branch, not branch2
            department=self.department,
        )

        employee.save()
        self.assertNotEqual(employee.branch, branch2)
        self.assertEqual(employee.branch, self.department.branch)

    def test_employee_validation_department_block(self):
        """Test validation that department must belong to block"""
        block2 = Block.objects.create(
            code="KH002",
            name="Test Block 2",
            branch=self.branch,
            block_type=Block.BlockType.SUPPORT,
        )

        employee = Employee(
            fullname="John Doe",
            username="johndoe",
            email="john@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="john.personal@example.com",
            start_date="2024-01-01",
            branch=self.branch,
            block=block2,
            department=self.department,  # This department belongs to self.block, not block2
        )

        employee.save()
        self.assertNotEqual(employee.block, block2)
        self.assertEqual(employee.block, self.department.block)

    def test_employee_auto_assign_branch_block_from_department(self):
        """Test that branch and block are auto-assigned from department on save"""
        # Create employee with only department specified
        employee = Employee.objects.create(
            fullname="Auto Assign Test",
            username="autotest",
            email="autotest@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="autotest.personal@example.com",
            start_date="2024-01-01",
            department=self.department,
            citizen_id="123456789",
        )

        # Verify that branch and block were automatically set from department
        self.assertEqual(employee.branch, self.department.branch)
        self.assertEqual(employee.block, self.department.block)
        self.assertEqual(employee.branch, self.branch)
        self.assertEqual(employee.block, self.block)

    def test_employee_update_department_updates_branch_block(self):
        """Test that changing department updates branch and block"""
        # Create a second organizational structure
        branch2 = Branch.objects.create(
            code="CN002",
            name="Test Branch 2",
            province=self.province,
            administrative_unit=self.admin_unit,
        )
        block2 = Block.objects.create(
            code="KH002",
            name="Test Block 2",
            branch=branch2,
            block_type=Block.BlockType.BUSINESS,
        )
        department2 = Department.objects.create(
            code="PB002",
            name="Test Department 2",
            branch=branch2,
            block=block2,
        )

        # Create employee with initial department
        employee = Employee.objects.create(
            fullname="Transfer Test",
            username="transfertest",
            email="transfertest@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="transfertest.personal@example.com",
            start_date="2024-01-01",
            department=self.department,
            citizen_id="123456789",
        )

        # Initially should be in first branch/block
        self.assertEqual(employee.branch, self.branch)
        self.assertEqual(employee.block, self.block)

        # Update to second department
        employee.department = department2
        employee.save()

        # Should now be in second branch/block
        self.assertEqual(employee.branch, branch2)
        self.assertEqual(employee.block, block2)
        self.assertEqual(employee.department, department2)

    def test_change_status_back_to_onboarding_fails(self):
        """Test that changing status back to On-boarding for an existing employee fails."""
        from django.core.exceptions import ValidationError

        employee = Employee.objects.create(
            fullname="Test Employee",
            username="testemployee",
            email="test@example.com",
            phone="1234567890",
            attendance_code="12345",
            start_date="2024-01-01",
            department=self.department,
            citizen_id="123456789",
        )
        # Set status to ACTIVE using update_fields to bypass validation
        employee.status = Employee.Status.ACTIVE
        employee.save(update_fields=["status"])
        # Refresh old_status to reflect the current status
        employee.old_status = employee.status

        employee.status = Employee.Status.ONBOARDING
        with self.assertRaises(ValidationError):
            employee.clean()

    def test_resignation_reasons_are_updated(self):
        """Test that ResignationReason choices have been updated"""
        expected_reasons = [
            "AGREEMENT_TERMINATION",
            "PROBATION_FAIL",
            "JOB_ABANDONMENT",
            "DISCIPLINARY_TERMINATION",
            "WORKFORCE_REDUCTION",
            "UNDERPERFORMING",
            "CONTRACT_EXPIRED",
            "VOLUNTARY_HEALTH",
            "VOLUNTARY_PERSONAL",
            "VOLUNTARY_CAREER_CHANGE",
            "VOLUNTARY_OTHER",
            "OTHER",
        ]
        actual_reasons = [reason.name for reason in Employee.ResignationReason]
        self.assertCountEqual(expected_reasons, actual_reasons)

    def test_employee_colored_code_type_property(self):
        """Test that colored_code_type property returns correct format"""
        employee = Employee.objects.create(
            fullname="Test Employee",
            username="testcolor",
            email="testcolor@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="testcolor.personal@example.com",
            start_date="2024-01-01",
            department=self.department,
            code_type=Employee.CodeType.MV,
            citizen_id="123456789",
        )

        colored_value = employee.colored_code_type
        self.assertIsNotNone(colored_value)
        self.assertIn("value", colored_value)
        self.assertIn("variant", colored_value)
        self.assertEqual(colored_value["value"], "MV")

    def test_employee_colored_status_property(self):
        """Test that colored_status property returns correct format"""
        employee = Employee.objects.create(
            fullname="Test Employee",
            username="testcolor",
            email="testcolor@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="testcolor.personal@example.com",
            start_date="2024-01-01",
            department=self.department,
            citizen_id="123456789",
        )
        # Set status to ACTIVE using update_fields to bypass validation
        employee.status = Employee.Status.ACTIVE
        employee.save(update_fields=["status"])

        colored_value = employee.colored_status
        self.assertIsNotNone(colored_value)
        self.assertIn("value", colored_value)
        self.assertIn("variant", colored_value)
        self.assertEqual(colored_value["value"], "Active")

    def test_employee_code_type_os_option(self):
        """Test that OS code type option can be set and retrieved"""
        # Arrange & Act: Create employee with OS code type
        employee = Employee.objects.create(
            fullname="Test Employee OS",
            username="testemployeeos",
            email="testemployeeos@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="testemployeeos.personal@example.com",
            start_date="2024-01-01",
            department=self.department,
            code_type=Employee.CodeType.OS,
            citizen_id="123456789",
        )

        # Assert: Verify OS code type is set correctly
        self.assertEqual(employee.code_type, Employee.CodeType.OS)
        self.assertEqual(employee.code_type.label, "OS")

    def test_employee_code_type_os_colored_property(self):
        """Test that colored_code_type property returns correct format for OS type with BLUE variant"""
        # Arrange & Act: Create employee with OS code type
        employee = Employee.objects.create(
            fullname="Test Employee OS Color",
            username="testemployeeoscolor",
            email="testemployeeoscolor@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="testemployeeoscolor.personal@example.com",
            start_date="2024-01-01",
            department=self.department,
            code_type=Employee.CodeType.OS,
            citizen_id="123456789",
        )

        # Assert: Verify colored_code_type returns correct value and BLUE variant
        colored_value = employee.colored_code_type
        self.assertIsNotNone(colored_value)
        self.assertIn("value", colored_value)
        self.assertIn("variant", colored_value)
        self.assertEqual(colored_value["value"], "OS")
        self.assertEqual(colored_value["variant"], "BLUE")

    def test_employee_citizen_id_file_can_be_null(self):
        """Test that citizen_id_file can be null"""
        # Arrange & Act: Create employee without citizen_id_file
        employee = Employee.objects.create(
            fullname="Test Employee No File",
            username="testemployeenofile",
            email="testemployeenofile@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="testemployeenofile.personal@example.com",
            start_date="2024-01-01",
            department=self.department,
            citizen_id="123456789",
            citizen_id_file=None,
        )

        # Assert: Verify citizen_id_file is None
        self.assertIsNone(employee.citizen_id_file)

    def test_employee_citizen_id_file_foreign_key_relationship(self):
        """Test that citizen_id_file can be linked to FileModel"""

        # Arrange: Create a FileModel instance
        file_instance = FileModel.objects.create(
            purpose="citizen_id",
            file_name="citizen_id_document.pdf",
            file_path="documents/citizen_ids/citizen_id_document.pdf",
            size=102400,
        )

        # Act: Create employee with citizen_id_file
        employee = Employee.objects.create(
            fullname="Test Employee With File",
            username="testemployeewithfile",
            email="testemployeewithfile@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="testemployeewithfile.personal@example.com",
            start_date="2024-01-01",
            department=self.department,
            citizen_id="123456789",
            citizen_id_file=file_instance,
        )

        # Assert: Verify the foreign key relationship
        self.assertIsNotNone(employee.citizen_id_file)
        self.assertEqual(employee.citizen_id_file.id, file_instance.id)
        self.assertEqual(employee.citizen_id_file.file_name, "citizen_id_document.pdf")

    def test_employee_citizen_id_file_set_null_on_delete(self):
        """Test that citizen_id_file is set to null when FileModel is deleted"""

        # Arrange: Create FileModel and Employee with that file
        file_instance = FileModel.objects.create(
            purpose="citizen_id",
            file_name="citizen_id_to_delete.pdf",
            file_path="documents/citizen_ids/citizen_id_to_delete.pdf",
            size=102400,
        )

        employee = Employee.objects.create(
            fullname="Test Employee File Delete",
            username="testemployeefiledelete",
            email="testemployeefiledelete@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            personal_email="testemployeefiledelete.personal@example.com",
            start_date="2024-01-01",
            department=self.department,
            citizen_id="123456789",
            citizen_id_file=file_instance,
        )

        # Verify file is linked
        self.assertIsNotNone(employee.citizen_id_file)

        # Act: Delete the FileModel
        file_instance.delete()

        # Assert: Refresh employee and verify citizen_id_file is now null
        employee.refresh_from_db()
        self.assertIsNone(employee.citizen_id_file)


class EmployeeAPITest(TestCase, APITestMixin):
    """Test cases for Employee API endpoints"""

    def setUp(self):
        """Set up test data"""
        # Patch signal tasks to avoid broker connection during API tests
        self.hr_report_patcher = patch("apps.hrm.signals.hr_reports.aggregate_hr_reports_for_work_history.delay")
        self.mock_hr_report_delay = self.hr_report_patcher.start()

        self.recruitment_report_patcher = patch(
            "apps.hrm.signals.recruitment_reports.aggregate_recruitment_reports_for_candidate.delay"
        )
        self.mock_recruitment_report_delay = self.recruitment_report_patcher.start()

        # Changed to superuser to bypass RoleBasedPermission for API tests
        self.admin_user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="testpass123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin_user)

        # Create test organizational structure
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

        # Create test employees
        self.employee1 = Employee.objects.create(
            fullname="John Doe",
            username="emp001",
            email="emp1@example.com",
            phone="1234567890",
            attendance_code="0000000000001",
            date_of_birth="1990-01-01",
            personal_email="emp1.personal@example.com",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="123456789",
        )

        self.employee2 = Employee.objects.create(
            fullname="Jane Smith",
            username="emp002",
            email="emp2@example.com",
            phone="2234567890",
            attendance_code="0000000000002",
            date_of_birth="1991-01-01",
            personal_email="emp2.personal@example.com",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="123456780",
        )

        self.employee3 = Employee.objects.create(
            fullname="Bob Johnson",
            username="emp003",
            email="emp3@example.com",
            phone="3234567890",
            attendance_code="0000000000003",
            date_of_birth="1992-01-01",
            personal_email="emp3.personal@example.com",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="123456781",
        )

    def test_list_employees(self):
        """Test listing all employees"""
        url = reverse("hrm:employee-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        self.assertEqual(count, 3)
        self.assertEqual(len(results), 3)
        codes = {item["code"] for item in results}
        self.assertTrue(all(code.startswith("MV") for code in codes))

    def test_filter_employees_by_code(self):
        """Test filtering employees by code"""
        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"code": self.employee1.code})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)
        self.assertEqual(count, 1)
        self.assertEqual(results[0]["code"], self.employee1.code)

    def test_filter_employees_by_fullname(self):
        """Test filtering employees by fullname"""
        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"fullname": "John"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)
        self.assertGreaterEqual(count, 1)
        self.assertTrue(any("John" in item["fullname"] for item in results))

    def test_search_employees(self):
        """Test searching employees"""
        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"search": "Jane"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)
        self.assertGreaterEqual(count, 1)
        self.assertTrue(any(item["fullname"] == "Jane Smith" for item in results))

    def test_search_employees_by_citizen_id(self):
        """Test searching employees by citizen_id"""
        # Create an employee with a specific citizen_id for testing
        test_employee = Employee.objects.create(
            fullname="Test Employee",
            username="test_search_citizen",
            email="testsearch@example.com",
            phone="9876543210",
            citizen_id="987654321",
            start_date=date.today(),
            branch=self.branch,
            department=self.department,
        )

        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"search": "987654321"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)
        self.assertGreaterEqual(count, 1)
        self.assertTrue(any(item.get("citizen_id") == "987654321" for item in results))

    def test_list_employees_pagination(self):
        """Test employee list pagination"""
        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"page": 1, "page_size": 2})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)
        self.assertEqual(count, 2)
        self.assertLessEqual(len(results), 2)

    def test_retrieve_employee(self):
        """Test retrieving a single employee"""
        url = reverse("hrm:employee-detail", kwargs={"pk": self.employee1.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(data["fullname"], "John Doe")
        self.assertEqual(data["username"], "emp001")
        self.assertEqual(data["email"], "emp1@example.com")
        self.assertIn("user", data)
        self.assertIn("branch", data)
        self.assertIn("block", data)
        self.assertIn("department", data)

    def test_create_employee(self):
        """Test creating an employee"""
        url = reverse("hrm:employee-list")
        payload = {
            "fullname": "Alice Williams",
            "username": "emp004",
            "email": "emp4@example.com",
            "phone": "4234567890",
            "attendance_code": "58607083146091314660",
            "date_of_birth": "1993-01-01",
            "personal_email": "emp4.personal@example.com",
            "start_date": "2024-01-01",
            "department_id": self.department.id,
            "note": "Test note",
            "citizen_id": "123456787",
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = self.get_response_data(response)
        self.assertTrue(data["code"].startswith("MV"))
        self.assertEqual(data["fullname"], "Alice Williams")
        self.assertEqual(data["username"], "emp004")
        self.assertEqual(data["email"], "emp4@example.com")
        self.assertTrue(Employee.objects.filter(username="emp004").exists())

        # Verify user was created
        employee = Employee.objects.get(username="emp004")
        self.assertIsNotNone(employee.user)
        self.assertEqual(employee.user.username, "emp004")
        # Verify branch and block were auto-set from department
        self.assertEqual(employee.branch, self.branch)
        self.assertEqual(employee.block, self.block)

    def test_update_employee(self):
        """Test updating an employee"""
        url = reverse("hrm:employee-detail", kwargs={"pk": self.employee1.id})
        payload = {
            "fullname": "John Updated",
            "username": "emp001",
            "email": "emp1@example.com",
            "phone": "9999999999",
            "attendance_code": "586070831460",
            "date_of_birth": "1990-01-01",
            "personal_email": "emp1.personal@example.com",
            "start_date": "2024-01-01",
            "citizen_id": self.employee1.citizen_id,
            "department_id": self.department.id,
        }
        response = self.client.put(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(data["fullname"], "John Updated")
        self.assertEqual(data["phone"], "9999999999")

        self.employee1.refresh_from_db()
        self.assertEqual(self.employee1.fullname, "John Updated")
        self.assertEqual(self.employee1.phone, "9999999999")

    def test_partial_update_employee(self):
        """Test partially updating an employee"""
        url = reverse("hrm:employee-detail", kwargs={"pk": self.employee1.id})
        payload = {"fullname": "John Partially Updated"}
        response = self.client.patch(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(data["fullname"], "John Partially Updated")

        self.employee1.refresh_from_db()
        self.assertEqual(self.employee1.fullname, "John Partially Updated")

    def test_delete_employee(self):
        """Test deleting an employee"""
        url = reverse("hrm:employee-detail", kwargs={"pk": self.employee3.id})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Employee.objects.filter(id=self.employee3.id).exists())

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_create_employee_with_citizen_id_file(self, mock_s3_service_class):
        """Test creating an employee with citizen_id_file_id"""
        # Mock S3 service for view/download URLs in FileModel properties
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance
        mock_s3_instance.generate_view_url.return_value = "https://example.com/view/citizen_id.pdf"
        mock_s3_instance.generate_download_url.return_value = "https://example.com/download/citizen_id.pdf"

        # Arrange: Create a FileModel instance
        file_instance = FileModel.objects.create(
            purpose="citizen_id",
            file_name="citizen_id_api_test.pdf",
            file_path="documents/citizen_ids/citizen_id_api_test.pdf",
            size=102400,
        )

        # Act: Create employee with citizen_id_file_id
        url = reverse("hrm:employee-list")
        payload = {
            "fullname": "Employee With Citizen ID File",
            "username": "empwithfile",
            "email": "empwithfile@example.com",
            "phone": "1234567890",
            "attendance_code": "58607083146091314661",
            "date_of_birth": "1995-01-01",
            "personal_email": "empwithfile.personal@example.com",
            "start_date": "2024-01-01",
            "department_id": self.department.id,
            "citizen_id": "123456788",
            "citizen_id_file_id": file_instance.id,
        }
        response = self.client.post(url, payload, format="json")

        # Assert: Verify employee was created with citizen_id_file
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = self.get_response_data(response)

        # Verify citizen_id_file is returned in response (read-only field)
        self.assertIn("citizen_id_file", data)
        self.assertIsNotNone(data["citizen_id_file"])
        self.assertEqual(data["citizen_id_file"]["id"], file_instance.id)
        self.assertEqual(data["citizen_id_file"]["file_name"], "citizen_id_api_test.pdf")

        # Verify citizen_id_file_id is not in response (write-only field)
        self.assertNotIn("citizen_id_file_id", data)

        # Verify in database
        employee = Employee.objects.get(username="empwithfile")
        self.assertIsNotNone(employee.citizen_id_file)
        self.assertEqual(employee.citizen_id_file.id, file_instance.id)

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_update_employee_citizen_id_file(self, mock_s3_service_class):
        """Test updating an employee's citizen_id_file_id"""
        # Mock S3 service for view/download URLs in FileModel properties
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance
        mock_s3_instance.generate_view_url.return_value = "https://example.com/view/citizen_id.pdf"
        mock_s3_instance.generate_download_url.return_value = "https://example.com/download/citizen_id.pdf"

        # Arrange: Create a new FileModel instance
        new_file = FileModel.objects.create(
            purpose="citizen_id",
            file_name="updated_citizen_id.pdf",
            file_path="documents/citizen_ids/updated_citizen_id.pdf",
            size=204800,
        )

        # Act: Update employee with new citizen_id_file_id
        url = reverse("hrm:employee-detail", kwargs={"pk": self.employee1.id})
        payload = {
            "fullname": self.employee1.fullname,
            "username": self.employee1.username,
            "email": self.employee1.email,
            "phone": self.employee1.phone,
            "attendance_code": self.employee1.attendance_code,
            "date_of_birth": str(self.employee1.date_of_birth),
            "personal_email": self.employee1.personal_email,
            "start_date": str(self.employee1.start_date),
            "department_id": self.department.id,
            "citizen_id": self.employee1.citizen_id,
            "citizen_id_file_id": new_file.id,
        }
        response = self.client.put(url, payload, format="json")

        # Assert: Verify update was successful
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        # Verify citizen_id_file is returned with new file data
        self.assertIn("citizen_id_file", data)
        self.assertIsNotNone(data["citizen_id_file"])
        self.assertEqual(data["citizen_id_file"]["id"], new_file.id)
        self.assertEqual(data["citizen_id_file"]["file_name"], "updated_citizen_id.pdf")

        # Verify in database
        self.employee1.refresh_from_db()
        self.assertIsNotNone(self.employee1.citizen_id_file)
        self.assertEqual(self.employee1.citizen_id_file.id, new_file.id)

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_partial_update_employee_citizen_id_file(self, mock_s3_service_class):
        """Test partially updating an employee with citizen_id_file_id"""
        # Mock S3 service for view/download URLs in FileModel properties
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance
        mock_s3_instance.generate_view_url.return_value = "https://example.com/view/citizen_id.pdf"
        mock_s3_instance.generate_download_url.return_value = "https://example.com/download/citizen_id.pdf"

        # Arrange: Create a FileModel instance
        file_instance = FileModel.objects.create(
            purpose="citizen_id",
            file_name="partial_update_citizen_id.pdf",
            file_path="documents/citizen_ids/partial_update_citizen_id.pdf",
            size=153600,
        )

        # Act: Partially update employee with citizen_id_file_id
        url = reverse("hrm:employee-detail", kwargs={"pk": self.employee2.id})
        payload = {
            "citizen_id_file_id": file_instance.id,
        }
        response = self.client.patch(url, payload, format="json")

        # Assert: Verify update was successful
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        # Verify citizen_id_file is returned
        self.assertIn("citizen_id_file", data)
        self.assertIsNotNone(data["citizen_id_file"])
        self.assertEqual(data["citizen_id_file"]["id"], file_instance.id)

        # Verify in database
        self.employee2.refresh_from_db()
        self.assertIsNotNone(self.employee2.citizen_id_file)
        self.assertEqual(self.employee2.citizen_id_file.id, file_instance.id)

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_get_employee_with_citizen_id_file(self, mock_s3_service_class):
        """Test retrieving an employee with citizen_id_file returns FileSerializer data"""
        # Mock S3 service for view/download URLs in FileModel properties
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance
        mock_s3_instance.generate_view_url.return_value = "https://example.com/view/citizen_id.pdf"
        mock_s3_instance.generate_download_url.return_value = "https://example.com/download/citizen_id.pdf"

        # Arrange: Create FileModel and link to employee
        file_instance = FileModel.objects.create(
            purpose="citizen_id",
            file_name="get_test_citizen_id.pdf",
            file_path="documents/citizen_ids/get_test_citizen_id.pdf",
            size=122880,
        )
        self.employee1.citizen_id_file = file_instance
        self.employee1.save(update_fields=["citizen_id_file"])

        # Act: Retrieve employee
        url = reverse("hrm:employee-detail", kwargs={"pk": self.employee1.id})
        response = self.client.get(url)

        # Assert: Verify citizen_id_file is properly serialized
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        self.assertIn("citizen_id_file", data)
        self.assertIsNotNone(data["citizen_id_file"])
        self.assertEqual(data["citizen_id_file"]["id"], file_instance.id)
        self.assertEqual(data["citizen_id_file"]["file_name"], "get_test_citizen_id.pdf")
        self.assertEqual(data["citizen_id_file"]["size"], 122880)
        self.assertEqual(data["citizen_id_file"]["file_path"], "documents/citizen_ids/get_test_citizen_id.pdf")

        # Verify FileSerializer includes expected fields
        self.assertIn("view_url", data["citizen_id_file"])
        self.assertIn("download_url", data["citizen_id_file"])
        self.assertIn("created_at", data["citizen_id_file"])
        self.assertIn("updated_at", data["citizen_id_file"])

    def test_update_employee_remove_citizen_id_file(self):
        """Test removing citizen_id_file by setting citizen_id_file_id to null"""
        # Arrange: Create FileModel and link to employee
        file_instance = FileModel.objects.create(
            purpose="citizen_id",
            file_name="to_be_removed.pdf",
            file_path="documents/citizen_ids/to_be_removed.pdf",
            size=102400,
        )
        self.employee1.citizen_id_file = file_instance
        self.employee1.save(update_fields=["citizen_id_file"])

        # Verify file is linked
        self.assertIsNotNone(self.employee1.citizen_id_file)

        # Act: Remove citizen_id_file by setting to null
        url = reverse("hrm:employee-detail", kwargs={"pk": self.employee1.id})
        payload = {
            "citizen_id_file_id": None,
        }
        response = self.client.patch(url, payload, format="json")

        # Assert: Verify file was removed
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        self.assertIn("citizen_id_file", data)
        self.assertIsNone(data["citizen_id_file"])

        # Verify in database
        self.employee1.refresh_from_db()
        self.assertIsNone(self.employee1.citizen_id_file)

    def test_create_employee_invalid_block(self):
        """Test that branch and block are auto-set from department"""
        # Create a second branch with its own block and department
        branch2 = Branch.objects.create(
            code="CN002",
            name="Test Branch 2",
            province=self.province,
            administrative_unit=self.admin_unit,
        )
        block2 = Block.objects.create(
            code="KH002",
            name="Test Block 2",
            branch=branch2,
            block_type=Block.BlockType.BUSINESS,
        )
        department2 = Department.objects.create(
            code="PB002",
            name="Test Department 2",
            branch=branch2,
            block=block2,
        )

        url = reverse("hrm:employee-list")
        payload = {
            "fullname": "Test Employee",
            "username": "testuser",
            "email": "testuser@example.com",
            "phone": "5555555555",
            "attendance_code": "586070831460",
            "date_of_birth": "1994-01-01",
            "personal_email": "testuser.personal@example.com",
            "start_date": "2024-01-01",
            "department_id": department2.id,
            "citizen_id": "123456788",
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = self.get_response_data(response)

        # Verify that branch and block were auto-set from department2
        employee = Employee.objects.get(username="testuser")
        self.assertEqual(employee.branch, branch2)
        self.assertEqual(employee.block, block2)
        self.assertEqual(employee.department, department2)

    def test_update_employee_to_resigned_without_fields_fails(self):
        """Test that updating employee status to Resigned without required fields fails"""
        url = reverse("hrm:employee-detail", kwargs={"pk": self.employee1.id})
        payload = {
            "fullname": self.employee1.fullname,
            "username": self.employee1.username,
            "email": self.employee1.email,
            "phone": self.employee1.phone,
            "attendance_code": self.employee1.attendance_code,
            "date_of_birth": "1990-01-01",
            "personal_email": self.employee1.personal_email,
            "start_date": "2024-01-01",
            "department_id": self.department.id,
            "status": "Resigned",
            "citizen_id": self.employee1.citizen_id,
        }
        response = self.client.put(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        content = json.loads(response.content.decode())
        self.assertIn("error", content)

    def test_retrieve_employee_includes_colored_values(self):
        """Test that retrieving employee includes colored_code_type and colored_status"""
        url = reverse("hrm:employee-detail", kwargs={"pk": self.employee1.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        # Check colored_code_type
        self.assertIn("colored_code_type", data)
        self.assertIsNotNone(data["colored_code_type"])
        self.assertIn("value", data["colored_code_type"])
        self.assertIn("variant", data["colored_code_type"])

        # Check colored_status
        self.assertIn("colored_status", data)
        self.assertIsNotNone(data["colored_status"])
        self.assertIn("value", data["colored_status"])
        self.assertIn("variant", data["colored_status"])

    def test_list_employees_includes_colored_values(self):
        """Test that listing employees includes colored values"""
        url = reverse("hrm:employee-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        self.assertGreater(count, 0)
        for item in results:
            self.assertIn("colored_code_type", item)
            self.assertIn("colored_status", item)

    def tearDown(self):
        # Stop signal patchers
        self.hr_report_patcher.stop()
        self.recruitment_report_patcher.stop()
        return super().tearDown()

    def test_create_employee_with_position(self):
        """Test creating employee with optional position_id"""
        from apps.hrm.models import Position

        position = Position.objects.create(code="POS001", name="Test Position")

        url = reverse("hrm:employee-list")
        payload = {
            "fullname": "Employee With Position",
            "username": "emp_with_pos",
            "email": "emp_with_pos@example.com",
            "phone": "6666666666",
            "attendance_code": "586070831460",
            "date_of_birth": "1995-01-01",
            "personal_email": "emp_with_pos.personal@example.com",
            "start_date": "2024-01-01",
            "department_id": self.department.id,
            "position_id": position.id,
            "citizen_id": "123456790",
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = self.get_response_data(response)

        # Verify nested objects are returned in response
        self.assertIn("position", data)
        self.assertIsNotNone(data["position"])
        self.assertEqual(data["position"]["id"], position.id)
        self.assertEqual(data["position"]["name"], "Test Position")

        # Verify in database
        employee = Employee.objects.get(username="emp_with_pos")
        self.assertEqual(employee.position.id, position.id)

    def test_serializer_returns_nested_objects_for_read(self):
        """Test that serializer returns full nested objects for branch, block, department"""
        url = reverse("hrm:employee-detail", kwargs={"pk": self.employee1.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)

        # Branch should be nested object with id, name, code
        self.assertIn("branch", data)
        self.assertIsInstance(data["branch"], dict)
        self.assertIn("id", data["branch"])
        self.assertIn("name", data["branch"])
        self.assertIn("code", data["branch"])
        self.assertEqual(data["branch"]["id"], self.branch.id)

        # Block should be nested object
        self.assertIn("block", data)
        self.assertIsInstance(data["block"], dict)
        self.assertIn("id", data["block"])
        self.assertIn("name", data["block"])
        self.assertIn("code", data["block"])
        self.assertEqual(data["block"]["id"], self.block.id)

        # Department should be nested object
        self.assertIn("department", data)
        self.assertIsInstance(data["department"], dict)
        self.assertIn("id", data["department"])
        self.assertIn("name", data["department"])
        self.assertIn("code", data["department"])
        self.assertEqual(data["department"]["id"], self.department.id)

        # User should be nested object
        self.assertIn("user", data)
        self.assertIsInstance(data["user"], dict)

    def test_create_employee_without_date_of_birth(self):
        """Test creating an employee without date_of_birth (should be optional now)"""
        employee = Employee.objects.create(
            fullname="Jane Doe",
            username="janedoe",
            email="jane@example.com",
            phone="0123456788",
            attendance_code="12346",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="123456791",
        )
        self.assertIsNone(employee.date_of_birth)
        self.assertEqual(employee.fullname, "Jane Doe")
        self.assertEqual(employee.email, "jane@example.com")

    def test_create_employee_without_personal_email(self):
        """Test creating an employee without personal_email (should be optional now)"""
        employee = Employee.objects.create(
            fullname="Bob Smith",
            username="bobsmith",
            email="bob@example.com",
            phone="0123456787",
            attendance_code="12347",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="123456792",
        )
        self.assertIsNone(employee.personal_email)
        self.assertEqual(employee.fullname, "Bob Smith")
        self.assertEqual(employee.email, "bob@example.com")

    def test_create_employee_with_optional_fields(self):
        """Test creating an employee with optional fields"""
        employee = Employee.objects.create(
            fullname="Alice Johnson",
            username="alicejohnson",
            email="alice@example.com",
            phone="0123456786",
            attendance_code="12348",
            date_of_birth="1995-05-15",
            personal_email="alice.personal@example.com",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="123456782",
        )
        self.assertEqual(str(employee.date_of_birth), "1995-05-15")
        self.assertEqual(employee.personal_email, "alice.personal@example.com")
        self.assertEqual(employee.fullname, "Alice Johnson")

    def test_create_multiple_employees_without_personal_email(self):
        """Test creating multiple employees without personal_email (no unique constraint)"""
        employee1 = Employee.objects.create(
            fullname="Charlie Brown",
            username="charliebrown",
            email="charlie@example.com",
            phone="0123456785",
            attendance_code="12349",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="123456783",
        )

        employee2 = Employee.objects.create(
            fullname="David Green",
            username="davidgreen",
            email="david@example.com",
            phone="0123456784",
            attendance_code="12350",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="123456784",
        )

        self.assertIsNone(employee1.personal_email)
        self.assertIsNone(employee2.personal_email)
        # Both should have been created successfully
        self.assertEqual(Employee.objects.filter(personal_email__isnull=True).count(), 2)

    def test_is_onboarding_email_sent_default(self):
        """Test that is_onboarding_email_sent defaults to False"""
        employee = Employee.objects.create(
            fullname="Emily White",
            username="emilywhite",
            email="emily@example.com",
            phone="0123456783",
            attendance_code="12351",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="123456785",
        )
        self.assertFalse(employee.is_onboarding_email_sent)

    def test_is_onboarding_email_sent_can_be_updated(self):
        """Test that is_onboarding_email_sent can be updated"""
        employee = Employee.objects.create(
            fullname="Frank Black",
            username="frankblack",
            email="frank@example.com",
            phone="0123456782",
            attendance_code="12352",
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            citizen_id="123456786",
        )
        self.assertFalse(employee.is_onboarding_email_sent)

        # Update the field
        employee.is_onboarding_email_sent = True
        employee.save()

        # Verify the update persisted
        employee.refresh_from_db()
        self.assertTrue(employee.is_onboarding_email_sent)


class EmployeeFilterTest(TestCase, APITestMixin):
    """Test cases for Employee API filters"""

    def setUp(self):
        """Set up test data"""
        # Patch signal tasks to avoid broker connection during filter tests
        self.hr_report_patcher = patch("apps.hrm.signals.hr_reports.aggregate_hr_reports_for_work_history.delay")
        self.mock_hr_report_delay = self.hr_report_patcher.start()

        self.recruitment_report_patcher = patch(
            "apps.hrm.signals.recruitment_reports.aggregate_recruitment_reports_for_candidate.delay"
        )
        self.mock_recruitment_report_delay = self.recruitment_report_patcher.start()

        # Changed to superuser to bypass RoleBasedPermission for API tests
        self.admin_user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="testpass123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin_user)

        # Create test organizational structure
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

        # Create positions with different is_leadership values
        self.leadership_position = Position.objects.create(
            name="Manager",
            code="MGR",
            is_leadership=True,
        )
        self.regular_position = Position.objects.create(
            name="Staff",
            code="STF",
            is_leadership=False,
        )

        # Create employees with different positions and attributes
        self.leader_employee = Employee.objects.create(
            fullname="Leader One",
            username="leader001",
            email="leader1@example.com",
            phone="1111111111",
            attendance_code="LDR001",
            date_of_birth=date(1985, 3, 15),
            start_date=date(2020, 1, 1),
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.leadership_position,
            is_onboarding_email_sent=True,
            citizen_id="123456789",
        )

        self.staff_employee = Employee.objects.create(
            fullname="Staff One",
            username="staff001",
            email="staff1@example.com",
            phone="2222222222",
            attendance_code="STF001",
            date_of_birth=date(1990, 3, 20),
            start_date=date(2021, 1, 1),
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.regular_position,
            is_onboarding_email_sent=False,
            citizen_id="123456780",
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
            position=self.regular_position,
            is_onboarding_email_sent=True,
            citizen_id="123456781",
        )

        self.march_birthday_employee = Employee.objects.create(
            fullname="March Birthday",
            username="march001",
            email="march1@example.com",
            phone="4444444444",
            attendance_code="MAR001",
            date_of_birth=date(1988, 3, 5),
            start_date=date(2019, 1, 1),
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.leadership_position,
            is_onboarding_email_sent=False,
            citizen_id="123456782",
        )

        # Link a citizen ID file to the leader employee for filter tests
        self.leader_citizen_id_file = FileModel.objects.create(
            purpose="citizen_id",
            file_name="leader_citizen_id.pdf",
            file_path="documents/citizen_ids/leader_citizen_id.pdf",
            size=1024,
        )
        self.leader_employee.citizen_id_file = self.leader_citizen_id_file
        self.leader_employee.save(update_fields=["citizen_id_file"])

        # Create employees with different code types for code_type filter tests
        self.os_employee = Employee.objects.create(
            fullname="OS Employee",
            username="os001",
            email="os1@example.com",
            phone="5555555555",
            attendance_code="OS001",
            date_of_birth=date(1991, 5, 15),
            start_date=date(2022, 1, 1),
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.regular_position,
            code_type=Employee.CodeType.OS,
            citizen_id="123456783",
        )

        self.ctv_employee = Employee.objects.create(
            fullname="CTV Employee",
            username="ctv001",
            email="ctv1@example.com",
            phone="6666666666",
            attendance_code="CTV001",
            date_of_birth=date(1993, 7, 20),
            start_date=date(2023, 1, 1),
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.regular_position,
            code_type=Employee.CodeType.CTV,
            citizen_id="123456784",
        )

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_filter_by_position_is_leadership_true(self, mock_s3_service_class):
        """Test filtering employees by leadership positions"""
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance
        mock_s3_instance.generate_view_url.return_value = "https://example.com/view/citizen_id.pdf"
        mock_s3_instance.generate_download_url.return_value = "https://example.com/download/citizen_id.pdf"

        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"position__is_leadership": "true"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        self.assertEqual(count, 2)
        codes = {item["code"] for item in results}
        self.assertIn(self.leader_employee.code, codes)
        self.assertIn(self.march_birthday_employee.code, codes)
        self.assertNotIn(self.staff_employee.code, codes)
        self.assertNotIn(self.onboarding_employee.code, codes)

    def test_filter_by_position_is_leadership_false(self):
        """Test filtering employees by non-leadership positions"""
        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"position__is_leadership": "false"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        self.assertEqual(count, 4)
        codes = {item["code"] for item in results}
        self.assertIn(self.staff_employee.code, codes)
        self.assertIn(self.onboarding_employee.code, codes)
        self.assertIn(self.os_employee.code, codes)
        self.assertIn(self.ctv_employee.code, codes)
        self.assertNotIn(self.leader_employee.code, codes)
        self.assertNotIn(self.march_birthday_employee.code, codes)

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_filter_by_is_onboarding_email_sent_true(self, mock_s3_service_class):
        """Test filtering employees who received onboarding email"""
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance
        mock_s3_instance.generate_view_url.return_value = "https://example.com/view/citizen_id.pdf"
        mock_s3_instance.generate_download_url.return_value = "https://example.com/download/citizen_id.pdf"

        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"is_onboarding_email_sent": "true"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        self.assertEqual(count, 2)
        codes = {item["code"] for item in results}
        self.assertIn(self.leader_employee.code, codes)
        self.assertIn(self.onboarding_employee.code, codes)
        self.assertNotIn(self.staff_employee.code, codes)
        self.assertNotIn(self.march_birthday_employee.code, codes)

    def test_filter_by_is_onboarding_email_sent_false(self):
        """Test filtering employees who did not receive onboarding email"""
        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"is_onboarding_email_sent": "false"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        self.assertEqual(count, 4)
        codes = {item["code"] for item in results}
        self.assertIn(self.staff_employee.code, codes)
        self.assertIn(self.march_birthday_employee.code, codes)
        self.assertIn(self.os_employee.code, codes)
        self.assertIn(self.ctv_employee.code, codes)
        self.assertNotIn(self.leader_employee.code, codes)
        self.assertNotIn(self.onboarding_employee.code, codes)

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_filter_by_has_citizen_id_file_true(self, mock_s3_service_class):
        """Test filtering employees with uploaded citizen ID files"""
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance
        mock_s3_instance.generate_view_url.return_value = "https://example.com/view/citizen_id.pdf"
        mock_s3_instance.generate_download_url.return_value = "https://example.com/download/citizen_id.pdf"

        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"has_citizen_id_file": "true"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        self.assertEqual(count, 1)
        codes = {item["code"] for item in results}
        self.assertIn(self.leader_employee.code, codes)
        self.assertNotIn(self.staff_employee.code, codes)
        self.assertNotIn(self.onboarding_employee.code, codes)
        self.assertNotIn(self.march_birthday_employee.code, codes)

    def test_filter_by_has_citizen_id_file_false(self):
        """Test filtering employees without citizen ID files"""
        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"has_citizen_id_file": "false"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        self.assertEqual(count, 5)
        codes = {item["code"] for item in results}
        self.assertIn(self.staff_employee.code, codes)
        self.assertIn(self.onboarding_employee.code, codes)
        self.assertIn(self.march_birthday_employee.code, codes)
        self.assertIn(self.os_employee.code, codes)
        self.assertIn(self.ctv_employee.code, codes)
        self.assertNotIn(self.leader_employee.code, codes)

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_filter_by_date_of_birth_month_march(self, mock_s3_service_class):
        """Test filtering employees born in March (month 3)"""
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance
        mock_s3_instance.generate_view_url.return_value = "https://example.com/view/citizen_id.pdf"
        mock_s3_instance.generate_download_url.return_value = "https://example.com/download/citizen_id.pdf"

        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"date_of_birth__month": "3"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        self.assertEqual(count, 3)
        codes = {item["code"] for item in results}
        self.assertIn(self.leader_employee.code, codes)
        self.assertIn(self.staff_employee.code, codes)
        self.assertIn(self.march_birthday_employee.code, codes)
        self.assertNotIn(self.onboarding_employee.code, codes)

    def test_filter_by_date_of_birth_month_june(self):
        """Test filtering employees born in June (month 6)"""
        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"date_of_birth__month": "6"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        self.assertEqual(count, 1)
        codes = {item["code"] for item in results}
        self.assertIn(self.onboarding_employee.code, codes)
        self.assertNotIn(self.leader_employee.code, codes)
        self.assertNotIn(self.staff_employee.code, codes)
        self.assertNotIn(self.march_birthday_employee.code, codes)

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_combined_filter_leadership_and_onboarding(self, mock_s3_service_class):
        """Test combining leadership and onboarding email filters"""
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance
        mock_s3_instance.generate_view_url.return_value = "https://example.com/view/citizen_id.pdf"
        mock_s3_instance.generate_download_url.return_value = "https://example.com/download/citizen_id.pdf"

        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"position__is_leadership": "true", "is_onboarding_email_sent": "true"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        self.assertEqual(count, 1)
        codes = {item["code"] for item in results}
        self.assertIn(self.leader_employee.code, codes)
        self.assertNotIn(self.staff_employee.code, codes)
        self.assertNotIn(self.onboarding_employee.code, codes)
        self.assertNotIn(self.march_birthday_employee.code, codes)

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_combined_filter_leadership_and_birth_month(self, mock_s3_service_class):
        """Test combining leadership and birth month filters"""
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance
        mock_s3_instance.generate_view_url.return_value = "https://example.com/view/citizen_id.pdf"
        mock_s3_instance.generate_download_url.return_value = "https://example.com/download/citizen_id.pdf"

        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"position__is_leadership": "true", "date_of_birth__month": "3"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        self.assertEqual(count, 2)
        codes = {item["code"] for item in results}
        self.assertIn(self.leader_employee.code, codes)
        self.assertIn(self.march_birthday_employee.code, codes)
        self.assertNotIn(self.staff_employee.code, codes)
        self.assertNotIn(self.onboarding_employee.code, codes)

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_filter_by_citizen_id_exact(self, mock_s3_service_class):
        """Test filtering employees by exact citizen_id"""
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance
        mock_s3_instance.generate_view_url.return_value = "https://example.com/view/citizen_id.pdf"
        mock_s3_instance.generate_download_url.return_value = "https://example.com/download/citizen_id.pdf"

        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"citizen_id": "123456789"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        self.assertEqual(count, 1)
        self.assertEqual(results[0]["citizen_id"], "123456789")
        self.assertEqual(results[0]["code"], self.leader_employee.code)

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_filter_by_citizen_id_partial(self, mock_s3_service_class):
        """Test filtering employees by partial citizen_id (icontains)"""
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance
        mock_s3_instance.generate_view_url.return_value = "https://example.com/view/citizen_id.pdf"
        mock_s3_instance.generate_download_url.return_value = "https://example.com/download/citizen_id.pdf"

        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"citizen_id": "12345678"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        # Should match all 6 employees whose citizen_id starts with 12345678
        self.assertEqual(count, 6)
        citizen_ids = {item["citizen_id"] for item in results}
        self.assertIn("123456789", citizen_ids)
        self.assertIn("123456780", citizen_ids)
        self.assertIn("123456781", citizen_ids)
        self.assertIn("123456782", citizen_ids)
        self.assertIn("123456783", citizen_ids)
        self.assertIn("123456784", citizen_ids)

    def test_search_by_citizen_id(self):
        """Test searching employees by citizen_id using search parameter"""
        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"search": "123456782"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        self.assertEqual(count, 1)
        self.assertEqual(results[0]["citizen_id"], "123456782")
        self.assertEqual(results[0]["code"], self.march_birthday_employee.code)

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_filter_by_is_os_code_type_true(self, mock_s3_service_class):
        """Test filtering employees with code_type == OS"""
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance
        mock_s3_instance.generate_view_url.return_value = "https://example.com/view/citizen_id.pdf"
        mock_s3_instance.generate_download_url.return_value = "https://example.com/download/citizen_id.pdf"

        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"is_os_code_type": "true"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        self.assertEqual(count, 1)
        codes = {item["code"] for item in results}
        self.assertIn(self.os_employee.code, codes)
        self.assertNotIn(self.leader_employee.code, codes)
        self.assertNotIn(self.staff_employee.code, codes)
        self.assertNotIn(self.onboarding_employee.code, codes)
        self.assertNotIn(self.march_birthday_employee.code, codes)
        self.assertNotIn(self.ctv_employee.code, codes)

    @patch("apps.files.utils.s3_utils.S3FileUploadService")
    def test_filter_by_is_os_code_type_false(self, mock_s3_service_class):
        """Test filtering employees with code_type != OS"""
        mock_s3_instance = MagicMock()
        mock_s3_service_class.return_value = mock_s3_instance
        mock_s3_instance.generate_view_url.return_value = "https://example.com/view/citizen_id.pdf"
        mock_s3_instance.generate_download_url.return_value = "https://example.com/download/citizen_id.pdf"

        url = reverse("hrm:employee-list")
        response = self.client.get(url, {"is_os_code_type": "false"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        results, count = self.normalize_list_response(data)

        # Should return all employees except the OS type
        self.assertEqual(count, 5)
        codes = {item["code"] for item in results}
        self.assertIn(self.leader_employee.code, codes)
        self.assertIn(self.staff_employee.code, codes)
        self.assertIn(self.onboarding_employee.code, codes)
        self.assertIn(self.march_birthday_employee.code, codes)
        self.assertIn(self.ctv_employee.code, codes)
        self.assertNotIn(self.os_employee.code, codes)

    def tearDown(self):
        # Stop signal patchers
        self.hr_report_patcher.stop()
        self.recruitment_report_patcher.stop()
        return super().tearDown()
