
import pytest
from datetime import date
from unittest.mock import patch, MagicMock

from apps.payroll.tasks import aggregate_sales_revenue_report_task
from apps.payroll.import_handlers.sales_revenue import on_import_complete


class TestSalesRevenueAggregationTask:
    """Test sales revenue report aggregation task."""

    @pytest.mark.django_db
    def test_aggregate_with_target_month(self):
        """Task should aggregate only for specified month."""
        with patch('apps.payroll.tasks.SalesRevenueReportAggregator') as mock_agg:
            mock_agg.aggregate_for_months.return_value = 5

            result = aggregate_sales_revenue_report_task("2025-12-01")

            mock_agg.aggregate_for_months.assert_called_once_with([date(2025, 12, 1)])
            assert result["status"] == "success"
            assert result["count"] == 5

    @pytest.mark.django_db
    def test_aggregate_without_target_month_fallback(self):
        """Task without target_month should aggregate all months."""
        with patch('apps.payroll.tasks.SalesRevenueReportAggregator') as mock_agg:
            mock_agg.aggregate_from_import.return_value = 10

            result = aggregate_sales_revenue_report_task(None)

            mock_agg.aggregate_from_import.assert_called_once()
            assert result["status"] == "success"


class TestOnImportComplete:
    """Test on_import_complete callback."""

    def test_calls_task_with_target_month(self):
        """on_import_complete should call task with parsed target_month."""
        with patch('apps.payroll.import_handlers.sales_revenue.aggregate_sales_revenue_report_task') as mock_task:
            options = {"target_month": "12/2025"}

            on_import_complete(import_job_id=1, options=options)

            mock_task.delay.assert_called_once_with("2025-12-01")

    def test_skips_if_no_target_month(self):
        """on_import_complete should call task with None if no target_month in options."""
        with patch('apps.payroll.import_handlers.sales_revenue.aggregate_sales_revenue_report_task') as mock_task:
            options = {}

            on_import_complete(import_job_id=1, options=options)

            mock_task.delay.assert_called_once_with(None)
