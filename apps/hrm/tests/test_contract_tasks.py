"""Tests for HRM contract status update task."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import Block, Branch, Contract, ContractType, Department, Employee
from apps.hrm.tasks import check_contract_status


@pytest.fixture
def province(db):
    """Create a province for testing."""
    return Province.objects.create(code="CS", name="Contract Status Province")


@pytest.fixture
def admin_unit(db, province):
    """Create an administrative unit for testing."""
    return AdministrativeUnit.objects.create(
        code="CS",
        name="Contract Status Admin Unit",
        parent_province=province,
        level=AdministrativeUnit.UnitLevel.DISTRICT,
    )


@pytest.fixture
def organization(db, province, admin_unit):
    """Create organization hierarchy for testing."""
    branch = Branch.objects.create(
        name="Contract Status Branch",
        province=province,
        administrative_unit=admin_unit,
    )
    block = Block.objects.create(
        name="Contract Status Block",
        branch=branch,
        block_type=Block.BlockType.BUSINESS,
    )
    department = Department.objects.create(
        name="Contract Status Department",
        block=block,
        branch=branch,
    )
    return {"branch": branch, "block": block, "department": department}


@pytest.fixture
def contract_type(db):
    """Create a contract type for testing."""
    return ContractType.objects.create(
        name="Test Contract Type For Status",
        symbol="TCS",
        duration_type=ContractType.DurationType.FIXED,
        duration_months=12,
        base_salary=Decimal("10000000"),
        annual_leave_days=12,
    )


@pytest.fixture
def employee(db, organization):
    """Create an employee for testing."""
    return Employee.objects.create(
        fullname="Contract Status Test Employee",
        email="contract.status@test.com",
        username="contractstatususer",
        phone="0123456789",
        citizen_id="999888777666",
        attendance_code="CST001",
        start_date=date.today(),
        department=organization["department"],
        block=organization["block"],
        branch=organization["branch"],
        personal_email="contract.status.personal@test.com",
    )


def create_contract_with_forced_status(
    employee,
    contract_type,
    sign_date,
    effective_date,
    expiration_date,
    forced_status,
):
    """Create a contract with a forced status value, bypassing save logic.

    The Contract model recalculates status on save for non-DRAFT contracts.
    This helper creates contracts with DRAFT status first, then uses a direct
    DB update to set the desired status without triggering the save logic.

    Args:
        employee: Employee instance
        contract_type: ContractType instance
        sign_date: Date when contract was signed
        effective_date: Date when contract becomes effective
        expiration_date: Date when contract expires (None for indefinite)
        forced_status: ContractStatus value to force set

    Returns:
        Contract: The created contract with the forced status
    """
    contract = Contract.objects.create(
        employee=employee,
        contract_type=contract_type,
        sign_date=sign_date,
        effective_date=effective_date,
        expiration_date=expiration_date,
        status=Contract.ContractStatus.DRAFT,
        base_salary=contract_type.base_salary,
    )
    # Force set status using direct DB update to bypass save logic
    Contract.objects.filter(pk=contract.pk).update(status=forced_status)
    contract.refresh_from_db()
    return contract


@pytest.mark.django_db
class TestCheckContractStatusTask:
    """Test cases for check_contract_status task."""

    def test_updates_active_to_about_to_expire(self, db, employee, contract_type):
        """Test contract transitions from ACTIVE to ABOUT_TO_EXPIRE."""
        # Arrange - Create contract that should become ABOUT_TO_EXPIRE
        contract = create_contract_with_forced_status(
            employee=employee,
            contract_type=contract_type,
            sign_date=date.today() - timedelta(days=350),
            effective_date=date.today() - timedelta(days=340),
            expiration_date=date.today() + timedelta(days=15),
            forced_status=Contract.ContractStatus.ACTIVE,
        )
        assert contract.status == Contract.ContractStatus.ACTIVE  # Verify setup

        # Act
        result = check_contract_status()

        # Assert
        contract.refresh_from_db()
        assert contract.status == Contract.ContractStatus.ABOUT_TO_EXPIRE
        assert result["updated_count"] >= 1
        assert result["about_to_expire_count"] >= 1

    def test_updates_about_to_expire_to_expired(self, db, employee, contract_type):
        """Test contract transitions from ABOUT_TO_EXPIRE to EXPIRED."""
        # Arrange - Create contract that should become EXPIRED
        contract = create_contract_with_forced_status(
            employee=employee,
            contract_type=contract_type,
            sign_date=date.today() - timedelta(days=400),
            effective_date=date.today() - timedelta(days=380),
            expiration_date=date.today() - timedelta(days=10),
            forced_status=Contract.ContractStatus.ABOUT_TO_EXPIRE,
        )
        assert contract.status == Contract.ContractStatus.ABOUT_TO_EXPIRE  # Verify setup

        # Act
        result = check_contract_status()

        # Assert
        contract.refresh_from_db()
        assert contract.status == Contract.ContractStatus.EXPIRED
        assert result["updated_count"] >= 1
        assert result["expired_count"] >= 1

    def test_updates_active_to_expired(self, db, employee, contract_type):
        """Test contract transitions directly from ACTIVE to EXPIRED."""
        # Arrange - Create contract that should become EXPIRED
        contract = create_contract_with_forced_status(
            employee=employee,
            contract_type=contract_type,
            sign_date=date.today() - timedelta(days=400),
            effective_date=date.today() - timedelta(days=380),
            expiration_date=date.today() - timedelta(days=5),
            forced_status=Contract.ContractStatus.ACTIVE,
        )
        assert contract.status == Contract.ContractStatus.ACTIVE  # Verify setup

        # Act
        result = check_contract_status()

        # Assert
        contract.refresh_from_db()
        assert contract.status == Contract.ContractStatus.EXPIRED
        assert result["updated_count"] >= 1
        assert result["expired_count"] >= 1

    def test_preserves_draft_status(self, db, employee, contract_type):
        """Test that DRAFT contracts are not updated."""
        # Arrange - Create draft contract with past expiration date
        contract = Contract.objects.create(
            employee=employee,
            contract_type=contract_type,
            sign_date=date.today() - timedelta(days=400),
            effective_date=date.today() - timedelta(days=380),
            expiration_date=date.today() - timedelta(days=5),
            status=Contract.ContractStatus.DRAFT,
            base_salary=contract_type.base_salary,
        )

        # Act
        result = check_contract_status()

        # Assert
        contract.refresh_from_db()
        assert contract.status == Contract.ContractStatus.DRAFT
        # DRAFT contracts are excluded from processing
        assert result["total_contracts"] == 0

    def test_updates_not_effective_to_active(self, db, employee, contract_type):
        """Test contract transitions from NOT_EFFECTIVE to ACTIVE."""
        # Arrange - Create contract that should become ACTIVE
        contract = create_contract_with_forced_status(
            employee=employee,
            contract_type=contract_type,
            sign_date=date.today() - timedelta(days=30),
            effective_date=date.today() - timedelta(days=10),
            expiration_date=date.today() + timedelta(days=355),
            forced_status=Contract.ContractStatus.NOT_EFFECTIVE,
        )
        assert contract.status == Contract.ContractStatus.NOT_EFFECTIVE  # Verify setup

        # Act
        result = check_contract_status()

        # Assert
        contract.refresh_from_db()
        assert contract.status == Contract.ContractStatus.ACTIVE
        assert result["updated_count"] >= 1
        assert result["active_count"] >= 1

    def test_indefinite_contract_stays_active(self, db, employee, contract_type):
        """Test indefinite contract remains ACTIVE."""
        # Arrange - Create indefinite contract that should stay ACTIVE
        contract = create_contract_with_forced_status(
            employee=employee,
            contract_type=contract_type,
            sign_date=date.today() - timedelta(days=30),
            effective_date=date.today() - timedelta(days=10),
            expiration_date=None,  # Indefinite
            forced_status=Contract.ContractStatus.ACTIVE,
        )
        assert contract.status == Contract.ContractStatus.ACTIVE  # Verify setup

        # Act
        result = check_contract_status()

        # Assert
        contract.refresh_from_db()
        assert contract.status == Contract.ContractStatus.ACTIVE
        # No change expected since status is already correct
        assert result["updated_count"] == 0

    def test_returns_correct_summary(self, db, employee, contract_type):
        """Test that the task returns correct summary."""
        # Arrange - Create multiple contracts with different statuses
        # Contract 1: ACTIVE that should become ABOUT_TO_EXPIRE
        create_contract_with_forced_status(
            employee=employee,
            contract_type=contract_type,
            sign_date=date.today() - timedelta(days=350),
            effective_date=date.today() - timedelta(days=340),
            expiration_date=date.today() + timedelta(days=15),
            forced_status=Contract.ContractStatus.ACTIVE,
        )

        # Contract 2: ABOUT_TO_EXPIRE that should become EXPIRED
        create_contract_with_forced_status(
            employee=employee,
            contract_type=contract_type,
            sign_date=date.today() - timedelta(days=400),
            effective_date=date.today() - timedelta(days=380),
            expiration_date=date.today() - timedelta(days=5),
            forced_status=Contract.ContractStatus.ABOUT_TO_EXPIRE,
        )

        # Act
        result = check_contract_status()

        # Assert
        assert result["total_contracts"] == 2
        assert result["updated_count"] == 2
        assert result["about_to_expire_count"] == 1
        assert result["expired_count"] == 1

    def test_no_updates_when_no_contracts(self, db):
        """Test task handles empty contract list."""
        # Act
        result = check_contract_status()

        # Assert
        assert result["total_contracts"] == 0
        assert result["updated_count"] == 0

    def test_no_updates_when_status_unchanged(self, db, employee, contract_type):
        """Test no updates when contract status is already correct."""
        # Arrange - Create active contract that should stay active
        contract = create_contract_with_forced_status(
            employee=employee,
            contract_type=contract_type,
            sign_date=date.today() - timedelta(days=30),
            effective_date=date.today() - timedelta(days=10),
            expiration_date=date.today() + timedelta(days=300),
            forced_status=Contract.ContractStatus.ACTIVE,
        )
        assert contract.status == Contract.ContractStatus.ACTIVE  # Verify setup

        # Act
        result = check_contract_status()

        # Assert
        contract.refresh_from_db()
        assert contract.status == Contract.ContractStatus.ACTIVE
        assert result["total_contracts"] == 1
        assert result["updated_count"] == 0
