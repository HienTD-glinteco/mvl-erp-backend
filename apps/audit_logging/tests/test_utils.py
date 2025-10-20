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
        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")

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
        self.assertIsNone(log_data["position_id"])
        self.assertIsNone(log_data["position_name"])

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
        # Position should be None if no organization chart entry exists
        self.assertIsNone(log_data["position_id"])
        self.assertIsNone(log_data["position_name"])

    def test_prepare_user_info_with_position(self):
        """Test that position fields are captured from organization chart."""
        from datetime import date

        from apps.core.models import AdministrativeUnit, Province
        from apps.hrm.models import Block, Branch, Department, Employee, OrganizationChart, Position

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
            department=department,
        )

        # Link employee to user
        employee.user = self.user
        employee.save()

        # Create position
        position = Position.objects.create(
            name="Test Position",
            code="TP01",
        )

        # Create organization chart entry
        OrganizationChart.objects.create(
            employee=self.user,
            position=position,
            department=department,
            start_date=date.today(),
            is_primary=True,
            is_active=True,
        )

        log_data = {}
        prepare_user_info(log_data, self.user)

        self.assertEqual(log_data["user_id"], str(self.user.pk))
        self.assertEqual(log_data["username"], self.user.username)
        self.assertEqual(log_data["employee_code"], "MV001")
        self.assertEqual(log_data["full_name"], "Test User Full Name")
        self.assertEqual(log_data["department_id"], str(department.pk))
        self.assertEqual(log_data["department_name"], "Test Department")
        self.assertEqual(log_data["position_id"], str(position.pk))
        self.assertEqual(log_data["position_name"], "Test Position")

    def test_prepare_user_info_with_multiple_positions(self):
        """Test that only primary position is captured when user has multiple positions."""
        from datetime import date

        from apps.core.models import AdministrativeUnit, Province
        from apps.hrm.models import Block, Branch, Department, Employee, OrganizationChart, Position

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
            department=department,
        )

        # Link employee to user
        employee.user = self.user
        employee.save()

        # Create primary position
        primary_position = Position.objects.create(
            name="Primary Position",
            code="PP01",
        )

        # Create secondary position
        secondary_position = Position.objects.create(
            name="Secondary Position",
            code="SP01",
        )

        # Create organization chart entries
        OrganizationChart.objects.create(
            employee=self.user,
            position=primary_position,
            department=department,
            start_date=date.today(),
            is_primary=True,
            is_active=True,
        )

        OrganizationChart.objects.create(
            employee=self.user,
            position=secondary_position,
            department=department,
            start_date=date.today(),
            is_primary=False,
            is_active=True,
        )

        log_data = {}
        prepare_user_info(log_data, self.user)

        # Should capture the primary position
        self.assertEqual(log_data["position_id"], str(primary_position.pk))
        self.assertEqual(log_data["position_name"], "Primary Position")

    def test_prepare_user_info_with_no_user(self):
        """Test that function handles None user gracefully."""
        log_data = {}
        prepare_user_info(log_data, None)

        self.assertIsNone(log_data["user_id"])
