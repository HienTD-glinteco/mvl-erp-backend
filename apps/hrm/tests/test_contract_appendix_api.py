"""Tests for Contract Appendix (using Contract model with category='appendix')."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import Block, Branch, Contract, ContractType, Department, Employee
from apps.hrm.utils.contract_code import generate_contract_code


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
    """Create a contract type for testing (category='contract')."""
    return ContractType.objects.create(
        name="Test Contract Type",
        symbol="TCT",
        category=ContractType.Category.CONTRACT,
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
def appendix_contract_type(db):
    """Create a contract type for appendices (category='appendix')."""
    return ContractType.objects.create(
        name="Test Appendix Type",
        symbol="PLHD",
        category=ContractType.Category.APPENDIX,
        duration_type=ContractType.DurationType.INDEFINITE,
        base_salary=Decimal("0"),
        annual_leave_days=0,
        working_conditions="",
        rights_and_obligations="",
        terms="",
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
    """Create a contract for testing (parent contract)."""
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
def appendix_data(contract, appendix_contract_type, employee):
    """Return base contract appendix data for tests."""
    return {
        "parent_contract_id": contract.id,
        "contract_type_id": appendix_contract_type.id,
        "employee_id": employee.id,
        "sign_date": date.today().isoformat(),
        "effective_date": (date.today() + timedelta(days=7)).isoformat(),
        "content": "Test appendix content",
    }


@pytest.fixture
def contract_appendix(db, contract, appendix_contract_type, employee):
    """Create a contract appendix for testing."""
    return Contract.objects.create(
        parent_contract=contract,
        employee=employee,
        contract_type=appendix_contract_type,
        sign_date=date.today(),
        effective_date=date.today() + timedelta(days=7),
        content="Test appendix content",
    )


class TestContractAppendixModel:
    """Test cases for Contract Appendix (using Contract model)."""

    def test_create_contract_appendix(self, db, contract, appendix_contract_type, employee):
        """Test creating a contract appendix."""
        appendix = Contract.objects.create(
            parent_contract=contract,
            employee=employee,
            contract_type=appendix_contract_type,
            sign_date=date.today(),
            effective_date=date.today() + timedelta(days=7),
            content="Test content",
        )

        assert appendix.id is not None
        assert appendix.code is not None
        assert appendix.contract_number is not None
        # Code format: PLHDxxxxx (System ID)
        assert appendix.code.startswith("PLHD")
        # contract_number format: xx/yyyy/PLHD-MVL (Business ID)
        assert "/PLHD-MVL" in appendix.contract_number
        assert f"/{date.today().year}/" in appendix.contract_number
        # parent_contract should be set
        assert appendix.parent_contract == contract
        assert appendix.is_appendix is True

    def test_contract_appendix_str_representation(self, contract_appendix):
        """Test string representation of contract appendix."""
        expected = f"{contract_appendix.code} - {contract_appendix.employee.fullname}"
        assert str(contract_appendix) == expected

    def test_contract_appendix_auto_code_generation(self, db, contract, appendix_contract_type, employee):
        """Test that contract appendix codes are auto-generated."""
        appendix = Contract.objects.create(
            parent_contract=contract,
            employee=employee,
            contract_type=appendix_contract_type,
            sign_date=date.today(),
            effective_date=date.today() + timedelta(days=7),
            content="Test content",
        )

        # Code should be generated by signal (System ID: PLHDxxxxx)
        assert appendix.code is not None
        assert appendix.code.startswith("PLHD")

        # contract_number should be generated by signal (Business ID: xx/yyyy/PLHD-MVL)
        assert appendix.contract_number is not None
        assert "/PLHD-MVL" in appendix.contract_number
        assert f"/{date.today().year}/" in appendix.contract_number

    def test_is_appendix_property(self, contract, contract_appendix):
        """Test is_appendix property."""
        assert contract.is_appendix is False
        assert contract_appendix.is_appendix is True


class TestContractAppendixCodeGeneration:
    """Test cases for contract appendix code generation."""

    def test_generate_appendix_codes(self, db, contract, appendix_contract_type, employee):
        """Test generate_contract_code function for appendices."""
        appendix = Contract.objects.create(
            parent_contract=contract,
            employee=employee,
            contract_type=appendix_contract_type,
            sign_date=date.today(),
            effective_date=date.today() + timedelta(days=7),
            content="Test content",
        )

        # Now generate code using the function
        code = generate_contract_code(appendix)
        # Code format: PLHDxxxxx (System ID)
        assert code.startswith("PLHD")
        # contract_number format: xx/yyyy/PLHD-MVL (Business ID) - set by generate_contract_code
        assert appendix.contract_number is not None
        assert "/PLHD-MVL" in appendix.contract_number
        assert f"/{date.today().year}/" in appendix.contract_number

    def test_multiple_appendices_sequential_codes(self, db, contract, appendix_contract_type, employee):
        """Test that multiple appendices get sequential codes."""
        appendix1 = Contract.objects.create(
            parent_contract=contract,
            employee=employee,
            contract_type=appendix_contract_type,
            sign_date=date.today(),
            effective_date=date.today() + timedelta(days=7),
            content="First appendix",
        )
        appendix2 = Contract.objects.create(
            parent_contract=contract,
            employee=employee,
            contract_type=appendix_contract_type,
            sign_date=date.today(),
            effective_date=date.today() + timedelta(days=14),
            content="Second appendix",
        )

        # Both should have unique codes
        assert appendix1.code != appendix2.code
        assert appendix1.contract_number != appendix2.contract_number


class TestContractAppendixAPI:
    """Test cases for Contract Appendix API endpoints."""

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
        assert data["contract_number"] == contract_appendix.contract_number

    def test_create_contract_appendix(self, api_client, appendix_data):
        """Test creating a contract appendix."""
        url = reverse("hrm:contract-appendix-list")
        response = api_client.post(url, appendix_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()["data"]
        assert data["code"] is not None
        assert data["contract_number"] is not None
        # Code format: PLHDxxxxx (System ID)
        assert data["code"].startswith("PLHD")
        # contract_number format: xx/yyyy/PLHD-MVL (Business ID)
        assert "/PLHD-MVL" in data["contract_number"]

    def test_create_contract_appendix_validates_dates(self, api_client, appendix_data):
        """Test that sign_date must be before or equal to effective_date."""
        appendix_data["sign_date"] = (date.today() + timedelta(days=10)).isoformat()
        appendix_data["effective_date"] = date.today().isoformat()

        url = reverse("hrm:contract-appendix-list")
        response = api_client.post(url, appendix_data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "sign_date" in str(response.json()["error"])

    def test_create_contract_appendix_requires_parent_contract(self, api_client, appendix_data):
        """Test that parent_contract is required."""
        del appendix_data["parent_contract_id"]

        url = reverse("hrm:contract-appendix-list")
        response = api_client.post(url, appendix_data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "parent_contract" in str(response.json()["error"]).lower()

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
        assert Contract.objects.filter(pk=contract_appendix.pk).count() == 0

    def test_filter_by_parent_contract(self, api_client, contract_appendix, contract):
        """Test filtering contract appendices by parent contract."""
        url = reverse("hrm:contract-appendix-list")
        response = api_client.get(url, {"parent_contract": contract.id})

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

    def test_publish_contract_appendix(self, api_client, contract_appendix):
        """Test publishing a contract appendix."""
        url = reverse("hrm:contract-appendix-publish", kwargs={"pk": contract_appendix.pk})
        response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["status"] != "draft"

        # Verify status in DB
        contract_appendix.refresh_from_db()
        assert contract_appendix.status != Contract.ContractStatus.DRAFT

    def test_cannot_publish_non_draft_appendix(self, api_client, contract_appendix):
        """Test that non-draft appendices cannot be published."""
        # First publish it
        contract_appendix.status = Contract.ContractStatus.ACTIVE
        contract_appendix.save()

        url = reverse("hrm:contract-appendix-publish", kwargs={"pk": contract_appendix.pk})
        response = api_client.post(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "DRAFT" in str(response.json()["error"])
