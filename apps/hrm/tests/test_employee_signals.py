"""Tests for Employee signal handlers."""

from datetime import date
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.constants import EmployeeType
from apps.hrm.models import Block, Branch, Department, Employee, EmployeeWorkHistory, Position


@pytest.fixture
def province(db):
    """Create a test province."""
    return Province.objects.create(code="01", name="Test Province")


@pytest.fixture
def administrative_unit(db, province):
    """Create a test administrative unit."""
    return AdministrativeUnit.objects.create(
        code="01",
        name="Test Admin Unit",
        parent_province=province,
        level=AdministrativeUnit.UnitLevel.DISTRICT,
    )


@pytest.fixture
def branch(db, province, administrative_unit):
    """Create a test branch."""
    return Branch.objects.create(
        code="CN001",
        name="Test Branch",
        province=province,
        administrative_unit=administrative_unit,
    )


@pytest.fixture
def block(db, branch):
    """Create a test block."""
    return Block.objects.create(
        code="KH001",
        name="Test Block",
        branch=branch,
        block_type=Block.BlockType.BUSINESS,
    )


@pytest.fixture
def department(db, branch, block):
    """Create a test department."""
    return Department.objects.create(
        code="PB001",
        name="Test Department",
        branch=branch,
        block=block,
    )


@pytest.fixture
def position(db):
    """Create a test position."""
    return Position.objects.create(code="CV001", name="Test Position")


@pytest.fixture
def employee(db, branch, block, department, position):
    """Create a test employee."""
    return Employee.objects.create(
        code="EMP001",
        fullname="Test Employee",
        employee_type=EmployeeType.PROBATION,
        start_date=date(2024, 1, 1),
        branch=branch,
        block=block,
        department=department,
        position=position,
        username="emp001",
        email="emp001@example.com",
        citizen_id="123456789012",
        phone="0900000001",
    )


@pytest.mark.django_db
class TestEmployeeTypeChangeSignal:
    """Tests for employee_type change signal."""

    def test_signal_creates_work_history_on_employee_type_change(self, employee):
        """Test that changing employee_type via save() creates EmployeeWorkHistory."""
        # Arrange
        old_type = employee.employee_type
        new_type = EmployeeType.OFFICIAL
        effective_date = timezone.localdate()

        # Act
        employee._change_type_signal_context = {
            "effective_date": effective_date,
            "note": "Test change via signal",
        }
        employee.employee_type = new_type
        employee.save()

        # Assert
        work_history = EmployeeWorkHistory.objects.filter(
            employee=employee,
            name=EmployeeWorkHistory.EventType.CHANGE_EMPLOYEE_TYPE,
        ).first()

        assert work_history is not None
        assert work_history.old_employee_type == old_type
        assert work_history.new_employee_type == new_type
        assert work_history.date == effective_date
        assert work_history.note == "Test change via signal"

    def test_signal_uses_default_values_when_no_context(self, employee):
        """Test that signal uses default values when no context is provided."""
        # Arrange
        new_type = EmployeeType.OFFICIAL
        today = timezone.localdate()

        # Act - no context set
        employee.employee_type = new_type
        employee.save()

        # Assert
        work_history = EmployeeWorkHistory.objects.filter(
            employee=employee,
            name=EmployeeWorkHistory.EventType.CHANGE_EMPLOYEE_TYPE,
        ).first()

        assert work_history is not None
        assert work_history.date == today
        assert work_history.note == ""

    def test_signal_does_not_create_history_when_type_unchanged(self, employee):
        """Test that no history is created when employee_type doesn't change."""
        # Arrange
        initial_count = EmployeeWorkHistory.objects.filter(
            employee=employee,
            name=EmployeeWorkHistory.EventType.CHANGE_EMPLOYEE_TYPE,
        ).count()

        # Act - save without changing employee_type
        employee.fullname = "Updated Name"
        employee.save()

        # Assert
        final_count = EmployeeWorkHistory.objects.filter(
            employee=employee,
            name=EmployeeWorkHistory.EventType.CHANGE_EMPLOYEE_TYPE,
        ).count()
        assert final_count == initial_count

    def test_signal_does_not_create_history_on_new_employee(self, branch, block, department, position):
        """Test that no CHANGE_EMPLOYEE_TYPE history is created for new employees."""
        # Act
        new_employee = Employee.objects.create(
            code="EMP002",
            fullname="New Employee",
            employee_type=EmployeeType.PROBATION,
            start_date=date(2024, 1, 1),
            branch=branch,
            block=block,
            department=department,
            position=position,
            username="emp002",
            email="emp002@example.com",
            citizen_id="123456789013",
            phone="0900000002",
        )

        # Assert
        history_count = EmployeeWorkHistory.objects.filter(
            employee=new_employee,
            name=EmployeeWorkHistory.EventType.CHANGE_EMPLOYEE_TYPE,
        ).count()
        assert history_count == 0

    def test_signal_creates_history_with_contract_reference(self, employee):
        """Test that signal creates history with contract reference when provided."""
        from apps.hrm.models import Contract, ContractType

        # Arrange
        contract_type = ContractType.objects.create(
            code="HDLD",
            name="Labor Contract",
            category=ContractType.Category.CONTRACT,
        )
        contract = Contract.objects.create(
            employee=employee,
            contract_type=contract_type,
            effective_date=timezone.localdate(),
            sign_date=timezone.localdate(),
        )

        # Act
        employee._change_type_signal_context = {
            "effective_date": timezone.localdate(),
            "note": "Contract import",
            "contract": contract,
        }
        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        # Assert
        work_history = EmployeeWorkHistory.objects.filter(
            employee=employee,
            name=EmployeeWorkHistory.EventType.CHANGE_EMPLOYEE_TYPE,
        ).first()

        assert work_history is not None
        assert work_history.contract == contract

    def test_pre_save_signal_captures_old_employee_type(self, employee):
        """Test that pre_save signal correctly captures old employee_type."""
        # Arrange
        old_type = employee.employee_type

        # Act
        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        # Assert - check that work history has correct old_employee_type
        work_history = EmployeeWorkHistory.objects.filter(
            employee=employee,
            name=EmployeeWorkHistory.EventType.CHANGE_EMPLOYEE_TYPE,
        ).first()

        assert work_history is not None
        assert work_history.old_employee_type == old_type

    @patch("apps.hrm.signals.employee.create_employee_type_change_event")
    def test_signal_calls_service_function_without_contract(self, mock_create_event, employee):
        """Test that signal calls create_employee_type_change_event when no contract in context."""
        # Arrange
        effective_date = timezone.localdate()

        # Act
        employee._change_type_signal_context = {
            "effective_date": effective_date,
            "note": "Test note",
        }
        employee.employee_type = EmployeeType.OFFICIAL
        employee.save()

        # Assert
        mock_create_event.assert_called_once()
        call_kwargs = mock_create_event.call_args[1]
        assert call_kwargs["employee"] == employee
        assert call_kwargs["old_employee_type"] == EmployeeType.PROBATION
        assert call_kwargs["new_employee_type"] == EmployeeType.OFFICIAL
        assert call_kwargs["effective_date"] == effective_date
        assert call_kwargs["note"] == "Test note"
