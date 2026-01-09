"""Tests for SalesRevenue Excel export functionality."""

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.payroll.api.serializers import SalesRevenueExportSerializer
from apps.payroll.models import SalesRevenue

User = get_user_model()


@pytest.mark.django_db
class SalesRevenueExportSerializerTest(TestCase):
    """Test SalesRevenueExportSerializer for Excel export."""

    @pytest.fixture(autouse=True)
    def setup_fixtures(self, employee):
        self.employee = employee

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        # Create a sales revenue record
        self.sales_revenue = SalesRevenue.objects.create(
            employee=self.employee,
            month=date(2025, 11, 1),
            revenue=Decimal("150000000"),
            transaction_count=12,
            kpi_target=Decimal("100000000"),
            created_by=self.user,
        )

    def test_export_serializer_flattens_nested_objects(self):
        """Test that export serializer returns flat data structure."""
        serializer = SalesRevenueExportSerializer(self.sales_revenue)
        data = serializer.data

        # All fields should be simple values, not dicts
        for key, value in data.items():
            self.assertNotIsInstance(
                value,
                dict,
                f"Field '{key}' should not be a dict, got {type(value).__name__}: {value}",
            )

    def test_export_serializer_includes_employee_info(self):
        """Test that export serializer includes flattened employee info."""
        serializer = SalesRevenueExportSerializer(self.sales_revenue)
        data = serializer.data

        # Check that employee fields are included and are simple values
        self.assertIn("employee_code", data)
        self.assertIn("employee_name", data)
        self.assertEqual(data["employee_code"], self.employee.code)
        self.assertEqual(data["employee_name"], self.employee.fullname)

    def test_export_serializer_includes_org_structure(self):
        """Test that export serializer includes organization structure."""
        serializer = SalesRevenueExportSerializer(self.sales_revenue)
        data = serializer.data

        # Check that org fields are included
        self.assertIn("block_name", data)
        self.assertIn("branch_name", data)
        self.assertIn("department_name", data)
        self.assertIn("position_name", data)

    def test_export_serializer_month_format(self):
        """Test that month is formatted as MM/YYYY."""
        serializer = SalesRevenueExportSerializer(self.sales_revenue)
        data = serializer.data

        self.assertEqual(data["month"], "11/2025")

    def test_export_serializer_status_display(self):
        """Test that status is displayed as human-readable text."""
        serializer = SalesRevenueExportSerializer(self.sales_revenue)
        data = serializer.data

        self.assertIn("status_display", data)
        # Should be display value, not the internal code
        self.assertIsInstance(data["status_display"], str)

    def test_export_serializer_all_values_excel_compatible(self):
        """Test that all serialized values can be written to Excel."""
        from openpyxl import Workbook

        serializer = SalesRevenueExportSerializer(self.sales_revenue)
        data = serializer.data

        wb = Workbook()
        ws = wb.active

        # Try to write each value to an Excel cell
        for col, (key, value) in enumerate(data.items(), start=1):
            try:
                ws.cell(row=1, column=col, value=value)
            except ValueError as e:
                self.fail(f"Field '{key}' with value {value!r} cannot be written to Excel: {e}")


@pytest.mark.django_db
class SalesRevenueExportAPITest(TestCase):
    """Test SalesRevenue export API endpoint."""

    @pytest.fixture(autouse=True)
    def setup_fixtures(self, employee):
        self.employee = employee

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_authenticate(user=self.user)

        # Create sales revenue records
        self.sales_revenue = SalesRevenue.objects.create(
            employee=self.employee,
            month=date(2025, 11, 1),
            revenue=Decimal("150000000"),
            transaction_count=12,
            created_by=self.user,
        )

    def test_export_endpoint_returns_success(self):
        """Test that export endpoint returns successful response."""
        response = self.client.get("/api/payroll/sales-revenues/export/")

        # Should not return 500 error
        self.assertNotEqual(response.status_code, 500)
        # Should return either 200 (direct download) or link
        self.assertIn(response.status_code, [200, 201, 202])
