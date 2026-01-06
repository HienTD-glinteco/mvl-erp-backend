"""Tests for Contract Appendix (using Contract model with category='appendix')."""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import Block, Branch, Contract, ContractType, Department, Employee
from apps.hrm.models.contract_type import APPENDIX_CONTRACT_TYPE_CACHE_KEY
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
        personal_email="john.doe@test.com",
    )


@pytest.fixture
def contract(db, employee, contract_type):
    """Create a contract for testing (parent contract).

    Note: status is set to ACTIVE. For status to remain ACTIVE after save,
    effective_date must be in the past and expiration_date must be None (indefinite)
    or in the future.
    """
    contract = Contract.objects.create(
        employee=employee,
        contract_type=contract_type,
        sign_date=date.today() - timedelta(days=30),
        effective_date=date.today() - timedelta(days=7),  # Past date for ACTIVE status
        status=Contract.ContractStatus.ACTIVE,
        base_salary=contract_type.base_salary,
        lunch_allowance=contract_type.lunch_allowance,
        phone_allowance=contract_type.phone_allowance,
        working_conditions=contract_type.working_conditions,
        rights_and_obligations=contract_type.rights_and_obligations,
        terms=contract_type.terms,
    )
    return contract


@pytest.fixture
def appendix_data(contract, appendix_contract_type):
    """Return base contract appendix data for tests.

    Note: contract_type_id and employee_id are auto-derived from parent_contract
    by the serializer, so they should NOT be included in request data.

    The appendix_contract_type fixture is required to ensure the contract type
    exists in the database for the serializer to use.
    """
    return {
        "parent_contract_id": contract.id,
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

        # Now generate code using the function (function mutates instance)
        generate_contract_code(appendix)
        # Code format: PLHDxxxxx (System ID)
        assert appendix.code.startswith("PLHD")
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

    def test_create_appendix_auto_derives_employee_from_parent(
        self, api_client, appendix_data, contract, appendix_contract_type
    ):
        """Test that employee is automatically derived from parent_contract."""
        url = reverse("hrm:contract-appendix-list")
        response = api_client.post(url, appendix_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()["data"]

        # Verify employee was auto-derived from parent contract
        assert data["employee"]["id"] == contract.employee.id
        assert data["employee"]["fullname"] == contract.employee.fullname

    def test_create_appendix_auto_sets_contract_type(self, api_client, appendix_data, appendix_contract_type):
        """Test that contract_type is automatically set to appendix type."""
        url = reverse("hrm:contract-appendix-list")
        response = api_client.post(url, appendix_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()["data"]

        # Verify contract_type was auto-set to appendix type
        assert data["contract_type"]["id"] == appendix_contract_type.id
        assert data["contract_type"]["name"] == appendix_contract_type.name

    def test_create_appendix_validates_parent_contract_status_draft(
        self, api_client, contract, contract_type, appendix_contract_type
    ):
        """Test that parent_contract must be in ACTIVE or ABOUT_TO_EXPIRE status."""
        # Set parent contract to DRAFT status using update() to bypass model status calculation
        Contract.objects.filter(pk=contract.pk).update(status=Contract.ContractStatus.DRAFT)

        url = reverse("hrm:contract-appendix-list")
        data = {
            "parent_contract_id": contract.id,
            "sign_date": date.today().isoformat(),
            "effective_date": (date.today() + timedelta(days=7)).isoformat(),
            "content": "Test appendix content",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error = response.json()["error"]
        assert "parent_contract" in str(error).lower()
        assert "ACTIVE" in str(error) or "ABOUT_TO_EXPIRE" in str(error)

    def test_create_appendix_validates_parent_contract_status_expired(
        self, api_client, contract, appendix_contract_type
    ):
        """Test that expired parent_contract is not allowed."""
        # Set parent contract to EXPIRED status using update() to bypass model status calculation
        Contract.objects.filter(pk=contract.pk).update(status=Contract.ContractStatus.EXPIRED)

        url = reverse("hrm:contract-appendix-list")
        data = {
            "parent_contract_id": contract.id,
            "sign_date": date.today().isoformat(),
            "effective_date": (date.today() + timedelta(days=7)).isoformat(),
            "content": "Test appendix content",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_appendix_allows_about_to_expire_parent(self, api_client, contract, appendix_contract_type):
        """Test that ABOUT_TO_EXPIRE parent_contract is allowed."""
        # Set parent contract to ABOUT_TO_EXPIRE status using update() to bypass model status calculation
        Contract.objects.filter(pk=contract.pk).update(status=Contract.ContractStatus.ABOUT_TO_EXPIRE)

        url = reverse("hrm:contract-appendix-list")
        data = {
            "parent_contract_id": contract.id,
            "sign_date": date.today().isoformat(),
            "effective_date": (date.today() + timedelta(days=7)).isoformat(),
            "content": "Test appendix content",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED

    def test_create_contract_appendix_validates_dates(self, api_client, appendix_data):
        """Test that sign_date must be before or equal to effective_date."""
        appendix_data["sign_date"] = (date.today() + timedelta(days=10)).isoformat()
        appendix_data["effective_date"] = date.today().isoformat()

        url = reverse("hrm:contract-appendix-list")
        response = api_client.post(url, appendix_data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "sign_date" in str(response.json()["error"])

    def test_create_contract_appendix_validates_effective_date_against_parent(
        self, api_client, appendix_data, contract
    ):
        """Test that appendix effective_date must be >= parent_contract.effective_date."""
        # parent effective_date is today - 7 days (from fixture)
        # Try to create appendix with effective_date = today - 8 days
        appendix_data["effective_date"] = (contract.effective_date - timedelta(days=1)).isoformat()
        # Ensure sign_date is valid relative to effective_date
        appendix_data["sign_date"] = (contract.effective_date - timedelta(days=2)).isoformat()

        url = reverse("hrm:contract-appendix-list")
        response = api_client.post(url, appendix_data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        # Parse response. Based on other tests, it seems "error" key might wrap the standardized errors.
        # Structure likely: {"error": {"type": "validation_error", "errors": [...]}}
        response_data = response.json()

        if "error" in response_data:
            error_data = response_data["error"]
        else:
            error_data = response_data

        assert error_data["type"] == "validation_error"

        # Check if any error is for effective_date with correct message
        errors = error_data["errors"]
        effective_date_errors = [e for e in errors if e["attr"] == "effective_date"]
        assert len(effective_date_errors) > 0
        assert (
            "Appendix effective date must be on or after parent contract effective date"
            in effective_date_errors[0]["detail"]
        )

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

    def test_update_appendix_syncs_employee_when_parent_changes(
        self, api_client, contract_appendix, contract, contract_type, province, admin_unit
    ):
        """Test that changing parent_contract also updates employee."""
        # Create a new employee and contract
        branch = Branch.objects.create(
            name="Another Branch",
            province=province,
            administrative_unit=admin_unit,
        )
        block = Block.objects.create(
            name="Another Block",
            branch=branch,
            block_type=Block.BlockType.BUSINESS,
        )
        department = Department.objects.create(
            name="Another Department",
            block=block,
            branch=branch,
        )
        new_employee = Employee.objects.create(
            fullname="Jane Smith",
            email="jane.smith@test.com",
            username="janesmith",
            phone="0987654321",
            citizen_id="987654321012",
            attendance_code="002",
            start_date=date.today(),
            department=department,
            block=block,
            branch=branch,
            personal_email="jane.smith@test.com",
        )
        new_contract = Contract.objects.create(
            employee=new_employee,
            contract_type=contract_type,
            sign_date=date.today() - timedelta(days=30),
            effective_date=date.today() - timedelta(days=7),  # Past date for ACTIVE status
            status=Contract.ContractStatus.ACTIVE,
            base_salary=contract_type.base_salary,
        )

        # Update appendix to new parent contract
        url = reverse("hrm:contract-appendix-detail", kwargs={"pk": contract_appendix.pk})
        response = api_client.patch(url, {"parent_contract_id": new_contract.id}, format="json")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]

        # Verify employee was synced from new parent contract
        assert data["employee"]["id"] == new_employee.id
        assert data["parent_contract"]["id"] == new_contract.id

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


class TestContractAppendixCache:
    """Test cases for contract appendix type caching functionality."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        """Clear the cache before each test."""
        cache.delete(APPENDIX_CONTRACT_TYPE_CACHE_KEY)
        yield
        cache.delete(APPENDIX_CONTRACT_TYPE_CACHE_KEY)

    def test_create_appendix_caches_contract_type_id(self, api_client, appendix_data, appendix_contract_type):
        """Test that creating an appendix caches the contract type ID."""
        # Ensure cache is empty
        assert cache.get(APPENDIX_CONTRACT_TYPE_CACHE_KEY) is None

        url = reverse("hrm:contract-appendix-list")
        response = api_client.post(url, appendix_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED

        # Verify cache was set
        cached_id = cache.get(APPENDIX_CONTRACT_TYPE_CACHE_KEY)
        assert cached_id == appendix_contract_type.id

    def test_cached_contract_type_used_on_subsequent_creates(
        self, api_client, appendix_data, appendix_contract_type, contract
    ):
        """Test that subsequent creates use cached contract type ID."""
        url = reverse("hrm:contract-appendix-list")

        # First create populates cache
        response1 = api_client.post(url, appendix_data, format="json")
        assert response1.status_code == status.HTTP_201_CREATED

        # Verify cache is set
        assert cache.get(APPENDIX_CONTRACT_TYPE_CACHE_KEY) == appendix_contract_type.id

        # Create second appendix with same parent (change effective_date for uniqueness)
        appendix_data["effective_date"] = (date.today() + timedelta(days=14)).isoformat()

        # Mock database query to verify cache is used
        with patch.object(ContractType.objects, "filter") as mock_filter:
            # Configure mock to still return the expected value if called
            mock_filter.return_value.values.return_value.first.return_value = {"id": appendix_contract_type.id}

            response2 = api_client.post(url, appendix_data, format="json")
            assert response2.status_code == status.HTTP_201_CREATED

            # Database should NOT be queried because cache is used
            mock_filter.assert_not_called()

    def test_create_appendix_without_contract_type_fails(self, api_client, appendix_data, db):
        """Test that creating appendix without any appendix contract type fails."""
        # Delete all appendix contract types
        ContractType.objects.filter(category=ContractType.Category.APPENDIX).delete()

        url = reverse("hrm:contract-appendix-list")
        response = api_client.post(url, appendix_data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "contract_type" in str(response.json()["error"]).lower()
