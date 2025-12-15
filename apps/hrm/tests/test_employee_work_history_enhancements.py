"""Tests for EmployeeWorkHistory enhancements including new fields and service helper functions."""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import (
    Block,
    Branch,
    Contract,
    ContractType,
    Department,
    Employee,
    EmployeeWorkHistory,
    Position,
)
from apps.hrm.services.employee import (
    create_contract_change_event,
    create_position_change_event,
    create_state_change_event,
    create_transfer_event,
)

User = get_user_model()


class EmployeeWorkHistoryEnhancementsTest(TransactionTestCase):
    """Test cases for EmployeeWorkHistory model enhancements."""

    def setUp(self):
        """Set up test data."""
        # Clear all existing data for clean tests
        EmployeeWorkHistory.objects.all().delete()
        Employee.objects.all().delete()
        User.objects.all().delete()

        # Changed to superuser to bypass RoleBasedPermission for API tests
        self.user = User.objects.create_superuser(
            username="testuser", email="test@example.com", password="testpass123"
        )

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
        self.position = Position.objects.create(code="CV001", name="Senior Developer")

        # Create test employee
        self.employee = Employee.objects.create(
            fullname="John Doe",
            username="johndoe_enhanced",
            email="johndoe_enhanced@example.com",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            start_date="2024-01-01",
            citizen_id="000000030301",
            attendance_code="12345",
            phone="0123456789",
        )

    def test_change_contract_event_type_exists(self):
        """Test that CHANGE_CONTRACT event type is available."""
        # Assert
        self.assertIn(
            EmployeeWorkHistory.EventType.CHANGE_CONTRACT,
            [choice[0] for choice in EmployeeWorkHistory.EventType.choices],
        )

    def test_retain_seniority_field(self):
        """Test retain_seniority field for return to work events."""
        # Act
        work_history = EmployeeWorkHistory.objects.create(
            employee=self.employee,
            date=date(2024, 6, 1),
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            detail="Returned from maternity leave",
            retain_seniority=True,
        )

        # Assert
        self.assertTrue(work_history.retain_seniority)

    def test_resignation_reason_field(self):
        """Test resignation_reason field with Employee.ResignationReason choices."""
        # Act
        work_history = EmployeeWorkHistory.objects.create(
            employee=self.employee,
            date=date(2024, 6, 1),
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            detail="Employee resigned",
            status=Employee.Status.RESIGNED,
            resignation_reason=Employee.ResignationReason.VOLUNTARY_CAREER_CHANGE,
        )

        # Assert
        self.assertEqual(work_history.resignation_reason, Employee.ResignationReason.VOLUNTARY_CAREER_CHANGE)
        self.assertIsNotNone(work_history.get_resignation_reason_display())


class EmployeeWorkHistoryServiceTest(TransactionTestCase):
    """Test cases for EmployeeWorkHistory QuerySet helper methods."""

    def setUp(self):
        """Set up test data."""
        # Clear all existing data for clean tests
        EmployeeWorkHistory.objects.all().delete()
        Employee.objects.all().delete()
        User.objects.all().delete()

        self.user = User.objects.create_superuser(
            username="testuser", email="test@example.com", password="testpass123"
        )

        # Create organizational structure
        self.province = Province.objects.create(code="02", name="Test Province 2")
        self.admin_unit = AdministrativeUnit.objects.create(
            code="02",
            name="Test Admin Unit 2",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )

        self.branch = Branch.objects.create(
            code="CN002",
            name="Main Branch 2",
            province=self.province,
            administrative_unit=self.admin_unit,
        )
        self.block = Block.objects.create(
            code="KH002", name="Main Block 2", branch=self.branch, block_type=Block.BlockType.BUSINESS
        )
        self.department = Department.objects.create(
            code="PB002", name="Engineering Department 2", block=self.block, branch=self.branch
        )
        self.new_department = Department.objects.create(
            code="PB003", name="HR Department", block=self.block, branch=self.branch
        )
        self.position = Position.objects.create(code="CV002", name="Developer")
        self.new_position = Position.objects.create(code="CV003", name="Senior Developer")
        self.contract_type_a = ContractType.objects.create(name="Contract Type A")
        self.contract_type_b = ContractType.objects.create(name="Contract Type B")

        # Create test employee
        self.employee = Employee.objects.create(
            fullname="Jane Smith",
            username="janesmith_qs",
            email="janesmith_qs@example.com",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            start_date="2024-01-01",
            citizen_id="000000030302",
            attendance_code="54321",
            phone="0987654321",
        )
        self.old_contract = Contract.objects.create(
            employee=self.employee,
            contract_type=self.contract_type_a,
            sign_date=date(2023, 1, 1),
            effective_date=date(2023, 1, 1),
            code="OLD_CONTRACT",
            contract_number="OLD_NUMBER",
        )
        self.new_contract = Contract.objects.create(
            employee=self.employee,
            contract_type=self.contract_type_b,
            sign_date=date(2024, 1, 1),
            effective_date=date(2024, 1, 1),
            code="NEW_CONTRACT",
            contract_number="NEW_NUMBER",
        )

    def test_create_state_change_event(self):
        """Test creating a state change event using service helper."""
        # Act
        work_history = create_state_change_event(
            employee=self.employee,
            old_status=Employee.Status.ACTIVE,
            new_status=Employee.Status.MATERNITY_LEAVE,
            effective_date=date(2024, 6, 1),
            start_date=date(2024, 6, 1),
            end_date=date(2024, 12, 1),
            note="Maternity leave for 6 months",
        )

        # Assert
        self.assertIsNotNone(work_history.id)
        self.assertEqual(work_history.employee, self.employee)
        self.assertEqual(work_history.name, EmployeeWorkHistory.EventType.CHANGE_STATUS)
        self.assertEqual(work_history.status, Employee.Status.MATERNITY_LEAVE)
        self.assertEqual(work_history.from_date, date(2024, 6, 1))
        self.assertEqual(work_history.to_date, date(2024, 12, 1))
        self.assertEqual(work_history.note, "Maternity leave for 6 months")
        self.assertEqual(work_history.previous_data["status"], Employee.Status.ACTIVE)

    def test_create_position_change_event(self):
        """Test creating a position change event using service helper."""
        # Act
        work_history = create_position_change_event(
            employee=self.employee,
            old_position=self.position,
            new_position=self.new_position,
            effective_date=date(2024, 6, 1),
            note="Promoted due to excellent performance",
        )

        # Assert
        self.assertIsNotNone(work_history.id)
        self.assertEqual(work_history.employee, self.employee)
        self.assertEqual(work_history.name, EmployeeWorkHistory.EventType.CHANGE_POSITION)
        self.assertEqual(work_history.note, "Promoted due to excellent performance")
        self.assertEqual(work_history.previous_data["position_id"], self.position.id)
        self.assertIn(self.position.name, work_history.detail)
        self.assertIn(self.new_position.name, work_history.detail)

    def test_create_transfer_event(self):
        """Test creating a transfer event using service helper."""
        # Act
        work_history = create_transfer_event(
            employee=self.employee,
            old_department=self.department,
            new_department=self.new_department,
            old_position=self.position,
            new_position=self.new_position,
            effective_date=date(2024, 6, 1),
            note="Transferred to HR for new role",
        )

        # Assert
        self.assertIsNotNone(work_history.id)
        self.assertEqual(work_history.employee, self.employee)
        self.assertEqual(work_history.name, EmployeeWorkHistory.EventType.TRANSFER)
        self.assertEqual(work_history.note, "Transferred to HR for new role")
        self.assertEqual(work_history.previous_data["department_id"], self.department.id)
        self.assertEqual(work_history.previous_data["position_id"], self.position.id)
        self.assertIn(self.department.name, work_history.detail)
        self.assertIn(self.new_department.name, work_history.detail)

    def test_create_transfer_event_defaults_to_today(self):
        """Test that transfer event defaults to today's date if no effective_date provided."""
        # Act
        work_history = create_transfer_event(
            employee=self.employee,
            old_department=self.department,
            new_department=self.new_department,
        )

        # Assert
        self.assertEqual(work_history.date, date.today())

    def test_create_contract_change_event(self):
        """Test creating a contract change event using service helper."""
        # Act
        work_history = create_contract_change_event(
            employee=self.employee,
            old_contract=self.old_contract,
            new_contract=self.new_contract,
            effective_date=date(2024, 6, 1),
            note="Contract updated",
        )

        # Assert
        self.assertIsNotNone(work_history.id)
        self.assertEqual(work_history.employee, self.employee)
        self.assertEqual(work_history.name, EmployeeWorkHistory.EventType.CHANGE_CONTRACT)
        self.assertEqual(work_history.contract, self.new_contract)
        self.assertEqual(work_history.note, "Contract updated")
        self.assertEqual(work_history.previous_data["contract_id"], self.old_contract.id)
        self.assertEqual(work_history.previous_data["contract_code"], self.old_contract.code)
        self.assertIn(self.old_contract.contract_number, work_history.detail)
        self.assertIn(self.new_contract.contract_number, work_history.detail)

    def test_create_position_change_event_from_none(self):
        """Test creating a position change event when old position is None."""
        # Act
        work_history = create_position_change_event(
            employee=self.employee,
            old_position=None,
            new_position=self.new_position,
            effective_date=date(2024, 6, 1),
        )

        # Assert
        self.assertIsNotNone(work_history.id)
        self.assertIsNone(work_history.previous_data["position_id"])

    def test_create_contract_change_event_from_none(self):
        """Test creating a contract change event when old contract is None."""
        # Act
        work_history = create_contract_change_event(
            employee=self.employee,
            old_contract=None,
            new_contract=self.new_contract,
            effective_date=date(2024, 6, 1),
        )

        # Assert
        self.assertIsNotNone(work_history.id)
        self.assertIsNone(work_history.previous_data["contract_id"])
