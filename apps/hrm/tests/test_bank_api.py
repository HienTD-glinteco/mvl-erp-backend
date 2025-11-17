import json

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.hrm.models import Bank, BankAccount, Employee

User = get_user_model()


class APITestMixin:
    """Mixin to handle wrapped API responses and data extraction."""

    def get_response_data(self, response):
        """Extract data from wrapped API response."""
        content = json.loads(response.content.decode())
        if "data" in content:
            data = content["data"]
            # Handle paginated responses - extract results list
            if isinstance(data, dict) and "results" in data:
                return data["results"]
            return data
        return content


class BankAPITest(TransactionTestCase, APITestMixin):
    """Test cases for Bank API endpoints (read-only)."""

    def setUp(self):
        # Clear all existing data for clean tests
        Bank.objects.all().delete()
        User.objects.all().delete()

        # Changed to superuser to bypass RoleBasedPermission for API tests
        self.user = User.objects.create_superuser(username="testuser", email="test@example.com", password="testpass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create test banks
        self.bank1 = Bank.objects.create(name="Vietcombank", code="VCB")
        self.bank2 = Bank.objects.create(name="BIDV", code="BIDV")

    def test_list_banks(self):
        """Test listing all banks."""
        url = reverse("hrm:bank-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 2)

    def test_retrieve_bank(self):
        """Test retrieving a single bank."""
        url = reverse("hrm:bank-detail", kwargs={"pk": self.bank1.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(data["code"], "VCB")
        self.assertEqual(data["name"], "Vietcombank")

    def test_filter_banks_by_name(self):
        """Test filtering banks by name."""
        url = reverse("hrm:bank-list")
        response = self.client.get(url, {"name": "Vietcom"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["code"], "VCB")

    def test_filter_banks_by_code(self):
        """Test filtering banks by code."""
        url = reverse("hrm:bank-list")
        response = self.client.get(url, {"code": "BIDV"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "BIDV")

    def test_search_banks(self):
        """Test searching banks."""
        url = reverse("hrm:bank-list")
        response = self.client.get(url, {"search": "VCB"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)

    def test_ordering_banks_by_name(self):
        """Test ordering banks by name."""
        url = reverse("hrm:bank-list")
        response = self.client.get(url, {"ordering": "name"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(data[0]["code"], "BIDV")
        self.assertEqual(data[1]["code"], "VCB")

    def test_create_bank_not_allowed(self):
        """Test that creating a bank via API is not allowed (read-only)."""
        url = reverse("hrm:bank-list")
        data = {"name": "Test Bank", "code": "TEST"}
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_update_bank_not_allowed(self):
        """Test that updating a bank via API is not allowed (read-only)."""
        url = reverse("hrm:bank-detail", kwargs={"pk": self.bank1.pk})
        data = {"name": "Updated Bank"}
        response = self.client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_delete_bank_not_allowed(self):
        """Test that deleting a bank via API is not allowed (read-only)."""
        url = reverse("hrm:bank-detail", kwargs={"pk": self.bank1.pk})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class BankAccountAPITest(TransactionTestCase, APITestMixin):
    """Test cases for BankAccount API endpoints."""

    def setUp(self):
        # Clear all existing data for clean tests
        BankAccount.objects.all().delete()
        Employee.objects.all().delete()
        Bank.objects.all().delete()
        User.objects.all().delete()

        self.user = User.objects.create_superuser(username="testuser", email="test@example.com", password="testpass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create organizational structure
        from apps.core.models import AdministrativeUnit, Province
        from apps.hrm.models import Block, Branch, Department

        self.province = Province.objects.create(code="01", name="Test Province")
        self.admin_unit = AdministrativeUnit.objects.create(
            code="01",
            name="Test Admin Unit",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )

        self.branch = Branch.objects.create(
            code="CN001",
            name="Main Branch",
            province=self.province,
            administrative_unit=self.admin_unit,
        )
        self.block = Block.objects.create(
            code="KH001", name="Main Block", branch=self.branch, block_type=Block.BlockType.BUSINESS
        )
        self.department = Department.objects.create(
            code="PB001", name="Engineering Department", block=self.block, branch=self.branch
        )

        # Create test employee
        self.employee = Employee.objects.create(
            fullname="John Doe",
            username="johndoe",
            email="john.doe@example.com",
            phone="0123456789",
            attendance_code="12345",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.department,
            start_date="2024-01-01",
        )

        # Create test bank
        self.bank = Bank.objects.create(name="Vietcombank", code="VCB")

        self.account_data = {
            "employee_id": self.employee.id,
            "bank_id": self.bank.id,
            "account_number": "1234567890",
            "account_name": "NGUYEN VAN A",
            "is_primary": True,
        }

    def test_create_bank_account(self):
        """Test creating a bank account via API."""
        url = reverse("hrm:bank-account-list")
        response = self.client.post(url, self.account_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(BankAccount.objects.count(), 1)

        account = BankAccount.objects.first()
        self.assertEqual(account.account_number, self.account_data["account_number"])
        self.assertEqual(account.account_name, self.account_data["account_name"])
        self.assertEqual(account.employee, self.employee)
        self.assertEqual(account.bank, self.bank)
        self.assertTrue(account.is_primary)

    def test_create_bank_account_minimal_fields(self):
        """Test creating a bank account with minimal fields."""
        url = reverse("hrm:bank-account-list")
        minimal_data = {
            "employee_id": self.employee.id,
            "bank_id": self.bank.id,
            "account_number": "9876543210",
            "account_name": "TRAN THI B",
            "is_primary": False,
        }
        response = self.client.post(url, minimal_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(BankAccount.objects.count(), 1)

        account = BankAccount.objects.first()
        self.assertFalse(account.is_primary)

    def test_create_bank_account_missing_required_field(self):
        """Test creating a bank account without required fields."""
        url = reverse("hrm:bank-account-list")
        invalid_data = {
            "account_number": "1234567890",
            # Missing employee_id, bank_id, and account_name
        }
        response = self.client.post(url, invalid_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(BankAccount.objects.count(), 0)

    def test_list_bank_accounts(self):
        """Test listing all bank accounts."""
        BankAccount.objects.create(
            employee=self.employee,
            bank=self.bank,
            account_number="1234567890",
            account_name="NGUYEN VAN A",
            is_primary=True,
        )

        url = reverse("hrm:bank-account-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)

    def test_retrieve_bank_account(self):
        """Test retrieving a single bank account."""
        account = BankAccount.objects.create(
            employee=self.employee,
            bank=self.bank,
            account_number="1234567890",
            account_name="NGUYEN VAN A",
            is_primary=True,
        )

        url = reverse("hrm:bank-account-detail", kwargs={"pk": account.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(data["account_number"], "1234567890")
        self.assertEqual(data["employee"]["id"], self.employee.id)
        self.assertEqual(data["bank"]["id"], self.bank.id)

    def test_update_bank_account(self):
        """Test updating a bank account."""
        account = BankAccount.objects.create(
            employee=self.employee,
            bank=self.bank,
            account_number="1234567890",
            account_name="NGUYEN VAN A",
            is_primary=False,
        )

        url = reverse("hrm:bank-account-detail", kwargs={"pk": account.pk})
        update_data = {
            "employee_id": self.employee.id,
            "bank_id": self.bank.id,
            "account_number": "9999999999",
            "account_name": "UPDATED NAME",
            "is_primary": False,
        }
        response = self.client.put(url, update_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        account.refresh_from_db()
        self.assertEqual(account.account_number, "9999999999")
        self.assertEqual(account.account_name, "UPDATED NAME")

    def test_partial_update_bank_account(self):
        """Test partially updating a bank account."""
        account = BankAccount.objects.create(
            employee=self.employee,
            bank=self.bank,
            account_number="1234567890",
            account_name="NGUYEN VAN A",
            is_primary=False,
        )

        url = reverse("hrm:bank-account-detail", kwargs={"pk": account.pk})
        partial_data = {"account_name": "PARTIAL UPDATE"}
        response = self.client.patch(url, partial_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        account.refresh_from_db()
        self.assertEqual(account.account_name, "PARTIAL UPDATE")
        self.assertEqual(account.account_number, "1234567890")

    def test_delete_bank_account(self):
        """Test deleting a bank account."""
        account = BankAccount.objects.create(
            employee=self.employee,
            bank=self.bank,
            account_number="1234567890",
            account_name="NGUYEN VAN A",
            is_primary=False,
        )

        url = reverse("hrm:bank-account-detail", kwargs={"pk": account.pk})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(BankAccount.objects.count(), 0)

    def test_filter_bank_accounts_by_employee(self):
        """Test filtering bank accounts by employee."""
        BankAccount.objects.create(
            employee=self.employee,
            bank=self.bank,
            account_number="1234567890",
            account_name="NGUYEN VAN A",
            is_primary=True,
        )

        url = reverse("hrm:bank-account-list")
        response = self.client.get(url, {"employee": self.employee.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)

    def test_filter_bank_accounts_by_bank(self):
        """Test filtering bank accounts by bank."""
        BankAccount.objects.create(
            employee=self.employee,
            bank=self.bank,
            account_number="1234567890",
            account_name="NGUYEN VAN A",
            is_primary=True,
        )

        url = reverse("hrm:bank-account-list")
        response = self.client.get(url, {"bank": self.bank.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)

    def test_filter_bank_accounts_by_is_primary(self):
        """Test filtering bank accounts by is_primary."""
        BankAccount.objects.create(
            employee=self.employee,
            bank=self.bank,
            account_number="1234567890",
            account_name="NGUYEN VAN A",
            is_primary=True,
        )
        BankAccount.objects.create(
            employee=self.employee,
            bank=self.bank,
            account_number="9876543210",
            account_name="NGUYEN VAN B",
            is_primary=False,
        )

        url = reverse("hrm:bank-account-list")
        response = self.client.get(url, {"is_primary": "true"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)
        self.assertTrue(data[0]["is_primary"])

    def test_only_one_primary_account_per_employee(self):
        """Test that only one primary account is allowed per employee."""
        # Create first primary account
        BankAccount.objects.create(
            employee=self.employee,
            bank=self.bank,
            account_number="1234567890",
            account_name="NGUYEN VAN A",
            is_primary=True,
        )

        # Try to create another primary account
        url = reverse("hrm:bank-account-list")
        duplicate_data = {
            "employee_id": self.employee.id,
            "bank_id": self.bank.id,
            "account_number": "9999999999",
            "account_name": "NGUYEN VAN B",
            "is_primary": True,
        }
        response = self.client.post(url, duplicate_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Should still have only 1 account
        self.assertEqual(BankAccount.objects.filter(employee=self.employee, is_primary=True).count(), 1)

    def test_search_bank_accounts(self):
        """Test searching bank accounts."""
        BankAccount.objects.create(
            employee=self.employee,
            bank=self.bank,
            account_number="1234567890",
            account_name="NGUYEN VAN A",
            is_primary=True,
        )

        url = reverse("hrm:bank-account-list")
        response = self.client.get(url, {"search": "NGUYEN VAN"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.get_response_data(response)
        self.assertEqual(len(data), 1)


class BankAccountModelTest(TransactionTestCase):
    """Test cases for BankAccount model validation."""

    def setUp(self):
        # Clear all existing data for clean tests
        BankAccount.objects.all().delete()
        Employee.objects.all().delete()
        Bank.objects.all().delete()

        # Create organizational structure
        from apps.core.models import AdministrativeUnit, Province
        from apps.hrm.models import Block, Branch, Department

        self.province = Province.objects.create(code="01", name="Test Province")
        self.admin_unit = AdministrativeUnit.objects.create(
            code="01",
            name="Test Admin Unit",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )

        self.branch = Branch.objects.create(
            code="CN001",
            name="Main Branch",
            province=self.province,
            administrative_unit=self.admin_unit,
        )
        self.block = Block.objects.create(
            code="KH001", name="Main Block", branch=self.branch, block_type=Block.BlockType.BUSINESS
        )
        self.department = Department.objects.create(
            code="PB001", name="Engineering Department", block=self.block, branch=self.branch
        )

        # Create test employee
        self.employee = Employee.objects.create(
            fullname="John Doe",
            username="johndoe",
            email="john.doe@example.com",
            phone="0123456789",
            attendance_code="12345",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.department,
            start_date="2024-01-01",
        )

        # Create test bank
        self.bank = Bank.objects.create(name="Vietcombank", code="VCB")

    def test_bank_account_str_representation(self):
        """Test string representation of BankAccount."""
        account = BankAccount.objects.create(
            employee=self.employee,
            bank=self.bank,
            account_number="1234567890",
            account_name="NGUYEN VAN A",
            is_primary=True,
        )
        expected = f"{self.employee.fullname} - {self.bank.name} - 1234567890"
        self.assertEqual(str(account), expected)

    def test_bank_str_representation(self):
        """Test string representation of Bank."""
        bank = Bank.objects.create(name="Test Bank", code="TEST")
        self.assertEqual(str(bank), "TEST - Test Bank")

    def test_primary_account_ordering(self):
        """Test that primary accounts are ordered first."""
        BankAccount.objects.create(
            employee=self.employee,
            bank=self.bank,
            account_number="2222222222",
            account_name="SECONDARY",
            is_primary=False,
        )
        BankAccount.objects.create(
            employee=self.employee,
            bank=self.bank,
            account_number="1111111111",
            account_name="PRIMARY",
            is_primary=True,
        )

        accounts = BankAccount.objects.all()
        self.assertTrue(accounts[0].is_primary)
        self.assertFalse(accounts[1].is_primary)
