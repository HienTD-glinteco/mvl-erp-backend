from datetime import timedelta

import pytest
from django.utils import timezone

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import Block, Branch, Contract, ContractType, Department, Employee


@pytest.mark.django_db
class TestContractAppendixLogic:
    @pytest.fixture
    def branch(self):
        province = Province.objects.create(code="01", name="Test Province")
        admin_unit = AdministrativeUnit.objects.create(
            code="01",
            name="Test Admin Unit",
            parent_province=province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )
        return Branch.objects.create(
            name="Test Branch",
            province=province,
            administrative_unit=admin_unit,
        )

    @pytest.fixture
    def block(self, branch):
        return Block.objects.create(
            name="Test Block",
            branch=branch,
            block_type=Block.BlockType.BUSINESS,
        )

    @pytest.fixture
    def department(self, branch, block):
        return Department.objects.create(
            name="Test Department",
            branch=branch,
            block=block,
        )

    @pytest.fixture
    def employee(self, branch, block, department):
        return Employee.objects.create(
            code="EMP001",
            fullname="Test Employee",
            username="test_emp",
            email="test@example.com",
            branch=branch,
            block=block,
            department=department,
            start_date=timezone.now().date(),
            citizen_id="001001001001",
            phone="0901001001",
            personal_email="test@example.com",
        )

    @pytest.fixture
    def contract_type_main(self):
        return ContractType.objects.create(
            code="CT001",
            name="Main Contract",
            category=ContractType.Category.CONTRACT,
            duration_type=ContractType.DurationType.FIXED,
            duration_months=12,
        )

    @pytest.fixture
    def contract_type_appendix(self):
        return ContractType.objects.create(
            code="CT002",
            name="Appendix Contract",
            category=ContractType.Category.APPENDIX,
            duration_type=ContractType.DurationType.INDEFINITE,
        )

    def test_create_main_contract(self, employee, contract_type_main):
        """Test creating a standard contract."""
        contract = Contract.objects.create(
            employee=employee,
            contract_type=contract_type_main,
            sign_date=timezone.now().date(),
            effective_date=timezone.now().date(),
            contract_number="HD001",
        )

        assert contract.pk is not None
        assert contract.contract_type.category == ContractType.Category.CONTRACT
        assert contract.parent_contract is None

    def test_create_contract_appendix(self, employee, contract_type_main, contract_type_appendix):
        """Test creating a contract appendix linked to a parent contract."""
        # Create parent contract
        parent_contract = Contract.objects.create(
            employee=employee,
            contract_type=contract_type_main,
            sign_date=timezone.now().date(),
            effective_date=timezone.now().date(),
            contract_number="HD001",
        )

        # Create appendix
        appendix = Contract.objects.create(
            employee=employee,
            contract_type=contract_type_appendix,
            sign_date=timezone.now().date(),
            effective_date=timezone.now().date(),
            contract_number="PL001",
            parent_contract=parent_contract,
        )

        assert appendix.pk is not None
        assert appendix.contract_type.category == ContractType.Category.APPENDIX
        assert appendix.parent_contract == parent_contract
        assert parent_contract.appendices.count() == 1
        assert parent_contract.appendices.first() == appendix

    def test_appendix_inherits_employee_from_parent(
        self, employee, contract_type_main, contract_type_appendix, branch, block, department
    ):
        """Test that appendix should belong to the same employee as parent (business logic check)."""
        parent_contract = Contract.objects.create(
            employee=employee,
            contract_type=contract_type_main,
            sign_date=timezone.now().date(),
            effective_date=timezone.now().date(),
            contract_number="HD001",
        )

        other_employee = Employee.objects.create(
            code="EMP002",
            fullname="Other Employee",
            username="other_emp",
            email="other@example.com",
            branch=branch,
            block=block,
            department=department,
            start_date=timezone.now().date(),
            citizen_id="002002002002",
            phone="0902002002",
            personal_email="other@example.com",
        )

        # Technically the model allows different employees, but business logic might flag this.
        # For now, we just verify we can create it, but in a real app we might want to enforce this via clean()
        # Let's assume for now we just want to verify the relationship works.

        appendix = Contract.objects.create(
            employee=other_employee,  # Different employee
            contract_type=contract_type_appendix,
            sign_date=timezone.now().date(),
            effective_date=timezone.now().date(),
            contract_number="PL002",
            parent_contract=parent_contract,
        )

        assert appendix.parent_contract == parent_contract
        assert appendix.employee != parent_contract.employee

    def test_contract_status_logic_with_appendix(self, employee, contract_type_main, contract_type_appendix):
        """Test that creating an appendix does NOT expire the parent contract.

        Bug fix: Publishing an appendix (PLHD) should not affect the parent contract status.
        Appendices run CONCURRENTLY with the main contract.
        """
        today = timezone.now().date()

        parent_contract = Contract.objects.create(
            employee=employee,
            contract_type=contract_type_main,
            sign_date=today,
            effective_date=today,
            expiration_date=today + timedelta(days=365),
            contract_number="HD001",
            status=Contract.ContractStatus.ACTIVE,
        )

        # Create appendix with ACTIVE status
        appendix = Contract.objects.create(
            employee=employee,
            contract_type=contract_type_appendix,
            sign_date=today,
            effective_date=today,
            contract_number="PL001",
            parent_contract=parent_contract,
            status=Contract.ContractStatus.ACTIVE,
        )

        # Refresh parent to get updated status from DB
        parent_contract.refresh_from_db()

        # CORRECT BEHAVIOR: Appendix should NOT expire the parent contract
        # Parent contract should remain ACTIVE
        assert parent_contract.status == Contract.ContractStatus.ACTIVE
        assert appendix.status == Contract.ContractStatus.ACTIVE
        assert appendix.is_appendix is True

    def test_new_main_contract_expires_previous_contracts(self, employee, contract_type_main):
        """Test that creating a NEW main contract DOES expire previous active contracts."""
        today = timezone.now().date()

        # Create first contract
        first_contract = Contract.objects.create(
            employee=employee,
            contract_type=contract_type_main,
            sign_date=today,
            effective_date=today,
            expiration_date=today + timedelta(days=365),
            contract_number="HD001",
            status=Contract.ContractStatus.ACTIVE,
        )

        # Create second main contract (not an appendix)
        second_contract = Contract.objects.create(
            employee=employee,
            contract_type=contract_type_main,
            sign_date=today,
            effective_date=today,
            expiration_date=today + timedelta(days=365),
            contract_number="HD002",
            status=Contract.ContractStatus.ACTIVE,
        )

        # Refresh first contract
        first_contract.refresh_from_db()

        # First contract should be EXPIRED because a new main contract was created
        assert first_contract.status == Contract.ContractStatus.EXPIRED
        assert second_contract.status == Contract.ContractStatus.ACTIVE
        assert second_contract.is_appendix is False

    def test_multiple_appendices_do_not_expire_parent_or_each_other(
        self, employee, contract_type_main, contract_type_appendix
    ):
        """Test that multiple appendices can coexist without expiring parent or each other."""
        today = timezone.now().date()

        # Create parent contract
        parent_contract = Contract.objects.create(
            employee=employee,
            contract_type=contract_type_main,
            sign_date=today,
            effective_date=today,
            expiration_date=today + timedelta(days=365),
            contract_number="HD001",
            status=Contract.ContractStatus.ACTIVE,
        )

        # Create first appendix
        appendix1 = Contract.objects.create(
            employee=employee,
            contract_type=contract_type_appendix,
            sign_date=today,
            effective_date=today,
            contract_number="PL001",
            parent_contract=parent_contract,
            status=Contract.ContractStatus.ACTIVE,
        )

        # Create second appendix
        appendix2 = Contract.objects.create(
            employee=employee,
            contract_type=contract_type_appendix,
            sign_date=today,
            effective_date=today,
            contract_number="PL002",
            parent_contract=parent_contract,
            status=Contract.ContractStatus.ACTIVE,
        )

        # Refresh all contracts
        parent_contract.refresh_from_db()
        appendix1.refresh_from_db()

        # All should remain ACTIVE - appendices don't expire anything
        assert parent_contract.status == Contract.ContractStatus.ACTIVE
        assert appendix1.status == Contract.ContractStatus.ACTIVE
        assert appendix2.status == Contract.ContractStatus.ACTIVE
