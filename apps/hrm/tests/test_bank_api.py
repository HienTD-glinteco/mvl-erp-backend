import pytest
from django.urls import reverse
from rest_framework import status

from apps.hrm.models import Bank, BankAccount


class APITestMixin:
    """Mixin to handle wrapped API responses and data extraction."""

    def get_response_data(self, response):
        """Extract data from wrapped API response."""
        content = response.json()
        if "data" in content:
            data = content["data"]
            # Handle paginated responses - extract results list
            if isinstance(data, dict) and "results" in data:
                return data["results"]
            return data
        return content


@pytest.mark.django_db
class TestBankAPI(APITestMixin):
    """Test cases for Bank API endpoints (read-only)."""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client, user):
        self.client = api_client
        self.user = user

    @pytest.fixture
    def banks(self, db):
        """Create test banks."""
        bank1 = Bank.objects.create(name="Vietcombank", code="VCB")
        bank2 = Bank.objects.create(name="BIDV", code="BIDV")
        return bank1, bank2

    def test_list_banks(self, banks):
        """Test listing all banks."""
        url = reverse("hrm:bank-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 2

    def test_retrieve_bank(self, banks):
        """Test retrieving a single bank."""
        bank1, _ = banks
        url = reverse("hrm:bank-detail", kwargs={"pk": bank1.pk})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert data["code"] == "VCB"
        assert data["name"] == "Vietcombank"

    def test_filter_banks_by_name(self, banks):
        """Test filtering banks by name."""
        url = reverse("hrm:bank-list")
        response = self.client.get(url, {"name": "Vietcom"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 1
        assert data[0]["code"] == "VCB"

    def test_filter_banks_by_code(self, banks):
        """Test filtering banks by code."""
        url = reverse("hrm:bank-list")
        response = self.client.get(url, {"code": "BIDV"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 1
        assert data[0]["name"] == "BIDV"

    def test_search_banks(self, banks):
        """Test searching banks."""
        url = reverse("hrm:bank-list")
        response = self.client.get(url, {"search": "VCB"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 1

    def test_search_banks_by_name(self, banks):
        """Test searching banks by partial name."""
        url = reverse("hrm:bank-list")
        response = self.client.get(url, {"search": "Vietcom"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 1
        assert data[0]["code"] == "VCB"

    def test_search_banks_phrase(self, db):
        """Test phrase search filter treats multi-word queries as single phrase."""
        # Create a bank with a multi-word name
        Bank.objects.create(name="Vietnam Bank for Agriculture", code="VBARD")

        url = reverse("hrm:bank-list")
        # PhraseSearchFilter should search for the entire phrase
        response = self.client.get(url, {"search": "Bank for"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        # Should find the bank with "Bank for" in its name
        assert len(data) == 1
        assert data[0]["code"] == "VBARD"

    def test_ordering_banks_by_name(self, banks):
        """Test ordering banks by name."""
        url = reverse("hrm:bank-list")
        response = self.client.get(url, {"ordering": "name"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert data[0]["code"] == "BIDV"
        assert data[1]["code"] == "VCB"

    def test_ordering_banks_by_code_descending(self, banks):
        """Test ordering banks by code in descending order."""
        url = reverse("hrm:bank-list")
        response = self.client.get(url, {"ordering": "-code"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert data[0]["code"] == "VCB"
        assert data[1]["code"] == "BIDV"

    def test_create_bank_not_allowed(self):
        """Test that creating a bank via API is not allowed (read-only)."""
        url = reverse("hrm:bank-list")
        data = {"name": "Test Bank", "code": "TEST"}
        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_update_bank_not_allowed(self, banks):
        """Test that updating a bank via API is not allowed (read-only)."""
        bank1, _ = banks
        url = reverse("hrm:bank-detail", kwargs={"pk": bank1.pk})
        data = {"name": "Updated Bank"}
        response = self.client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_delete_bank_not_allowed(self, banks):
        """Test that deleting a bank via API is not allowed (read-only)."""
        bank1, _ = banks
        url = reverse("hrm:bank-detail", kwargs={"pk": bank1.pk})
        response = self.client.delete(url)

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.django_db
class TestBankAccountAPI(APITestMixin):
    """Test cases for BankAccount API endpoints."""

    @pytest.fixture(autouse=True)
    def setup_client(self, api_client, user):
        self.client = api_client
        self.user = user

    def test_create_bank_account(self, employee, bank):
        """Test creating a bank account via API."""
        url = reverse("hrm:bank-account-list")
        data = {
            "employee_id": employee.id,
            "bank_id": bank.id,
            "account_number": "1234567890",
            "account_name": "NGUYEN VAN A",
            "is_primary": True,
        }
        response = self.client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert BankAccount.objects.count() == 1

        account = BankAccount.objects.first()
        assert account.account_number == data["account_number"]
        assert account.account_name == data["account_name"]
        assert account.employee == employee
        assert account.bank == bank
        assert account.is_primary is True

    def test_create_bank_account_minimal_fields(self, employee, bank):
        """Test creating a bank account with minimal fields."""
        url = reverse("hrm:bank-account-list")
        minimal_data = {
            "employee_id": employee.id,
            "bank_id": bank.id,
            "account_number": "9876543210",
            "account_name": "TRAN THI B",
            "is_primary": False,
        }
        response = self.client.post(url, minimal_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert BankAccount.objects.count() == 1

        account = BankAccount.objects.first()
        assert account.is_primary is False

    def test_create_bank_account_missing_required_field(self):
        """Test creating a bank account without required fields."""
        url = reverse("hrm:bank-account-list")
        invalid_data = {
            "account_number": "1234567890",
            # Missing employee_id, bank_id, and account_name
        }
        response = self.client.post(url, invalid_data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert BankAccount.objects.count() == 0

    def test_list_bank_accounts(self, bank_account):
        """Test listing all bank accounts."""
        url = reverse("hrm:bank-account-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 1

    def test_retrieve_bank_account(self, bank_account, employee, bank):
        """Test retrieving a single bank account."""
        url = reverse("hrm:bank-account-detail", kwargs={"pk": bank_account.pk})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert data["account_number"] == bank_account.account_number
        assert data["employee"]["id"] == employee.id
        assert data["bank"]["id"] == bank.id

    def test_update_bank_account(self, bank_account, employee, bank):
        """Test updating a bank account."""
        url = reverse("hrm:bank-account-detail", kwargs={"pk": bank_account.pk})
        update_data = {
            "employee_id": employee.id,
            "bank_id": bank.id,
            "account_number": "9999999999",
            "account_name": "UPDATED NAME",
            "is_primary": False,
        }
        response = self.client.put(url, update_data, format="json")

        assert response.status_code == status.HTTP_200_OK
        bank_account.refresh_from_db()
        assert bank_account.account_number == "9999999999"
        assert bank_account.account_name == "UPDATED NAME"

    def test_partial_update_bank_account(self, bank_account):
        """Test partially updating a bank account."""
        url = reverse("hrm:bank-account-detail", kwargs={"pk": bank_account.pk})
        partial_data = {"account_name": "PARTIAL UPDATE"}
        response = self.client.patch(url, partial_data, format="json")

        assert response.status_code == status.HTTP_200_OK
        bank_account.refresh_from_db()
        assert bank_account.account_name == "PARTIAL UPDATE"
        assert bank_account.account_number == "123456789"

    def test_delete_bank_account(self, bank_account):
        """Test deleting a bank account."""
        url = reverse("hrm:bank-account-detail", kwargs={"pk": bank_account.pk})
        response = self.client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert BankAccount.objects.count() == 0

    def test_filter_bank_accounts_by_employee(self, bank_account, employee):
        """Test filtering bank accounts by employee."""
        url = reverse("hrm:bank-account-list")
        response = self.client.get(url, {"employee": employee.id})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 1

    def test_filter_bank_accounts_by_bank(self, bank_account, bank):
        """Test filtering bank accounts by bank."""
        url = reverse("hrm:bank-account-list")
        response = self.client.get(url, {"bank": bank.id})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 1

    def test_filter_bank_accounts_by_is_primary(self, employee, bank):
        """Test filtering bank accounts by is_primary."""
        BankAccount.objects.create(
            employee=employee,
            bank=bank,
            account_number="1234567890",
            account_name="NGUYEN VAN A",
            is_primary=True,
        )
        BankAccount.objects.create(
            employee=employee,
            bank=bank,
            account_number="9876543210",
            account_name="NGUYEN VAN B",
            is_primary=False,
        )

        url = reverse("hrm:bank-account-list")
        response = self.client.get(url, {"is_primary": "true"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 1
        assert data[0]["is_primary"] is True

    def test_only_one_primary_account_per_employee(self, employee, bank):
        """Test that only one primary account is allowed per employee."""
        # Create first primary account
        BankAccount.objects.create(
            employee=employee,
            bank=bank,
            account_number="1234567890",
            account_name="NGUYEN VAN A",
            is_primary=True,
        )

        # Try to create another primary account
        url = reverse("hrm:bank-account-list")
        duplicate_data = {
            "employee_id": employee.id,
            "bank_id": bank.id,
            "account_number": "9999999999",
            "account_name": "NGUYEN VAN B",
            "is_primary": True,
        }
        response = self.client.post(url, duplicate_data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        # Should still have only 1 primary account
        assert BankAccount.objects.filter(employee=employee, is_primary=True).count() == 1

    def test_search_bank_accounts(self, bank_account):
        """Test searching bank accounts."""
        url = reverse("hrm:bank-account-list")
        response = self.client.get(url, {"search": "Test Employee"})

        assert response.status_code == status.HTTP_200_OK
        data = self.get_response_data(response)
        assert len(data) == 1


@pytest.mark.django_db
class TestBankAccountModel:
    """Test cases for BankAccount model validation."""

    def test_bank_account_str_representation(self, employee, bank):
        """Test string representation of BankAccount."""
        account = BankAccount.objects.create(
            employee=employee,
            bank=bank,
            account_number="1234567890",
            account_name="NGUYEN VAN A",
            is_primary=True,
        )
        expected = f"{employee.fullname} - {bank.name} - 1234567890"
        assert str(account) == expected

    def test_bank_str_representation(self):
        """Test string representation of Bank."""
        bank = Bank.objects.create(name="Test Bank", code="TEST")
        assert str(bank) == "TEST - Test Bank"

    def test_primary_account_ordering(self, employee, bank):
        """Test that primary accounts are ordered first."""
        BankAccount.objects.create(
            employee=employee,
            bank=bank,
            account_number="2222222222",
            account_name="SECONDARY",
            is_primary=False,
        )
        BankAccount.objects.create(
            employee=employee,
            bank=bank,
            account_number="1111111111",
            account_name="PRIMARY",
            is_primary=True,
        )

        accounts = BankAccount.objects.all()
        assert accounts[0].is_primary is True
        assert accounts[1].is_primary is False
