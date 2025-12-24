import json
from datetime import date
from pathlib import Path

import pytest
from django.urls import reverse
from rest_framework import status

from apps.payroll.models import RecoveryVoucher


@pytest.mark.django_db
class RecoveryVoucherAPITest:
    """Test cases for RecoveryVoucher API endpoints"""

    @pytest.fixture(autouse=True)
    def setup_fixtures(self, employee):
        self.employee = employee

    def setUp(self):
        """Set up test data"""

        # Valid data for creating voucher
        self.valid_data = {
            "name": "September back pay",
            "voucher_type": "BACK_PAY",
            "employee_id": str(self.employee.id),
            "amount": 1500000,
            "month": "09/2025",
            "note": "Adjustment for commission",
        }

    def test_list_vouchers_empty(self, api_client):
        """Test listing vouchers when none exist"""
        url = reverse("payroll:recovery-vouchers-list")
        response = api_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = json.loads(response.content)

        self.assertTrue(response_data["success"])
        self.assertIsNone(response_data["error"])
        self.assertEqual(response_data["data"]["count"], 0)
        self.assertEqual(response_data["data"]["results"], [])

    def test_list_vouchers_success(self, api_client):
        """Test listing vouchers successfully"""
        # Create test vouchers
        voucher1 = RecoveryVoucher.objects.create(
            code="TEMP_TEST1",
            name="Test Voucher 1",
            voucher_type=RecoveryVoucher.VoucherType.BACK_PAY,
            employee=self.employee,
            amount=1500000,
            month=date(2025, 9, 1),
        )
        voucher2 = RecoveryVoucher.objects.create(
            code="TEMP_TEST2",
            name="Test Voucher 2",
            voucher_type=RecoveryVoucher.VoucherType.RECOVERY,
            employee=self.employee,
            amount=500000,
            month=date(2025, 10, 1),
        )

        url = reverse("payroll:recovery-vouchers-list")
        response = api_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = json.loads(response.content)

        self.assertTrue(response_data["success"])
        self.assertIsNone(response_data["error"])
        self.assertEqual(response_data["data"]["count"], 2)
        self.assertEqual(len(response_data["data"]["results"]), 2)

    def test_list_vouchers_with_search(self, api_client):
        """Test listing vouchers with search"""
        voucher = RecoveryVoucher.objects.create(
            code="TEMP_TEST1",
            name="September back pay",
            voucher_type=RecoveryVoucher.VoucherType.BACK_PAY,
            employee=self.employee,
            amount=1500000,
            month=date(2025, 9, 1),
        )

        url = reverse("payroll:recovery-vouchers-list")
        response = api_client.get(url, {"search": "September"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = json.loads(response.content)

        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["data"]["count"], 1)

    def test_list_vouchers_with_filters(self, api_client):
        """Test listing vouchers with filters"""
        voucher1 = RecoveryVoucher.objects.create(
            code="TEMP_TEST1",
            name="Test Voucher 1",
            voucher_type=RecoveryVoucher.VoucherType.BACK_PAY,
            employee=self.employee,
            amount=1500000,
            month=date(2025, 9, 1),
        )
        voucher2 = RecoveryVoucher.objects.create(
            code="TEMP_TEST2",
            name="Test Voucher 2",
            voucher_type=RecoveryVoucher.VoucherType.RECOVERY,
            employee=self.employee,
            amount=500000,
            month=date(2025, 10, 1),
        )

        url = reverse("payroll:recovery-vouchers-list")
        response = api_client.get(url, {"voucher_type": "BACK_PAY"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = json.loads(response.content)

        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["data"]["count"], 1)

    def test_retrieve_voucher_success(self, api_client):
        """Test retrieving a single voucher"""
        voucher = RecoveryVoucher.objects.create(
            code="TEMP_TEST1",
            name="Test Voucher",
            voucher_type=RecoveryVoucher.VoucherType.BACK_PAY,
            employee=self.employee,
            amount=1500000,
            month=date(2025, 9, 1),
            note="Test note",
        )

        url = reverse("payroll:recovery-vouchers-detail", kwargs={"pk": voucher.pk})
        response = api_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = json.loads(response.content)

        self.assertTrue(response_data["success"])
        self.assertIsNone(response_data["error"])
        data = response_data["data"]
        self.assertEqual(data["id"], str(voucher.id))
        self.assertEqual(data["name"], "Test Voucher")
        self.assertEqual(data["voucher_type"], "BACK_PAY")
        self.assertEqual(data["amount"], 1500000)
        self.assertEqual(data["employee_code"], self.employee.code)
        self.assertEqual(data["employee_name"], "John Doe")

    def test_retrieve_voucher_not_found(self, api_client):
        """Test retrieving non-existent voucher"""
        url = reverse("payroll:recovery-vouchers-detail", kwargs={"pk": 99999})
        response = api_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        response_data = json.loads(response.content)

        self.assertFalse(response_data["success"])
        self.assertIsNone(response_data["data"])
        self.assertIsNotNone(response_data["error"])

    def test_create_voucher_success(self, api_client):
        """Test creating a voucher successfully"""
        url = reverse("payroll:recovery-vouchers-list")
        response = api_client.post(url, data=self.valid_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = json.loads(response.content)

        self.assertTrue(response_data["success"])
        self.assertIsNone(response_data["error"])
        data = response_data["data"]
        self.assertIsNotNone(data["id"])
        self.assertEqual(data["name"], "September back pay")
        self.assertEqual(data["voucher_type"], "BACK_PAY")
        self.assertEqual(data["amount"], 1500000)
        self.assertEqual(data["status"], "NOT_CALCULATED")
        self.assertIn("RV-", data["code"])

        self.assertEqual(data["employee"]["id"], str(self.employee.id))
        self.assertEqual(data["employee"]["code"], "E0001")
        self.assertEqual(data["employee"]["fullname"], "John Doe")
        self.assertEqual(data["block"]["code"], self.employee.block.code)
        self.assertEqual(data["branch"]["code"], self.employee.branch.code)
        self.assertEqual(data["department"]["code"], self.employee.department.code)
        self.assertIsNone(data["position"])

        # Verify in database
        voucher = RecoveryVoucher.objects.get(id=data["id"])
        self.assertEqual(voucher.name, "September back pay")
        self.assertEqual(voucher.employee, self.employee)
        self.assertEqual(voucher.created_by, self.user)

    def test_create_voucher_missing_required_field(self, api_client):
        """Test creating voucher with missing required field"""
        data = self.valid_data.copy()
        del data["name"]

        url = reverse("payroll:recovery-vouchers-list")
        response = api_client.post(url, data=data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = json.loads(response.content)

        self.assertFalse(response_data["success"])
        self.assertIsNone(response_data["data"])
        self.assertIn("name", response_data["error"])

    def test_create_voucher_invalid_amount(self, api_client):
        """Test creating voucher with invalid amount"""
        data = self.valid_data.copy()
        data["amount"] = 0

        url = reverse("payroll:recovery-vouchers-list")
        response = api_client.post(url, data=data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = json.loads(response.content)

        self.assertFalse(response_data["success"])
        self.assertIsNone(response_data["data"])
        self.assertIn("amount", response_data["error"])

    def test_create_voucher_with_sample_fixture(self, api_client):
        """Test creating a voucher using the shared sample fixture."""
        fixture_path = Path(__file__).resolve().parent / "fixtures" / "recovery_voucher_api_sample.json"
        sample = json.loads(fixture_path.read_text())
        payload = sample["create_voucher"]["request"].copy()
        payload["employee_id"] = str(self.employee.id)
        payload.pop("expense_type", None)

        url = reverse("payroll:recovery-vouchers-list")
        response = api_client.post(url, data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = json.loads(response.content)

        self.assertTrue(response_data["success"])
        self.assertIsNone(response_data["error"])
        expected = sample["create_voucher"]["expected"]
        for key in ["name", "voucher_type", "amount", "month", "status", "note"]:
            self.assertEqual(response_data["data"][key], expected[key])
        self.assertEqual(response_data["data"]["employee"]["id"], str(self.employee.id))
        self.assertTrue(response_data["data"]["code"].startswith("RV-"))

    def test_create_voucher_invalid_period_format(self, api_client):
        """Test creating voucher with invalid period format"""
        data = self.valid_data.copy()
        data["month"] = "2025-09-01"  # Wrong format, should be MM/YYYY

        url = reverse("payroll:recovery-vouchers-list")
        response = api_client.post(url, data=data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = json.loads(response.content)

        self.assertFalse(response_data["success"])
        self.assertIsNone(response_data["data"])
        self.assertIn("month", response_data["error"])

    def test_update_voucher_success(self, api_client):
        """Test updating a voucher successfully"""
        voucher = RecoveryVoucher.objects.create(
            code="TEMP_TEST1",
            name="Test Voucher",
            voucher_type=RecoveryVoucher.VoucherType.BACK_PAY,
            employee=self.employee,
            amount=1500000,
            month=date(2025, 9, 1),
            status=RecoveryVoucher.RecoveryVoucherStatus.CALCULATED,
        )

        update_data = {
            "name": "Updated Voucher",
            "voucher_type": "BACK_PAY",
            "employee_id": str(self.employee.id),
            "amount": 2000000,
            "month": "09/2025",
            "note": "Updated note",
        }

        url = reverse("payroll:recovery-vouchers-detail", kwargs={"pk": voucher.pk})
        response = api_client.put(url, data=update_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = json.loads(response.content)

        self.assertTrue(response_data["success"])
        self.assertIsNone(response_data["error"])
        data = response_data["data"]
        self.assertEqual(data["name"], "Updated Voucher")
        self.assertEqual(data["amount"], 2000000)
        # Status should be reset to NOT_CALCULATED after update
        self.assertEqual(data["status"], "NOT_CALCULATED")

        # Verify in database
        voucher.refresh_from_db()
        self.assertEqual(voucher.name, "Updated Voucher")
        self.assertEqual(voucher.amount, 2000000)
        self.assertEqual(voucher.status, RecoveryVoucher.RecoveryVoucherStatus.NOT_CALCULATED)

    def test_partial_update_voucher_success(self, api_client):
        """Test partially updating a voucher"""
        voucher = RecoveryVoucher.objects.create(
            code="TEMP_TEST1",
            name="Test Voucher",
            voucher_type=RecoveryVoucher.VoucherType.BACK_PAY,
            employee=self.employee,
            amount=1500000,
            month=date(2025, 9, 1),
        )

        update_data = {"amount": 2500000}

        url = reverse("payroll:recovery-vouchers-detail", kwargs={"pk": voucher.pk})
        response = api_client.patch(url, data=update_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = json.loads(response.content)

        self.assertTrue(response_data["success"])
        data = response_data["data"]
        self.assertEqual(data["amount"], 2500000)
        # Name should remain unchanged
        self.assertEqual(data["name"], "Test Voucher")

    def test_delete_voucher_success(self, api_client):
        """Test deleting a voucher successfully"""
        voucher = RecoveryVoucher.objects.create(
            code="TEMP_TEST1",
            name="Test Voucher",
            voucher_type=RecoveryVoucher.VoucherType.BACK_PAY,
            employee=self.employee,
            amount=1500000,
            month=date(2025, 9, 1),
        )

        url = reverse("payroll:recovery-vouchers-detail", kwargs={"pk": voucher.pk})
        response = api_client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify voucher is deleted
        self.assertFalse(RecoveryVoucher.objects.filter(id=voucher.id).exists())

    def test_delete_voucher_not_found(self, api_client):
        """Test deleting non-existent voucher"""
        url = reverse("payroll:recovery-vouchers-detail", kwargs={"pk": 99999})
        response = api_client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_code_generation_format(self, api_client):
        """Test that code is generated in correct format RV-{YYYYMM}-{seq}"""
        url = reverse("payroll:recovery-vouchers-list")
        response = api_client.post(url, data=self.valid_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = json.loads(response.content)

        code = response_data["data"]["code"]
        # Check format: RV-YYYYMM-XXXX
        self.assertTrue(code.startswith("RV-202509-"))
        self.assertEqual(len(code), 14)  # RV-YYYYMM-XXXX = 14 characters

    def test_employee_fields_cached(self, api_client):
        """Test that employee_code and employee_name are cached"""
        url = reverse("payroll:recovery-vouchers-list")
        response = api_client.post(url, data=self.valid_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = json.loads(response.content)

        data = response_data["data"]
        self.assertEqual(data["employee_code"], self.employee.code)
        self.assertEqual(data["employee_name"], self.employee.fullname)
