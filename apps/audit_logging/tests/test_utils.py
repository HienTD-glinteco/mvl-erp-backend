# audit_logging/tests/test_utils.py
"""
Tests for audit logging utility functions.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.audit_logging.utils import prepare_user_info

User = get_user_model()


class TestPrepareUserInfo(TestCase):
    """Test cases for prepare_user_info function."""

    def setUp(self):
        """Set up test data."""
        # Changed to superuser to bypass RoleBasedPermission for API tests
        self.user = User.objects.create_superuser(username="testuser", email="test@example.com", password="testpass123")

    def test_prepare_user_info_basic_fields(self):
        """Test that basic user fields are captured."""
        log_data = {}
        prepare_user_info(log_data, self.user)

        self.assertEqual(log_data["user_id"], str(self.user.pk))
        self.assertEqual(log_data["username"], self.user.username)
        # User without employee record should have empty employee fields
        self.assertEqual(log_data["employee_code"], "")
        self.assertEqual(log_data["full_name"], "")
        self.assertIsNone(log_data["department_id"])
        self.assertIsNone(log_data["department_name"])

    def test_prepare_user_info_with_employee(self):
        """Test that employee fields are captured when user has employee record."""
        from apps.core.models import AdministrativeUnit, Province
        from apps.hrm.models import Block, Branch, Department, Employee

        # Create organizational structure
        province = Province.objects.create(name="Test Province", code="TP")
        admin_unit = AdministrativeUnit.objects.create(
            name="Test Admin Unit",
            code="TAU",
            parent_province=province,
            level="district",
        )
        branch = Branch.objects.create(
            name="Test Branch",
            code="TB01",
            province=province,
            administrative_unit=admin_unit,
        )
        block = Block.objects.create(
            name="Test Block",
            code="BL01",
            block_type="support",
            branch=branch,
        )
        department = Department.objects.create(
            name="Test Department",
            code="TD01",
            branch=branch,
            block=block,
        )

        # Create employee
        employee = Employee.objects.create(
            code="MV001",
            fullname="Test User Full Name",
            username="testuser_emp",
            email="testuser_emp@example.com",
            personal_email="testuser_personal@example.com",
            phone="0123456789",
            attendance_code="12345",
            date_of_birth="1990-01-01",
            start_date="2024-01-01",
            department=department,
        )

        # Link employee to user
        employee.user = self.user
        employee.save()

        log_data = {}
        prepare_user_info(log_data, self.user)

        self.assertEqual(log_data["user_id"], str(self.user.pk))
        self.assertEqual(log_data["username"], self.user.username)
        self.assertEqual(log_data["employee_code"], "MV001")
        self.assertEqual(log_data["full_name"], "Test User Full Name")
        self.assertEqual(log_data["department_id"], str(department.pk))
        self.assertEqual(log_data["department_name"], "Test Department")

    def test_prepare_user_info_with_no_user(self):
        """Test that function handles None user gracefully."""
        log_data = {}
        prepare_user_info(log_data, None)

        self.assertIsNone(log_data["user_id"])
