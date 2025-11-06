"""Tests for automatic EmployeeWorkHistory creation."""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import Block, Branch, Department, Employee, EmployeeWorkHistory, Position

User = get_user_model()


class EmployeeWorkHistoryAutoCreationTest(TestCase):
    """Test cases for automatic work history creation on employee changes."""

    def setUp(self):
        """Set up test data."""
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
            name="Main Branch",
            province=self.province,
            administrative_unit=self.admin_unit,
        )
        self.block = Block.objects.create(
            code="KH001", name="Main Block", branch=self.branch, block_type=Block.BlockType.BUSINESS
        )
        self.department = Department.objects.create(
            code="PB001", name="Engineering Department", block=self.block, branch=self.branch
        )
        self.position = Position.objects.create(code="CV001", name="Developer")
        self.senior_position = Position.objects.create(code="CV002", name="Senior Developer")

        # Create second department for transfer tests
        self.department2 = Department.objects.create(
            code="PB002", name="HR Department", block=self.block, branch=self.branch
        )

    def test_create_employee_creates_initial_work_history(self):
        """Test that creating an employee automatically creates initial work history."""
        # Arrange & Act
        employee = Employee.objects.create(
            fullname="John Doe",
            username="johndoe_auto",
            email="johndoe_auto@example.com",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            start_date=date(2024, 1, 1),
            citizen_id="000000030001",
            attendance_code="10001",
            phone="0123456789",
            status=Employee.Status.ONBOARDING,
        )

        # Assert
        work_histories = EmployeeWorkHistory.objects.filter(employee=employee)
        self.assertEqual(work_histories.count(), 1)

        history = work_histories.first()
        self.assertEqual(history.name, EmployeeWorkHistory.EventType.CHANGE_STATUS)
        self.assertEqual(history.date, employee.start_date)
        self.assertIn("created", history.detail.lower())
        self.assertIn("onboarding", history.detail.lower())

    def test_change_employee_status_creates_work_history(self):
        """Test that changing employee status creates work history record."""
        # Arrange - Create employee with ONBOARDING status
        employee = Employee.objects.create(
            fullname="Jane Smith",
            username="janesmith_auto",
            email="janesmith_auto@example.com",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            start_date=date(2024, 1, 1),
            citizen_id="000000030002",
            attendance_code="10002",
            phone="0123456788",
            status=Employee.Status.ONBOARDING,
        )

        # Clear initial history to test only the status change
        EmployeeWorkHistory.objects.filter(employee=employee).delete()

        # Act - Change status to ACTIVE
        employee.status = Employee.Status.ACTIVE
        employee.save()

        # Assert
        work_histories = EmployeeWorkHistory.objects.filter(
            employee=employee, name=EmployeeWorkHistory.EventType.CHANGE_STATUS
        )
        self.assertEqual(work_histories.count(), 1)

        history = work_histories.first()
        self.assertIn("onboarding", history.detail.lower())
        self.assertIn("active", history.detail.lower())

    def test_change_employee_position_creates_work_history(self):
        """Test that changing employee position creates work history record."""
        # Arrange - Create employee
        employee = Employee.objects.create(
            fullname="Bob Johnson",
            username="bobjohnson_auto",
            email="bobjohnson_auto@example.com",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            start_date=date(2024, 1, 1),
            citizen_id="000000030003",
            attendance_code="10003",
            phone="0123456787",
        )

        # Clear initial history to test only the position change
        EmployeeWorkHistory.objects.filter(employee=employee).delete()

        # Act - Change position
        employee.position = self.senior_position
        employee.save()

        # Assert
        work_histories = EmployeeWorkHistory.objects.filter(
            employee=employee, name=EmployeeWorkHistory.EventType.CHANGE_POSITION
        )
        self.assertEqual(work_histories.count(), 1)

        history = work_histories.first()
        self.assertIn("developer", history.detail.lower())
        self.assertIn("senior developer", history.detail.lower())

    def test_change_employee_department_creates_transfer_history(self):
        """Test that changing employee department creates transfer work history record."""
        # Arrange - Create employee
        employee = Employee.objects.create(
            fullname="Alice Williams",
            username="alicewilliams_auto",
            email="alicewilliams_auto@example.com",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            start_date=date(2024, 1, 1),
            citizen_id="000000030004",
            attendance_code="10004",
            phone="0123456786",
        )

        # Clear initial history to test only the department change
        EmployeeWorkHistory.objects.filter(employee=employee).delete()

        # Act - Change department (transfer)
        employee.department = self.department2
        employee.save()

        # Assert
        work_histories = EmployeeWorkHistory.objects.filter(
            employee=employee, name=EmployeeWorkHistory.EventType.TRANSFER
        )
        self.assertEqual(work_histories.count(), 1)

        history = work_histories.first()
        self.assertIn("transferred", history.detail.lower())
        self.assertIn("engineering", history.detail.lower())
        self.assertIn("hr", history.detail.lower())

    def test_employee_resignation_creates_work_history(self):
        """Test that resigning an employee creates work history record."""
        # Arrange - Create active employee
        employee = Employee.objects.create(
            fullname="Charlie Brown",
            username="charliebrown_auto",
            email="charliebrown_auto@example.com",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            start_date=date(2024, 1, 1),
            citizen_id="000000030005",
            attendance_code="10005",
            phone="0123456785",
            status=Employee.Status.ACTIVE,
        )

        # Clear initial history to test only the resignation
        EmployeeWorkHistory.objects.filter(employee=employee).delete()

        # Act - Resign employee
        employee.status = Employee.Status.RESIGNED
        employee.resignation_start_date = date(2024, 12, 31)
        employee.resignation_reason = Employee.ResignationReason.VOLUNTARY_CAREER_CHANGE
        employee.save()

        # Assert
        work_histories = EmployeeWorkHistory.objects.filter(
            employee=employee, name=EmployeeWorkHistory.EventType.CHANGE_STATUS
        )
        self.assertEqual(work_histories.count(), 1)

        history = work_histories.first()
        self.assertIn("resigned", history.detail.lower())
        self.assertEqual(history.date, employee.resignation_start_date)

    def test_multiple_changes_create_multiple_histories(self):
        """Test that multiple changes create multiple work history records."""
        # Arrange - Create employee
        employee = Employee.objects.create(
            fullname="David Lee",
            username="davidlee_auto",
            email="davidlee_auto@example.com",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            start_date=date(2024, 1, 1),
            citizen_id="000000030006",
            attendance_code="10006",
            phone="0123456784",
            status=Employee.Status.ONBOARDING,
        )

        # Clear initial history
        EmployeeWorkHistory.objects.filter(employee=employee).delete()

        # Act - Make multiple changes
        # Change 1: Status to ACTIVE
        employee.status = Employee.Status.ACTIVE
        employee.save()

        # Change 2: Position change
        employee.position = self.senior_position
        employee.save()

        # Change 3: Department transfer
        employee.department = self.department2
        employee.save()

        # Assert
        work_histories = EmployeeWorkHistory.objects.filter(employee=employee).order_by("created_at")
        self.assertEqual(work_histories.count(), 3)

        # Check status change
        status_history = work_histories.filter(name=EmployeeWorkHistory.EventType.CHANGE_STATUS).first()
        self.assertIsNotNone(status_history)
        self.assertIn("active", status_history.detail.lower())

        # Check position change
        position_history = work_histories.filter(name=EmployeeWorkHistory.EventType.CHANGE_POSITION).first()
        self.assertIsNotNone(position_history)
        self.assertIn("senior developer", position_history.detail.lower())

        # Check transfer
        transfer_history = work_histories.filter(name=EmployeeWorkHistory.EventType.TRANSFER).first()
        self.assertIsNotNone(transfer_history)
        self.assertIn("transferred", transfer_history.detail.lower())

    def test_work_history_contains_correct_organizational_data(self):
        """Test that work history records contain correct organizational data."""
        # Arrange & Act
        employee = Employee.objects.create(
            fullname="Test Employee",
            username="testemployee_auto",
            email="testemployee_auto@example.com",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            start_date=date(2024, 1, 1),
            citizen_id="000000030008",
            attendance_code="10008",
            phone="0123456782",
        )

        # Assert
        history = EmployeeWorkHistory.objects.filter(employee=employee).first()
        self.assertIsNotNone(history)
        self.assertEqual(history.branch, employee.branch)
        self.assertEqual(history.block, employee.block)
        self.assertEqual(history.department, employee.department)
        self.assertEqual(history.position, employee.position)
