# PR4: Staff Quality Dashboard - Fix Plan

> **Branch name:** `fix/staff-quality-dashboard`
> **Sprint:** Sprint 8
> **Estimated effort:** 0.5 day
> **Priority:** 🟠 High

---

## 📋 Issue Summary

| # | Task ID | Title | Status | Root Cause |
|---|---------|-------|--------|------------|
| 1 | [86ew5cye2](./86ew5cye2-bc-chat-luong-nhan-su-chua-hien-thi.md) | BC chất lượng nhân sự_Chưa hiển thị dữ liệu | 🟢 OPEN | Report table empty |
| 2 | [86ew5da4f](./86ew5da4f-bieu-do-chat-luong-nhan-su-khoi-kd.md) | Biểu đồ chất lượng nhân sự khối KD chưa hiển thị | 🟠 IN PROGRESS | Report table empty |

---

## 🔍 Root Cause Analysis

### ✅ CONFIRMED: Report Table Empty

**Production DB Query:**
```sql
mvl_erp=> SELECT COUNT(*) FROM payroll_sales_revenue_report;
 count
-------
     0
(1 row)
```

**Root Cause:** `SalesRevenueReportFlatModel` có 0 records vì task aggregation chưa được trigger đúng cách sau import.

---

## 🐛 Bug Analysis

### Current Flow (BROKEN)

```
Import SalesRevenue → on_import_complete() → aggregate_sales_revenue_report_task.delay()
                                                        ↓
                                          aggregate_from_import() ← Xử lý TẤT CẢ months
```

**Issues:**
1. `on_import_complete()` không truyền `target_month` vào task
2. `aggregate_from_import()` query TẤT CẢ months từ SalesRevenue → **Performance BAD**
3. Task có thể timeout hoặc chạy quá lâu khi data lớn

### Current Code

**File:** `apps/payroll/import_handlers/sales_revenue.py`
```python
def on_import_complete(import_job_id: int, options: dict) -> None:
    # ❌ Không truyền target_month
    aggregate_sales_revenue_report_task.delay()
```

**File:** `apps/payroll/tasks.py`
```python
@shared_task
def aggregate_sales_revenue_report_task():
    # ❌ Xử lý TẤT CẢ months
    count = SalesRevenueReportAggregator.aggregate_from_import()
```

---

## 🔧 Fix Implementation

### Fix 1: Update `on_import_complete` to pass target_month

**File:** `apps/payroll/import_handlers/sales_revenue.py`

```python
def on_import_complete(import_job_id: int, options: dict) -> None:
    """Called after import completes successfully to trigger report aggregation.

    Args:
        import_job_id: ID of the completed ImportJob
        options: Import options dictionary containing 'target_month' (MM/YYYY format)
    """
    target_month_str = options.get("target_month")
    if not target_month_str:
        return  # No target month, skip aggregation

    target_month = _parse_target_month(target_month_str)
    if not target_month:
        return  # Invalid format, skip

    # Trigger aggregation for specific month only
    aggregate_sales_revenue_report_task.delay(target_month.isoformat())
```

### Fix 2: Update task to accept target_month parameter

**File:** `apps/payroll/tasks.py`

```python
@shared_task
def aggregate_sales_revenue_report_task(target_month_iso: str | None = None):
    """Aggregate sales revenue data into flat report model in background.

    Args:
        target_month_iso: Target month in ISO format (YYYY-MM-DD). If None, aggregates all months.

    Returns:
        dict: Result with count of records created/updated
    """
    import logging
    from datetime import date

    logger = logging.getLogger(__name__)

    try:
        if target_month_iso:
            # Parse ISO date and aggregate for specific month only
            target_month = date.fromisoformat(target_month_iso)
            count = SalesRevenueReportAggregator.aggregate_for_months([target_month])
            logger.info(f"Sales revenue report aggregation for {target_month}: {count} records")
        else:
            # Fallback: aggregate all months (for manual triggers)
            count = SalesRevenueReportAggregator.aggregate_from_import()
            logger.info(f"Sales revenue report aggregation (all months): {count} records")

        return {"status": "success", "count": count}
    except Exception as e:
        import sentry_sdk

        sentry_sdk.capture_exception(e)
        logger.error(f"Sales revenue report aggregation failed: {e}")
        return {"status": "failed", "error": str(e)}
```

---

## 📁 Files to Modify

| File | Change |
|------|--------|
| `apps/payroll/import_handlers/sales_revenue.py` | Pass target_month to task |
| `apps/payroll/tasks.py` | Accept target_month parameter |

---

## ✅ Test Cases

### Unit Tests

```python
# apps/payroll/tests/test_sales_revenue_aggregation.py

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
        """on_import_complete should skip if no target_month in options."""
        with patch('apps.payroll.import_handlers.sales_revenue.aggregate_sales_revenue_report_task') as mock_task:
            options = {}

            on_import_complete(import_job_id=1, options=options)

            mock_task.delay.assert_not_called()
```

### QA Test Table

| # | Test ID | Mô tả | Preconditions | Steps | Expected Result | Priority |
|---|---------|-------|---------------|-------|-----------------|----------|
| 1 | TC-PR4-001 | Import sales revenue → Report được tạo | - File import hợp lệ<br>- Target month: 12/2025 | 1. Import file sales revenue<br>2. Chờ task hoàn thành<br>3. Check DB report | Report có data cho tháng 12/2025 | 🔴 Critical |
| 2 | TC-PR4-002 | Dashboard hiển thị biểu đồ sau import | - Đã import thành công | 1. Login TP HCNS<br>2. Mở Dashboard<br>3. Xem biểu đồ chất lượng KD | Biểu đồ hiển thị data | 🔴 Critical |
| 3 | TC-PR4-003 | BC chất lượng NS hiển thị data | - Đã import thành công | 1. Login TP HCNS<br>2. Mở BC chất lượng NS<br>3. Chọn range có data | Báo cáo hiển thị data | 🔴 Critical |
| 4 | TC-PR4-004 | Re-import cùng tháng → Update data | - Đã import tháng 12/2025<br>- File mới với data khác | 1. Import lại file mới<br>2. Check report | Report được update, không duplicate | 🟠 High |

---

## 📊 Implementation Checklist

- [ ] Update `on_import_complete()` to pass target_month
- [ ] Update `aggregate_sales_revenue_report_task()` to accept target_month parameter
- [ ] Add unit tests for task and callback
- [ ] Manual test: Import → Check report table

### One-time Data Fix
- [ ] Run `aggregate_sales_revenue_report_task.delay()` (no args) to aggregate existing data

### Validation Phase
- [ ] Run tests: `ENVIRONMENT=test poetry run pytest apps/payroll/tests/test_sales_revenue_import_handler.py -v`
- [ ] Pre-commit: `pre-commit run --all-files`
- [ ] Manual QA with production data

---

## 📝 Notes

1. **One-time fix needed:** Sau khi deploy, cần chạy task 1 lần để aggregate existing data
2. **Performance:** Fix này đảm bảo chỉ aggregate tháng được import, không phải tất cả
3. **Backward compatible:** Task vẫn hỗ trợ gọi không có args (aggregate all) cho manual triggers

---

## 🔗 Related Files

- [86ew5cye2-bc-chat-luong-nhan-su-chua-hien-thi.md](./86ew5cye2-bc-chat-luong-nhan-su-chua-hien-thi.md)
- [86ew5da4f-bieu-do-chat-luong-nhan-su-khoi-kd.md](./86ew5da4f-bieu-do-chat-luong-nhan-su-khoi-kd.md)
