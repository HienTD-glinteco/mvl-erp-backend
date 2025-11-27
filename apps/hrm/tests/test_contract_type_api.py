"""Tests for ContractType model and API."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse
from rest_framework import status

from apps.hrm.models import ContractType


@pytest.fixture
def contract_type_data():
    """Return base contract type data for tests."""
    return {
        "name": "Full-time Employment Contract",
        "symbol": "HDLD",
        "duration_type": "indefinite",
        "duration_months": None,
        "base_salary": "15000000",
        "lunch_allowance": "500000",
        "phone_allowance": "200000",
        "other_allowance": None,
        "net_percentage": "100",
        "tax_calculation_method": "progressive",
        "working_time_type": "full_time",
        "annual_leave_days": 12,
        "has_social_insurance": True,
        "working_conditions": "Standard office conditions",
        "rights_and_obligations": "Employee rights and obligations",
        "terms": "Contract terms and conditions",
        "note": "Test note",
    }


@pytest.fixture
def contract_type(db):
    """Create a contract type for testing."""
    return ContractType.objects.create(
        name="Test Contract Type",
        symbol="TCT",
        duration_type=ContractType.DurationType.INDEFINITE,
        base_salary=Decimal("10000000"),
        annual_leave_days=12,
        working_conditions="Test conditions",
        rights_and_obligations="Test rights",
        terms="Test terms",
    )


@pytest.fixture
def fixed_term_contract_type(db):
    """Create a fixed-term contract type for testing."""
    return ContractType.objects.create(
        name="Fixed-term Contract",
        symbol="FTC",
        duration_type=ContractType.DurationType.FIXED,
        duration_months=12,
        base_salary=Decimal("8000000"),
        annual_leave_days=10,
        working_conditions="Fixed-term conditions",
        rights_and_obligations="Fixed-term rights",
        terms="Fixed-term terms",
    )


class TestContractTypeModel:
    """Test cases for ContractType model."""

    def test_create_contract_type_indefinite(self, db):
        """Test creating an indefinite contract type."""
        contract_type = ContractType.objects.create(
            name="Indefinite Contract",
            symbol="IC",
            duration_type=ContractType.DurationType.INDEFINITE,
            base_salary=Decimal("15000000"),
            annual_leave_days=12,
            working_conditions="Standard conditions",
            rights_and_obligations="Rights and obligations",
            terms="Contract terms",
        )

        assert contract_type.name == "Indefinite Contract"
        assert contract_type.symbol == "IC"
        assert contract_type.duration_type == ContractType.DurationType.INDEFINITE
        assert contract_type.duration_months is None
        assert contract_type.base_salary == Decimal("15000000")
        assert contract_type.code is not None
        assert contract_type.code.startswith("LHD")

    def test_create_contract_type_fixed_term(self, db):
        """Test creating a fixed-term contract type."""
        contract_type = ContractType.objects.create(
            name="Fixed Term Contract",
            symbol="FTC",
            duration_type=ContractType.DurationType.FIXED,
            duration_months=24,
            base_salary=Decimal("12000000"),
            annual_leave_days=12,
            working_conditions="Fixed-term conditions",
            rights_and_obligations="Rights and obligations",
            terms="Contract terms",
        )

        assert contract_type.duration_type == ContractType.DurationType.FIXED
        assert contract_type.duration_months == 24

    def test_contract_type_str_representation(self, contract_type):
        """Test string representation of contract type."""
        assert str(contract_type) == f"{contract_type.code} - Test Contract Type"

    def test_contract_type_unique_name(self, contract_type):
        """Test that contract type name is unique."""
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            ContractType.objects.create(
                name="Test Contract Type",  # Duplicate name
                symbol="DUP",
                base_salary=Decimal("10000000"),
                annual_leave_days=12,
                working_conditions="Conditions",
                rights_and_obligations="Rights",
                terms="Terms",
            )

    def test_duration_display_indefinite(self, contract_type):
        """Test duration_display for indefinite contract."""
        assert contract_type.duration_display == "Indefinite term"

    def test_duration_display_fixed(self, fixed_term_contract_type):
        """Test duration_display for fixed-term contract."""
        assert fixed_term_contract_type.duration_display == "12 months"

    def test_auto_code_generation(self, db):
        """Test that code is auto-generated."""
        contract_type = ContractType.objects.create(
            name="Auto Code Test",
            symbol="ACT",
            base_salary=Decimal("10000000"),
            annual_leave_days=12,
            working_conditions="Conditions",
            rights_and_obligations="Rights",
            terms="Terms",
        )

        assert contract_type.code is not None
        assert contract_type.code.startswith("LHD")

    def test_annual_leave_days_max_validation(self, db):
        """Test that annual leave days cannot exceed 12."""
        from django.core.exceptions import ValidationError

        with pytest.raises(ValidationError):
            contract_type = ContractType(
                name="Invalid Leave Days",
                symbol="ILD",
                base_salary=Decimal("10000000"),
                annual_leave_days=15,  # Invalid - exceeds max
                working_conditions="Conditions",
                rights_and_obligations="Rights",
                terms="Terms",
            )
            contract_type.full_clean()


class TestContractTypeAPI:
    """Test cases for ContractType API endpoints."""

    def test_list_contract_types(self, api_client, contract_type, fixed_term_contract_type):
        """Test listing all contract types."""
        url = reverse("hrm:contract-type-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["count"] == 2

    def test_retrieve_contract_type(self, api_client, contract_type):
        """Test retrieving a single contract type."""
        url = reverse("hrm:contract-type-detail", kwargs={"pk": contract_type.pk})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["name"] == "Test Contract Type"
        assert data["symbol"] == "TCT"
        assert data["duration_type"] == "indefinite"
        assert data["code"] == contract_type.code

    def test_create_contract_type_indefinite(self, api_client, contract_type_data):
        """Test creating an indefinite contract type."""
        url = reverse("hrm:contract-type-list")
        response = api_client.post(url, contract_type_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()["data"]
        assert data["name"] == "Full-time Employment Contract"
        assert data["symbol"] == "HDLD"
        assert data["duration_type"] == "indefinite"
        assert data["duration_months"] is None
        assert data["code"].startswith("LHD")

    def test_create_contract_type_fixed_term(self, api_client, contract_type_data):
        """Test creating a fixed-term contract type."""
        contract_type_data["name"] = "Fixed Term Contract"
        contract_type_data["duration_type"] = "fixed"
        contract_type_data["duration_months"] = 12

        url = reverse("hrm:contract-type-list")
        response = api_client.post(url, contract_type_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()["data"]
        assert data["duration_type"] == "fixed"
        assert data["duration_months"] == 12
        assert data["duration_display"] == "12 months"

    def test_create_contract_type_fixed_without_duration_months(self, api_client, contract_type_data):
        """Test that fixed-term contracts require duration_months."""
        contract_type_data["name"] = "Invalid Fixed Term"
        contract_type_data["duration_type"] = "fixed"
        contract_type_data["duration_months"] = None

        url = reverse("hrm:contract-type-list")
        response = api_client.post(url, contract_type_data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error = response.json()["error"]
        assert "duration_months" in str(error)

    def test_create_contract_type_duplicate_name(self, api_client, contract_type, contract_type_data):
        """Test creating a contract type with duplicate name."""
        contract_type_data["name"] = "Test Contract Type"  # Same as fixture

        url = reverse("hrm:contract-type-list")
        response = api_client.post(url, contract_type_data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_update_contract_type(self, api_client, contract_type):
        """Test updating a contract type."""
        url = reverse("hrm:contract-type-detail", kwargs={"pk": contract_type.pk})
        payload = {
            "name": "Updated Contract Type",
            "symbol": "UCT",
            "duration_type": "indefinite",
            "base_salary": "20000000",
            "annual_leave_days": 10,
            "working_conditions": "Updated conditions",
            "rights_and_obligations": "Updated rights",
            "terms": "Updated terms",
        }
        response = api_client.put(url, payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["name"] == "Updated Contract Type"
        assert data["base_salary"] == "20000000"
        # Code should remain unchanged
        assert data["code"] == contract_type.code

    def test_partial_update_contract_type(self, api_client, contract_type):
        """Test partial update of a contract type."""
        url = reverse("hrm:contract-type-detail", kwargs={"pk": contract_type.pk})
        payload = {"base_salary": "25000000"}
        response = api_client.patch(url, payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["base_salary"] == "25000000"

    def test_delete_contract_type(self, api_client, contract_type):
        """Test deleting a contract type."""
        url = reverse("hrm:contract-type-detail", kwargs={"pk": contract_type.pk})
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert ContractType.objects.filter(pk=contract_type.pk).count() == 0

    def test_filter_by_name(self, api_client, contract_type, fixed_term_contract_type):
        """Test filtering contract types by name."""
        url = reverse("hrm:contract-type-list")
        response = api_client.get(url, {"name": "Test"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["count"] == 1
        assert data["results"][0]["name"] == "Test Contract Type"

    def test_filter_by_duration_type(self, api_client, contract_type, fixed_term_contract_type):
        """Test filtering contract types by duration type."""
        url = reverse("hrm:contract-type-list")
        response = api_client.get(url, {"duration_type": "fixed"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["count"] == 1
        assert data["results"][0]["name"] == "Fixed-term Contract"

    def test_filter_by_social_insurance(self, api_client, contract_type):
        """Test filtering contract types by social insurance."""
        url = reverse("hrm:contract-type-list")
        response = api_client.get(url, {"has_social_insurance": "true"})

        assert response.status_code == status.HTTP_200_OK

    def test_search_by_name(self, api_client, contract_type, fixed_term_contract_type):
        """Test searching contract types by name."""
        url = reverse("hrm:contract-type-list")
        response = api_client.get(url, {"search": "Test Contract"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["count"] == 1

    def test_search_by_code(self, api_client, contract_type):
        """Test searching contract types by code."""
        url = reverse("hrm:contract-type-list")
        response = api_client.get(url, {"search": contract_type.code})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["count"] == 1

    def test_ordering_by_name(self, api_client, contract_type, fixed_term_contract_type):
        """Test ordering contract types by name."""
        url = reverse("hrm:contract-type-list")
        response = api_client.get(url, {"ordering": "name"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        # Fixed-term comes before Test alphabetically
        assert data["results"][0]["name"] == "Fixed-term Contract"

    def test_ordering_by_created_at_desc(self, api_client, contract_type, fixed_term_contract_type):
        """Test ordering contract types by created_at descending (default)."""
        url = reverse("hrm:contract-type-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        # Default ordering is -created_at, so fixed_term_contract_type should be first
        assert data["results"][0]["name"] == "Fixed-term Contract"

    @patch("django.core.cache.cache.delete")
    @patch("django.core.cache.cache.get")
    @patch("apps.files.utils.S3FileUploadService")
    def test_create_contract_type_with_template_file(
        self, mock_s3_service, mock_cache_get, mock_cache_delete, api_client, contract_type_data, db
    ):
        """Test creating a contract type with template file using FileConfirmSerializerMixin."""
        import json

        from apps.files.constants import CACHE_KEY_PREFIX

        # Setup file token
        file_token = "test-template-token-001"
        cache_data = {}

        def cache_get_side_effect(key):
            return cache_data.get(key)

        def cache_delete_side_effect(key):
            if key in cache_data:
                del cache_data[key]

        cache_key = f"{CACHE_KEY_PREFIX}{file_token}"
        cache_data[cache_key] = json.dumps(
            {
                "file_name": "template.docx",
                "file_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "purpose": "contract_type_template",
                "file_path": "uploads/tmp/test-template-token-001/template.docx",
            }
        )

        mock_cache_get.side_effect = cache_get_side_effect
        mock_cache_delete.side_effect = cache_delete_side_effect

        # Mock S3 service
        mock_instance = MagicMock()
        mock_s3_service.return_value = mock_instance
        mock_instance.check_file_exists.return_value = True
        mock_instance.generate_permanent_path.return_value = "uploads/contract_type_template/1/template.docx"
        mock_instance.move_file.return_value = True
        mock_instance.get_file_metadata.return_value = {
            "size": 12345,
            "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "etag": "abc123",
        }
        mock_instance.generate_view_url.return_value = "https://example.com/view/template.docx"
        mock_instance.generate_download_url.return_value = "https://example.com/download/template.docx"

        # Add file token to request data
        contract_type_data["files"] = {"template_file": file_token}

        url = reverse("hrm:contract-type-list")
        response = api_client.post(url, contract_type_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()["data"]
        assert data["template_file"] is not None
        assert data["template_file"]["file_name"] == "template.docx"

    def test_export_xlsx(self, api_client, contract_type, fixed_term_contract_type):
        """Test XLSX export endpoint."""
        url = reverse("hrm:contract-type-export")
        response = api_client.get(url, {"delivery": "direct"})

        # Should return 200 or 206 (partial content for direct download)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_206_PARTIAL_CONTENT]

    def test_change_indefinite_to_fixed(self, api_client, contract_type):
        """Test changing from indefinite to fixed-term contract."""
        url = reverse("hrm:contract-type-detail", kwargs={"pk": contract_type.pk})
        payload = {
            "duration_type": "fixed",
            "duration_months": 6,
        }
        response = api_client.patch(url, payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["duration_type"] == "fixed"
        assert data["duration_months"] == 6
        assert data["duration_display"] == "6 months"

    def test_change_fixed_to_indefinite_clears_duration_months(self, api_client, fixed_term_contract_type):
        """Test that changing to indefinite clears duration_months."""
        url = reverse("hrm:contract-type-detail", kwargs={"pk": fixed_term_contract_type.pk})
        payload = {"duration_type": "indefinite"}
        response = api_client.patch(url, payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["duration_type"] == "indefinite"
        assert data["duration_months"] is None
        assert data["duration_display"] == "Indefinite term"
