"""Tests for Contract model and API."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import Block, Branch, Contract, ContractType, Department, Employee


@pytest.fixture
def province(db):
    """Create a province for testing."""
    return Province.objects.create(code="01", name="Test Province")


@pytest.fixture
def admin_unit(db, province):
    """Create an administrative unit for testing."""
    return AdministrativeUnit.objects.create(
        code="01",
        name="Test Admin Unit",
        parent_province=province,
        level=AdministrativeUnit.UnitLevel.DISTRICT,
    )


@pytest.fixture
def contract_type(db):
    """Create a contract type for testing."""
    return ContractType.objects.create(
        name="Test Contract Type",
        symbol="TCT",
        duration_type=ContractType.DurationType.INDEFINITE,
        base_salary=Decimal("15000000"),
        lunch_allowance=Decimal("500000"),
        phone_allowance=Decimal("200000"),
        annual_leave_days=12,
        working_conditions="Standard office conditions",
        rights_and_obligations="Employee rights and obligations",
        terms="Contract terms and conditions",
    )


@pytest.fixture
def fixed_term_contract_type(db):
    """Create a fixed-term contract type for testing."""
    return ContractType.objects.create(
        name="Fixed-term Contract Type",
        symbol="FTC",
        duration_type=ContractType.DurationType.FIXED,
        duration_months=12,
        base_salary=Decimal("10000000"),
        lunch_allowance=Decimal("400000"),
        annual_leave_days=10,
        working_conditions="Fixed-term conditions",
        rights_and_obligations="Fixed-term rights",
        terms="Fixed-term terms",
    )


@pytest.fixture
def employee(db, province, admin_unit):
    """Create an employee for testing."""
    branch = Branch.objects.create(
        name="Test Branch",
        province=province,
        administrative_unit=admin_unit,
    )
    block = Block.objects.create(
        name="Test Block",
        branch=branch,
        block_type=Block.BlockType.BUSINESS,
    )
    department = Department.objects.create(
        name="Test Department",
        block=block,
        branch=branch,
    )

    return Employee.objects.create(
        fullname="John Doe",
        email="john.doe@test.com",
        username="johndoe",
        phone="0123456789",
        citizen_id="123456789012",
        attendance_code="001",
        start_date=date.today(),
        department=department,
        block=block,
        branch=branch,
    )


@pytest.fixture
def contract_data(employee, contract_type):
    """Return base contract data for tests."""
    return {
        "employee_id": employee.id,
        "contract_type_id": contract_type.id,
        "sign_date": date.today().isoformat(),
        "effective_date": (date.today() + timedelta(days=7)).isoformat(),
        "status": "draft",
    }


@pytest.fixture
def contract(db, employee, contract_type):
    """Create a contract for testing."""
    from apps.hrm.utils.contract_code import generate_contract_number

    contract = Contract(
        employee=employee,
        contract_type=contract_type,
        sign_date=date.today(),
        effective_date=date.today() + timedelta(days=7),
        status=Contract.ContractStatus.DRAFT,
        base_salary=contract_type.base_salary,
        lunch_allowance=contract_type.lunch_allowance,
        phone_allowance=contract_type.phone_allowance,
        working_conditions=contract_type.working_conditions,
        rights_and_obligations=contract_type.rights_and_obligations,
        terms=contract_type.terms,
    )
    # Generate contract_number manually for testing
    contract.contract_number = generate_contract_number(contract)
    contract.save()
    return contract


@pytest.fixture
def active_contract(db, employee, contract_type):
    """Create an active contract for testing."""
    from apps.hrm.utils.contract_code import generate_contract_number

    contract = Contract(
        employee=employee,
        contract_type=contract_type,
        sign_date=date.today() - timedelta(days=30),
        effective_date=date.today() - timedelta(days=15),
        status=Contract.ContractStatus.ACTIVE,
        base_salary=contract_type.base_salary,
    )
    # Generate contract_number manually for testing
    contract.contract_number = generate_contract_number(contract)
    contract.save()
    return contract


class TestContractModel:
    """Test cases for Contract model."""

    def test_create_contract(self, db, employee, contract_type):
        """Test creating a contract."""
        contract = Contract(
            employee=employee,
            contract_type=contract_type,
            sign_date=date.today(),
            effective_date=date.today() + timedelta(days=7),
            status=Contract.ContractStatus.DRAFT,
            base_salary=contract_type.base_salary,
        )
        from apps.hrm.utils.contract_code import generate_contract_number

        contract.contract_number = generate_contract_number(contract)
        contract.save()

        assert contract.id is not None
        assert contract.code is not None
        assert contract.code.startswith("HD")
        assert contract.contract_number is not None
        assert contract.status == Contract.ContractStatus.DRAFT

    def test_contract_str_representation(self, contract):
        """Test string representation of contract."""
        expected = f"{contract.code} - {contract.employee.fullname}"
        assert str(contract) == expected

    def test_contract_status_choices(self):
        """Test ContractStatus choices."""
        assert Contract.ContractStatus.DRAFT == "draft"
        assert Contract.ContractStatus.NOT_EFFECTIVE == "not_effective"
        assert Contract.ContractStatus.ACTIVE == "active"
        assert Contract.ContractStatus.ABOUT_TO_EXPIRE == "about_to_expire"
        assert Contract.ContractStatus.EXPIRED == "expired"

    def test_contract_auto_code_generation(self, db, employee, contract_type):
        """Test that contract code is auto-generated."""
        contract = Contract(
            employee=employee,
            contract_type=contract_type,
            sign_date=date.today(),
            effective_date=date.today() + timedelta(days=7),
            status=Contract.ContractStatus.DRAFT,
            base_salary=contract_type.base_salary,
        )
        from apps.hrm.utils.contract_code import generate_contract_number

        contract.contract_number = generate_contract_number(contract)
        contract.save()

        # Code should be generated by signal
        assert contract.code is not None
        assert contract.code.startswith("HD")
        # Code format: HD{5 digits}
        assert len(contract.code) == 7

    def test_colored_status_property(self, contract):
        """Test colored_status property."""
        colored = contract.colored_status
        assert "value" in colored
        assert "variant" in colored


class TestContractCodeGeneration:
    """Test cases for contract code generation."""

    def test_generate_contract_code(self, db, employee, contract_type):
        """Test generate_contract_code function."""
        from apps.hrm.utils.contract_code import generate_contract_code

        contract = Contract(
            employee=employee,
            contract_type=contract_type,
            sign_date=date.today(),
            effective_date=date.today() + timedelta(days=7),
            base_salary=contract_type.base_salary,
        )
        from apps.hrm.utils.contract_code import generate_contract_number

        contract.contract_number = generate_contract_number(contract)
        contract.save()

        # Now generate code
        code = generate_contract_code(contract)
        assert code.startswith("HD")
        assert len(code) == 7

    def test_generate_contract_number_format(self, db, employee, contract_type):
        """Test generate_contract_number format."""
        from apps.hrm.utils.contract_code import generate_contract_number

        contract = Contract(
            employee=employee,
            contract_type=contract_type,
            sign_date=date.today(),
            effective_date=date.today() + timedelta(days=7),
            base_salary=contract_type.base_salary,
        )

        number = generate_contract_number(contract)

        # Format: xx/yyyy/symbol - MVL
        current_year = date.today().year
        assert f"/{current_year}/" in number
        assert "- MVL" in number
        assert contract_type.symbol in number


class TestContractAPI:
    """Test cases for Contract API endpoints."""

    def test_list_contracts(self, api_client, contract):
        """Test listing all contracts."""
        url = reverse("hrm:contract-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["count"] >= 1

    def test_retrieve_contract(self, api_client, contract):
        """Test retrieving a single contract."""
        url = reverse("hrm:contract-detail", kwargs={"pk": contract.pk})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["code"] == contract.code
        assert data["contract_number"] == contract.contract_number

    def test_create_contract(self, api_client, contract_data):
        """Test creating a contract."""
        url = reverse("hrm:contract-list")
        response = api_client.post(url, contract_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()["data"]
        assert data["code"] is not None
        assert data["code"].startswith("HD")
        assert data["contract_number"] is not None
        assert "- MVL" in data["contract_number"]
        assert data["status"] == "draft"

    def test_create_contract_copies_snapshot_data(self, api_client, contract_data, contract_type):
        """Test that creating a contract copies snapshot data from contract type."""
        url = reverse("hrm:contract-list")
        response = api_client.post(url, contract_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()["data"]
        assert Decimal(data["base_salary"]) == contract_type.base_salary
        assert Decimal(data["lunch_allowance"]) == contract_type.lunch_allowance
        assert Decimal(data["phone_allowance"]) == contract_type.phone_allowance

    def test_create_contract_validates_dates(self, api_client, contract_data):
        """Test that sign_date must be before or equal to effective_date."""
        contract_data["sign_date"] = (date.today() + timedelta(days=10)).isoformat()
        contract_data["effective_date"] = date.today().isoformat()

        url = reverse("hrm:contract-list")
        response = api_client.post(url, contract_data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "sign_date" in str(response.json()["error"])

    def test_update_draft_contract(self, api_client, contract, contract_data):
        """Test updating a draft contract."""
        url = reverse("hrm:contract-detail", kwargs={"pk": contract.pk})
        contract_data["note"] = "Updated note"

        response = api_client.patch(url, {"note": "Updated note"}, format="json")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["note"] == "Updated note"

    def test_cannot_update_active_contract(self, api_client, active_contract, contract_data):
        """Test that active contracts cannot be updated."""
        url = reverse("hrm:contract-detail", kwargs={"pk": active_contract.pk})

        response = api_client.patch(url, {"note": "Updated note"}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "DRAFT" in str(response.json()["error"])

    def test_delete_draft_contract(self, api_client, contract):
        """Test deleting a draft contract."""
        url = reverse("hrm:contract-detail", kwargs={"pk": contract.pk})

        response = api_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert Contract.objects.filter(pk=contract.pk).count() == 0

    def test_cannot_delete_active_contract(self, api_client, active_contract):
        """Test that active contracts cannot be deleted."""
        url = reverse("hrm:contract-detail", kwargs={"pk": active_contract.pk})

        response = api_client.delete(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "DRAFT" in str(response.json()["error"])

    def test_filter_by_status(self, api_client, contract, active_contract):
        """Test filtering contracts by status."""
        url = reverse("hrm:contract-list")
        response = api_client.get(url, {"status": "draft"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert all(r["status"] == "draft" for r in data["results"])

    def test_filter_by_employee(self, api_client, contract, employee):
        """Test filtering contracts by employee."""
        url = reverse("hrm:contract-list")
        response = api_client.get(url, {"employee": employee.id})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["count"] >= 1

    def test_search_by_employee_name(self, api_client, contract, employee):
        """Test searching contracts by employee name."""
        url = reverse("hrm:contract-list")
        response = api_client.get(url, {"search": employee.fullname})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["count"] >= 1

    def test_search_by_contract_code(self, api_client, contract):
        """Test searching contracts by code."""
        url = reverse("hrm:contract-list")
        response = api_client.get(url, {"search": contract.code})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["count"] >= 1

    def test_ordering_by_created_at(self, api_client, contract):
        """Test ordering contracts by created_at."""
        url = reverse("hrm:contract-list")
        response = api_client.get(url, {"ordering": "-created_at"})

        assert response.status_code == status.HTTP_200_OK


class TestContractStatusCalculation:
    """Test cases for contract status calculation."""

    def test_status_not_effective(self, db, employee, contract_type):
        """Test contract status is NOT_EFFECTIVE when effective_date is in future."""
        from apps.hrm.api.serializers.contract import ContractCUDSerializer

        serializer = ContractCUDSerializer()
        effective_date = date.today() + timedelta(days=30)
        expiration_date = date.today() + timedelta(days=365)

        status_result = serializer._calculate_status(effective_date, expiration_date)
        assert status_result == Contract.ContractStatus.NOT_EFFECTIVE

    def test_status_active(self, db, employee, contract_type):
        """Test contract status is ACTIVE for ongoing contract."""
        from apps.hrm.api.serializers.contract import ContractCUDSerializer

        serializer = ContractCUDSerializer()
        effective_date = date.today() - timedelta(days=30)
        expiration_date = date.today() + timedelta(days=365)

        status_result = serializer._calculate_status(effective_date, expiration_date)
        assert status_result == Contract.ContractStatus.ACTIVE

    def test_status_about_to_expire(self, db, employee, contract_type):
        """Test contract status is ABOUT_TO_EXPIRE when expiring soon."""
        from apps.hrm.api.serializers.contract import ContractCUDSerializer

        serializer = ContractCUDSerializer()
        effective_date = date.today() - timedelta(days=30)
        expiration_date = date.today() + timedelta(days=15)

        status_result = serializer._calculate_status(effective_date, expiration_date)
        assert status_result == Contract.ContractStatus.ABOUT_TO_EXPIRE

    def test_status_expired(self, db, employee, contract_type):
        """Test contract status is EXPIRED when past expiration."""
        from apps.hrm.api.serializers.contract import ContractCUDSerializer

        serializer = ContractCUDSerializer()
        effective_date = date.today() - timedelta(days=365)
        expiration_date = date.today() - timedelta(days=30)

        status_result = serializer._calculate_status(effective_date, expiration_date)
        assert status_result == Contract.ContractStatus.EXPIRED

    def test_status_active_indefinite(self, db, employee, contract_type):
        """Test indefinite contract status is ACTIVE after effective date."""
        from apps.hrm.api.serializers.contract import ContractCUDSerializer

        serializer = ContractCUDSerializer()
        effective_date = date.today() - timedelta(days=30)
        expiration_date = None

        status_result = serializer._calculate_status(effective_date, expiration_date)
        assert status_result == Contract.ContractStatus.ACTIVE
