"""Tests for ContractAppendix model and API."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import Block, Branch, Contract, ContractAppendix, ContractType, Department, Employee
from apps.hrm.utils.appendix_code import generate_appendix_codes


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
def contract(db, employee, contract_type):
    """Create a contract for testing."""
    return Contract.objects.create(
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


@pytest.fixture
def appendix_data(contract):
    """Return base contract appendix data for tests."""
    return {
        "contract_id": contract.id,
        "sign_date": date.today().isoformat(),
        "effective_date": (date.today() + timedelta(days=7)).isoformat(),
        "content": "Test appendix content",
    }


@pytest.fixture
def contract_appendix(db, contract):
    """Create a contract appendix for testing."""
    return ContractAppendix.objects.create(
        contract=contract,
        sign_date=date.today(),
        effective_date=date.today() + timedelta(days=7),
        content="Test appendix content",
    )


class TestContractAppendixModel:
    """Test cases for ContractAppendix model."""

    def test_create_contract_appendix(self, db, contract):
        """Test creating a contract appendix."""
        appendix = ContractAppendix.objects.create(
            contract=contract,
            sign_date=date.today(),
            effective_date=date.today() + timedelta(days=7),
            content="Test content",
        )

        assert appendix.id is not None
        assert appendix.code is not None
        assert appendix.appendix_code is not None
        # Code format: xx/yyyy/PLHD-MVL
        assert "/PLHD-MVL" in appendix.code
        assert f"/{date.today().year}/" in appendix.code
        # appendix_code format: PLHDxxxxx
        assert appendix.appendix_code.startswith("PLHD")
        # appendix_number is a property that returns code
        assert appendix.appendix_number == appendix.code

    def test_contract_appendix_str_representation(self, contract_appendix):
        """Test string representation of contract appendix."""
        expected = f"{contract_appendix.code} - {contract_appendix.contract.employee.fullname}"
        assert str(contract_appendix) == expected

    def test_contract_appendix_auto_code_generation(self, db, contract):
        """Test that contract appendix codes are auto-generated."""
        appendix = ContractAppendix.objects.create(
            contract=contract,
            sign_date=date.today(),
            effective_date=date.today() + timedelta(days=7),
            content="Test content",
        )

        # Code should be generated by signal
        assert appendix.code is not None
        # Code format: xx/yyyy/PLHD-MVL
        assert "/PLHD-MVL" in appendix.code
        assert f"/{date.today().year}/" in appendix.code

        # appendix_code should be generated
        assert appendix.appendix_code is not None
        assert appendix.appendix_code.startswith("PLHD")

    def test_appendix_number_property(self, contract_appendix):
        """Test appendix_number property returns code."""
        assert contract_appendix.appendix_number == contract_appendix.code


class TestContractAppendixCodeGeneration:
    """Test cases for contract appendix code generation."""

    def test_generate_appendix_codes(self, db, contract):
        """Test generate_appendix_codes function."""
        appendix = ContractAppendix.objects.create(
            contract=contract,
            sign_date=date.today(),
            effective_date=date.today() + timedelta(days=7),
            content="Test content",
        )

        # Now generate code using the function
        code = generate_appendix_codes(appendix)
        # Code format: xx/yyyy/PLHD-MVL
        assert "/PLHD-MVL" in code
        assert f"/{date.today().year}/" in code

        # Refresh from db to check appendix_code was set
        appendix.refresh_from_db()
        assert appendix.appendix_code is not None
        assert appendix.appendix_code.startswith("PLHD")

    def test_multiple_appendices_sequential_codes(self, db, contract):
        """Test that multiple appendices get sequential codes."""
        appendix1 = ContractAppendix.objects.create(
            contract=contract,
            sign_date=date.today(),
            effective_date=date.today() + timedelta(days=7),
            content="First appendix",
        )
        appendix2 = ContractAppendix.objects.create(
            contract=contract,
            sign_date=date.today(),
            effective_date=date.today() + timedelta(days=14),
            content="Second appendix",
        )

        # Both should have unique codes
        assert appendix1.code != appendix2.code
        assert appendix1.appendix_code != appendix2.appendix_code


class TestContractAppendixAPI:
    """Test cases for ContractAppendix API endpoints."""

    def test_list_contract_appendices(self, api_client, contract_appendix):
        """Test listing all contract appendices."""
        url = reverse("hrm:contract-appendix-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["count"] >= 1

    def test_retrieve_contract_appendix(self, api_client, contract_appendix):
        """Test retrieving a single contract appendix."""
        url = reverse("hrm:contract-appendix-detail", kwargs={"pk": contract_appendix.pk})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["code"] == contract_appendix.code
        assert data["appendix_code"] == contract_appendix.appendix_code
        # appendix_number is a property that returns code
        assert data["appendix_number"] == contract_appendix.code

    def test_create_contract_appendix(self, api_client, appendix_data):
        """Test creating a contract appendix."""
        url = reverse("hrm:contract-appendix-list")
        response = api_client.post(url, appendix_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()["data"]
        assert data["code"] is not None
        assert data["appendix_code"] is not None
        # Code format: xx/yyyy/PLHD-MVL
        assert "/PLHD-MVL" in data["code"]
        # appendix_number is same as code
        assert data["appendix_number"] == data["code"]

    def test_create_contract_appendix_validates_dates(self, api_client, appendix_data):
        """Test that sign_date must be before or equal to effective_date."""
        appendix_data["sign_date"] = (date.today() + timedelta(days=10)).isoformat()
        appendix_data["effective_date"] = date.today().isoformat()

        url = reverse("hrm:contract-appendix-list")
        response = api_client.post(url, appendix_data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "sign_date" in str(response.json()["error"])

    def test_update_contract_appendix(self, api_client, contract_appendix):
        """Test updating a contract appendix."""
        url = reverse("hrm:contract-appendix-detail", kwargs={"pk": contract_appendix.pk})

        response = api_client.patch(url, {"note": "Updated note"}, format="json")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["note"] == "Updated note"

    def test_delete_contract_appendix(self, api_client, contract_appendix):
        """Test deleting a contract appendix."""
        url = reverse("hrm:contract-appendix-detail", kwargs={"pk": contract_appendix.pk})

        response = api_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert ContractAppendix.objects.filter(pk=contract_appendix.pk).count() == 0

    def test_filter_by_contract(self, api_client, contract_appendix, contract):
        """Test filtering contract appendices by contract."""
        url = reverse("hrm:contract-appendix-list")
        response = api_client.get(url, {"contract": contract.id})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["count"] >= 1

    def test_search_by_code(self, api_client, contract_appendix):
        """Test searching contract appendices by code."""
        url = reverse("hrm:contract-appendix-list")
        response = api_client.get(url, {"search": contract_appendix.code})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["count"] >= 1

    def test_ordering_by_created_at(self, api_client, contract_appendix):
        """Test ordering contract appendices by created_at."""
        url = reverse("hrm:contract-appendix-list")
        response = api_client.get(url, {"ordering": "-created_at"})

        assert response.status_code == status.HTTP_200_OK
