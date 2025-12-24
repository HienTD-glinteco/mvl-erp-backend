"""Tests for contract expiration behaviors tied to employees."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.constants import EmployeeType
from apps.hrm.models import Block, Branch, Contract, ContractType, Department, Employee


@pytest.fixture
def province(db):
    return Province.objects.create(code="CE", name="Contract Expiration Province")


@pytest.fixture
def admin_unit(db, province):
    return AdministrativeUnit.objects.create(
        code="CE",
        name="Contract Expiration Admin Unit",
        parent_province=province,
        level=AdministrativeUnit.UnitLevel.DISTRICT,
    )


@pytest.fixture
def organization(db, province, admin_unit):
    branch = Branch.objects.create(
        name="Contract Expiration Branch", province=province, administrative_unit=admin_unit
    )
    block = Block.objects.create(name="Contract Expiration Block", branch=branch, block_type=Block.BlockType.BUSINESS)
    department = Department.objects.create(name="Contract Expiration Department", block=block, branch=branch)
    return {"branch": branch, "block": block, "department": department}


@pytest.fixture
def contract_type(db):
    return ContractType.objects.create(
        name="Contract Expiration Type",
        symbol="CET",
        duration_type=ContractType.DurationType.FIXED,
        duration_months=12,
        base_salary=Decimal("5000000"),
        annual_leave_days=12,
    )


@pytest.fixture
def employee(db, organization):
    return Employee.objects.create(
        fullname="Contract Expiration Employee",
        email="contract.expiration@test.com",
        username="contractexpiration",
        phone="0123456788",
        citizen_id="111222333444",
        attendance_code="CE001",
        start_date=date.today(),
        department=organization["department"],
        block=organization["block"],
        branch=organization["branch"],
    )


@pytest.mark.django_db
def test_not_effective_contract_does_not_expire_active_contract(employee, contract_type):
    today = date.today()

    active_contract = Contract.objects.create(
        employee=employee,
        contract_type=contract_type,
        sign_date=today,
        effective_date=today - timedelta(days=10),
        expiration_date=today + timedelta(days=60),
        status=Contract.ContractStatus.ACTIVE,
        base_salary=contract_type.base_salary,
    )

    future_contract = Contract.objects.create(
        employee=employee,
        contract_type=contract_type,
        sign_date=today,
        effective_date=today + timedelta(days=10),
        expiration_date=today + timedelta(days=70),
        status=Contract.ContractStatus.NOT_EFFECTIVE,
        base_salary=contract_type.base_salary,
    )

    active_contract.refresh_from_db()
    future_contract.refresh_from_db()

    assert active_contract.status == Contract.ContractStatus.ACTIVE
    assert future_contract.status == Contract.ContractStatus.NOT_EFFECTIVE


@pytest.mark.django_db
def test_contracts_expire_when_employee_resigns(employee, contract_type):
    today = date.today()

    contract_one = Contract.objects.create(
        employee=employee,
        contract_type=contract_type,
        sign_date=today - timedelta(days=60),
        effective_date=today - timedelta(days=60),
        expiration_date=today + timedelta(days=180),
        status=Contract.ContractStatus.ACTIVE,
        base_salary=contract_type.base_salary,
    )
    contract_two = Contract.objects.create(
        employee=employee,
        contract_type=contract_type,
        sign_date=today - timedelta(days=30),
        effective_date=today - timedelta(days=30),
        expiration_date=today + timedelta(days=90),
        status=Contract.ContractStatus.ABOUT_TO_EXPIRE,
        base_salary=contract_type.base_salary,
    )

    employee.status = Employee.Status.RESIGNED
    employee.resignation_start_date = today
    employee.resignation_reason = Employee.ResignationReason.OTHER
    employee.save(update_fields=["status", "resignation_start_date", "resignation_reason", "updated_at"])

    contract_one.refresh_from_db()
    contract_two.refresh_from_db()

    assert contract_one.status == Contract.ContractStatus.EXPIRED
    assert contract_two.status == Contract.ContractStatus.EXPIRED


@pytest.mark.django_db
def test_contracts_expire_when_employee_type_becomes_unpaid_official(employee, contract_type):
    today = date.today()

    contract = Contract.objects.create(
        employee=employee,
        contract_type=contract_type,
        sign_date=today - timedelta(days=20),
        effective_date=today - timedelta(days=20),
        expiration_date=today + timedelta(days=200),
        status=Contract.ContractStatus.ACTIVE,
        base_salary=contract_type.base_salary,
    )

    employee.employee_type = EmployeeType.UNPAID_OFFICIAL
    employee.save(update_fields=["employee_type", "updated_at"])

    contract.refresh_from_db()

    assert contract.status == Contract.ContractStatus.EXPIRED


@pytest.mark.django_db
def test_contracts_not_expired_when_status_and_type_unchanged(employee, contract_type):
    today = date.today()

    contract = Contract.objects.create(
        employee=employee,
        contract_type=contract_type,
        sign_date=today - timedelta(days=5),
        effective_date=today - timedelta(days=5),
        expiration_date=today + timedelta(days=50),
        status=Contract.ContractStatus.ACTIVE,
        base_salary=contract_type.base_salary,
    )

    # Update an unrelated field; status and employee_type remain non-triggering
    employee.fullname = "Contract Expiration Employee Updated"
    employee.save(update_fields=["fullname", "updated_at"])

    contract.refresh_from_db()

    assert contract.status == Contract.ContractStatus.ACTIVE
