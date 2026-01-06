"""Tests for sales revenue import handler."""

from datetime import date

import pytest

from apps.payroll.import_handlers.sales_revenue import process_sales_revenue_row
from apps.payroll.models import SalesRevenue


@pytest.fixture
def sales_employee(employee):
    """Use the existing employee fixture as sales employee."""
    return employee


@pytest.fixture
def headers():
    """Excel headers for sales revenue import."""
    return ["Mã nhân viên", "Họ tên", "Chỉ tiêu", "Doanh Số", "Số giao dịch", "Thời gian"]


@pytest.mark.django_db
class TestSalesRevenueImportHandler:
    """Test sales revenue import handler."""

    def test_process_row_success_create(self, sales_employee, headers):
        """Test processing a row successfully creates new record."""
        # Arrange
        row = [sales_employee.code, sales_employee.username, 100000000, 150000000, 12, "11/2025"]
        options = {"headers": headers, "handler_options": {"target_month": "11/2025"}}

        # Act
        result = process_sales_revenue_row(3, row, 1, options)

        # Assert
        assert result["ok"] is True
        assert "result" in result
        assert result["result"]["action"] == "created"
        assert result["result"]["revenue"] == 150000000
        assert result["result"]["transaction_count"] == 12
        assert SalesRevenue.objects.filter(employee=sales_employee, month=date(2025, 11, 1)).exists()

    def test_process_row_success_update(self, sales_employee, headers):
        """Test processing a row successfully updates existing record."""
        # Arrange
        existing = SalesRevenue.objects.create(
            employee=sales_employee,
            kpi_target=100000000,
            revenue=100000000,
            transaction_count=10,
            month=date(2025, 11, 1),
        )
        row = [sales_employee.code, sales_employee.username, 150000000, 200000000, 20, "11/2025"]
        options = {"headers": headers, "handler_options": {"target_month": "11/2025"}}

        # Act
        result = process_sales_revenue_row(3, row, 1, options)

        # Assert
        assert result["ok"] is True
        assert result["result"]["action"] == "updated"
        assert result["result"]["revenue"] == 200000000
        existing.refresh_from_db()
        assert existing.revenue == 200000000
        assert existing.transaction_count == 20

    def test_process_row_with_month_matching_target(self, sales_employee, headers):
        """Test processing row with month matching target month from options."""
        # Arrange
        row = [sales_employee.code, sales_employee.username, 100000000, 150000000, 12, "12/2025"]
        options = {"headers": headers, "handler_options": {"target_month": "12/2025"}}

        # Act
        result = process_sales_revenue_row(3, row, 1, options)

        # Assert
        assert result["ok"] is True
        assert SalesRevenue.objects.filter(employee=sales_employee, month=date(2025, 12, 1)).exists()

    def test_process_row_missing_employee_code(self, headers):
        """Test processing row with missing employee code."""
        # Arrange
        row = ["", "Test", 100000000, 150000000, 12, "11/2025"]
        options = {"headers": headers, "handler_options": {"target_month": "11/2025"}}

        # Act
        result = process_sales_revenue_row(3, row, 1, options)

        # Assert
        assert result["ok"] is False
        assert "Employee code is required" in result["error"]

    def test_process_row_employee_not_found(self, headers):
        """Test processing row with non-existent employee code."""
        # Arrange
        row = ["INVALID", "Test", 100000000, 150000000, 12, "11/2025"]
        options = {"headers": headers, "handler_options": {"target_month": "11/2025"}}

        # Act
        result = process_sales_revenue_row(3, row, 1, options)

        # Assert
        assert result["ok"] is False
        assert "Employee not found" in result["error"]

    def test_process_row_month_mismatch(self, sales_employee, headers):
        """Test processing row with month not matching target month."""
        # Arrange
        row = [sales_employee.code, sales_employee.username, 100000000, 150000000, 12, "12/2025"]
        options = {"headers": headers, "handler_options": {"target_month": "11/2025"}}

        # Act
        result = process_sales_revenue_row(3, row, 1, options)

        # Assert
        assert result["ok"] is False
        assert "does not match target month" in result["error"]

    def test_process_row_invalid_month_format(self, sales_employee, headers):
        """Test processing row with invalid month format."""
        # Arrange
        row = [sales_employee.code, sales_employee.username, 100000000, 150000000, 12, "2025-11"]
        options = {"headers": headers, "handler_options": {"target_month": "11/2025"}}

        # Act
        result = process_sales_revenue_row(3, row, 1, options)

        # Assert
        assert result["ok"] is False
        assert "Invalid month format" in result["error"]

    def test_process_row_invalid_revenue(self, sales_employee, headers):
        """Test processing row with invalid revenue value."""
        # Arrange
        row = [sales_employee.code, sales_employee.username, 100000000, "invalid", 12, "11/2025"]
        options = {"headers": headers, "handler_options": {"target_month": "11/2025"}}

        # Act
        result = process_sales_revenue_row(3, row, 1, options)

        # Assert
        assert result["ok"] is False
        assert "Invalid revenue or transaction count" in result["error"]

    def test_process_row_negative_revenue(self, sales_employee, headers):
        """Test processing row with negative revenue."""
        # Arrange
        row = [sales_employee.code, sales_employee.username, 100000000, -100000, 12, "11/2025"]
        options = {"headers": headers, "handler_options": {"target_month": "11/2025"}}

        # Act
        result = process_sales_revenue_row(3, row, 1, options)

        # Assert
        assert result["ok"] is False
        assert "Revenue must be non-negative" in result["error"]

    def test_process_row_missing_target_month(self, sales_employee, headers):
        """Test processing row without target month in options."""
        # Arrange
        row = [sales_employee.code, sales_employee.username, 100000000, 150000000, 12, "11/2025"]
        options = {"headers": headers, "handler_options": {}}

        # Act
        result = process_sales_revenue_row(3, row, 1, options)

        # Assert
        assert result["ok"] is False
        assert "Target month not provided" in result["error"]

    def test_process_row_missing_headers(self, sales_employee):
        """Test processing row without headers in options."""
        # Arrange
        row = [sales_employee.code, sales_employee.username, 100000000, 150000000, 12, "11/2025"]
        options = {"handler_options": {"target_month": "11/2025"}}

        # Act
        result = process_sales_revenue_row(3, row, 1, options)

        # Assert
        assert result["ok"] is False
        assert "Headers not found" in result["error"]

    def test_process_row_invalid_target_month_format(self, sales_employee, headers):
        """Test processing row with invalid target month format."""
        # Arrange
        row = [sales_employee.code, sales_employee.username, 100000000, 150000000, 12, "11/2025"]
        options = {"headers": headers, "handler_options": {"target_month": "2025-11"}}

        # Act
        result = process_sales_revenue_row(3, row, 1, options)

        # Assert
        assert result["ok"] is False
        assert "Invalid target month format" in result["error"]
