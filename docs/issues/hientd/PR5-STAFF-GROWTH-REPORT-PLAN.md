# PR5: Staff Growth Report - Fix Plan

> **Branch name:** `fix/staff-growth-report-duplicate-count`
> **Sprint:** Sprint 8
> **Estimated effort:** 1-2 days
> **Priority:** 🟠 High

---

## 📋 Issue Summary

| # | Task ID | Title | Status | Module |
|---|---------|-------|--------|--------|
| 1 | [86ew457ta](./86ew457ta-bc-tang-truong-ns-nghi-nhieu-lan.md) | BC tăng trưởng NS_Nhân sự nghỉ nhiều lần đang đếm nhiều lần | 🟢 OPEN | 4.8. Báo cáo |

---

## 🔍 Root Cause Analysis

### Issue Description

> Nhân viên MV000000102 (Nguyen Van An) có 2 lần nghỉ việc trong tháng 1/2026
> Bug: BC đang đếm lên 2 lần nghỉ cho NV này
> Expected: Trong thời gian truy vấn, nếu nhân viên phát sinh nhiều lần nghỉ việc => Chỉ đếm 1 lần

### Current Logic (BROKEN)

**Step 1: Event Tracking** (`apps/hrm/tasks/reports_hr/helpers.py`)

Mỗi khi có event RESIGNATION, hệ thống gọi:
```python
_update_staff_growth_counter(
    report_date, branch_id, block_id, department_id,
    "num_resignations", delta=1, month_key, week_key
)
```

**Step 2: Data Storage** (`StaffGrowthReport` model)

Report lưu theo **ngày + department**:
```
| report_date | department_id | num_resignations |
|-------------|---------------|------------------|
| 2026-01-05  | 8             | 1                | ← Lần nghỉ 1
| 2026-01-10  | 8             | 1                | ← Lần nghỉ 2
```

**Step 3: API Aggregation** (`apps/hrm/api/views/recruitment_reports.py`)

API aggregate theo `Sum("num_resignations")`:
```python
aggregated = queryset.values(period_field).annotate(
    num_resignations=Sum("num_resignations"),
)
# Result: num_resignations = 1 + 1 = 2 ← BUG!
```

### Root Cause

**Logic đếm số EVENT (lần nghỉ việc)** thay vì **số EMPLOYEE (nhân viên nghỉ việc)**

Khi 1 nhân viên có 2 events RESIGNATION trong cùng 1 tháng → BC đếm 2 thay vì 1.

---

## 🔧 Solution Options

### Option 1: Track Employee IDs in Report (Recommended)

Thay đổi cách lưu data - track employee IDs đã đếm để tránh duplicate.

**Pros:**
- Fix đúng root cause
- Accurate count forever

**Cons:**
- Cần migration thêm field
- Cần refactor logic cập nhật report

### Option 2: Query Distinct Employees at API Level

Không dùng pre-aggregated report, query trực tiếp từ `EmployeeWorkHistory`.

**API Implementation:**
```python
def staff_growth(self, request):
    # Query distinct employees with resignation events
    resigned_count = EmployeeWorkHistory.objects.filter(
        name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
        status=Employee.Status.RESIGNED,
        date__range=(from_date, to_date),
        # Apply data scope filter
    ).values('employee_id').distinct().count()
```

**Pros:**
- Không cần migration
- Quick fix
- Always accurate

**Cons:**
- Slower (query on demand)
- Không tận dụng được pre-calculated report

### Option 3: Hybrid - Use Report with Distinct Query for Resignation

Giữ logic hiện tại cho các metrics khác, nhưng query distinct cho `num_resignations`.

**Pros:**
- Minimal change
- Fix specific issue

**Cons:**
- Inconsistent approach

---

## 📋 Recommended: Option 2 (Query Distinct)

Cho short-term fix, **Option 2** là phù hợp nhất:
- Quick implementation
- No migration needed
- Accurate results

**Long-term:** Consider Option 1 for better performance with large datasets.

---

## 🔧 Implementation

### Fix: Query Distinct Employees for Resignations

**File:** `apps/hrm/api/views/recruitment_reports.py`

**Current Code:**
```python
aggregated = (
    queryset.values(period_field)
    .order_by(period_field)
    .annotate(
        num_introductions=Sum("num_introductions"),
        num_returns=Sum("num_returns"),
        num_recruitment_source=Sum("num_recruitment_source"),
        num_transfers=Sum("num_transfers"),
        num_resignations=Sum("num_resignations"),  # ← BUG
    )
)
```

**Proposed Fix:**

Replace aggregation logic to query distinct employees for resignation count:

```python
@action(detail=False, methods=["get"], url_path="staff-growth")
def staff_growth(self, request):
    """Aggregate staff growth data by week or month period."""
    queryset, from_date, to_date, data_scope_qs, period_type = self._prepare_report_queryset(
        request,
        StaffGrowthReportParametersSerializer,
        StaffGrowthReport,
        period_param="period_type",
    )

    # Group by period (week or month)
    if period_type == ReportPeriodType.WEEK.value:
        period_field = "week_key"
    else:
        period_field = "month_key"

    # Aggregate non-resignation metrics from report
    aggregated = (
        queryset.values(period_field)
        .order_by(period_field)
        .annotate(
            num_introductions=Sum("num_introductions"),
            num_returns=Sum("num_returns"),
            num_recruitment_source=Sum("num_recruitment_source"),
            num_transfers=Sum("num_transfers"),
            # Don't use Sum for resignations - will calculate separately
        )
    )

    # Get distinct resignation counts per period from EmployeeWorkHistory
    resignation_counts = self._get_distinct_resignation_counts(
        from_date, to_date, period_type, data_scope_qs
    )

    # Merge results
    results = []
    for item in aggregated:
        period_key = item[period_field]
        # ... build result with resignation_counts[period_key]


def _get_distinct_resignation_counts(
    self, from_date, to_date, period_type, data_scope_qs
) -> dict[str, int]:
    """Get distinct employee resignation counts per period.

    Returns dict mapping period_key to count of distinct employees resigned.
    """
    from apps.hrm.models import EmployeeWorkHistory

    # Query distinct employees with resignation events
    qs = EmployeeWorkHistory.objects.filter(
        name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
        status=Employee.Status.RESIGNED,
        date__range=(from_date, to_date),
    )

    # Apply data scope filter if available
    if data_scope_qs is not None:
        qs = qs.filter(employee__in=data_scope_qs.values('id'))

    # Annotate with period key
    if period_type == ReportPeriodType.WEEK.value:
        # ... calculate week_key
        pass
    else:
        # month_key format: MM/YYYY
        qs = qs.annotate(
            period_key=Concat(
                ExtractMonth('date'), Value('/'), ExtractYear('date'),
                output_field=CharField()
            )
        )

    # Group by period and count distinct employees
    result = (
        qs.values('period_key')
        .annotate(count=Count('employee_id', distinct=True))
    )

    return {item['period_key']: item['count'] for item in result}
```

---

## 📁 Files to Modify

| File | Change |
|------|--------|
| `apps/hrm/api/views/recruitment_reports.py` | Add distinct employee count for resignations |

---

## ✅ Test Cases

### Unit Tests

```python
@pytest.mark.django_db
class TestStaffGrowthReportDistinctCount:
    """Test that resignation count is distinct per employee."""

    def test_employee_with_multiple_resignations_counted_once(
        self, api_client, employee_with_multiple_resignations
    ):
        """Employee with 2 resignations in same month should be counted once."""
        # Arrange: Employee has 2 resignation events in Jan 2026

        # Act: Call staff-growth API
        response = api_client.get(
            "/api/hrm/recruitment-reports/staff-growth/",
            {"from_date": "2026-01-01", "to_date": "2026-01-31", "period_type": "month"}
        )

        # Assert: num_resignations = 1 (not 2)
        assert response.status_code == 200
        data = response.json()["data"]
        assert data[0]["num_resignations"] == 1
```

### QA Test Table

| # | Test ID | Mô tả | Preconditions | Steps | Expected Result | Priority |
|---|---------|-------|---------------|-------|-----------------|----------|
| 1 | TC-PR5-001 | NV nghỉ 2 lần cùng tháng → Đếm 1 | - NV MV000000102 có 2 events RESIGNATION trong Jan 2026 | 1. Mở BC tăng trưởng NS<br>2. Chọn tháng 01/2026 | num_resignations = 1 | 🔴 Critical |
| 2 | TC-PR5-002 | 2 NV khác nhau nghỉ → Đếm 2 | - NV A nghỉ 05/01<br>- NV B nghỉ 10/01 | 1. Mở BC tăng trưởng NS<br>2. Chọn tháng 01/2026 | num_resignations = 2 | 🔴 Critical |
| 3 | TC-PR5-003 | NV nghỉ 2 tháng khác nhau → Đếm riêng | - NV nghỉ 01/2026 và 02/2026 | 1. Mở BC<br>2. Chọn range 01-02/2026 | Mỗi tháng đếm 1 | 🟠 High |

---

## 📊 Implementation Checklist

- [ ] Add `_get_distinct_resignation_counts()` helper method
- [ ] Update `staff_growth()` action to use distinct count
- [ ] Add unit tests for distinct counting
- [ ] Verify with test data

### Validation Phase
- [ ] Run tests: `ENVIRONMENT=test poetry run pytest apps/hrm/tests/test_recruitment_reports.py -v`
- [ ] Pre-commit: `pre-commit run --all-files`
- [ ] Manual QA with production data (MV000000102)

---

## 📝 Notes

1. **Same issue may apply to other metrics:** `num_transfers`, `num_returns` - verify if they also need distinct count
2. **Performance consideration:** Query from `EmployeeWorkHistory` may be slower than using pre-calculated report
3. **Alternative approach:** Refactor report model to track employee IDs (long-term solution)

---

## 🔗 Related Files

- [86ew457ta-bc-tang-truong-ns-nghi-nhieu-lan.md](./86ew457ta-bc-tang-truong-ns-nghi-nhieu-lan.md)
