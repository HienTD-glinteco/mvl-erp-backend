# PR3: Recruitment Dashboard - Fix Plan

> **Branch name:** `fix/recruitment-dashboard-charts`
> **Sprint:** Sprint 8
> **Estimated effort:** 1-2 days
> **Priority:** 🟡 Medium

---

## 📋 Issue Summary

| # | Task ID | Title | Status | Note |
|---|---------|-------|--------|------|
| 1 | [86ew3cqzd](./86ew3cqzd-chi-phi-tuyen-dung-binh-quan.md) | Chi phí tuyển dụng bình quân | ✅ RESOLVED | False alarm + Enhancement needed |
| 2 | [86ew3h4bh](./86ew3h4bh-bieu-do-so-lieu-tuyen-moi.md) | Số liệu tuyển mới theo nguồn/kênh | ✅ RESOLVED | False alarm - Data đúng |

---

## 🔍 Root Cause Analysis

### Issue 1: 86ew3cqzd - Chi phí tuyển dụng bình quân

**Description:**
> Chưa tính bình quân theo số ứng viên đã nhận việc, mới tổng số tiền

**API Endpoint:** `GET /api/hrm/dashboard/charts/cost-by-branches/`

**✅ VERIFIED: BE is CORRECT!**

**Production DB Query:**
```sql
-- RecruitmentCostReport (month_key: YYYY-MM)
SELECT month_key, branch_id, SUM(total_cost) as total_cost
FROM hrm_recruitmentcostreport
WHERE report_date BETWEEN '2025-12-01' AND '2025-12-31'
GROUP BY month_key, branch_id;

 month_key | branch_id | total_cost
-----------+-----------+-------------
 2025-12   |         3 | 73000000.00

-- HiredCandidateReport (month_key: MM/YYYY)
SELECT month_key, branch_id, SUM(num_candidates_hired) as total_hires
FROM hrm_hiredcandidatereport
WHERE report_date BETWEEN '2025-12-01' AND '2025-12-31'
GROUP BY month_key, branch_id;

 month_key | branch_id | total_hires
-----------+-----------+-------------
 12/2025   |         2 |           2
 12/2025   |         3 |           5
 12/2025   |         4 |           1
```

**API Response:**
```json
{
  "statistics": [{
    "total_cost": 73000000.0,
    "total_hires": 5,
    "avg_cost": 14600000.0  // ✅ = 73M ÷ 5 = 14.6M CORRECT!
  }]
}
```

**Root Cause: FE BUG** 🔴

| Aspect | Status | Note |
|--------|--------|------|
| Month_key conversion | ✅ OK | `12/2025` → `2025-12` works |
| avg_cost calculation | ✅ OK | 73M ÷ 5 = 14.6M |
| API response | ✅ OK | Contains both `total_cost` and `avg_cost` |
| **FE Display** | ❌ BUG | Showing `total_cost` instead of `avg_cost` |

**Action:**
- ✅ FE Bug đã được fix trước đó
- 🔧 BE Enhancement: Làm tròn `avg_cost` thành số nguyên (VND không có giá trị thập phân)

---

## 💡 Enhancement Request

### Round avg_cost to integer

**Issue:** `avg_cost` hiện trả về giá trị thập phân (e.g., `14600000.0`)

**Reason:** VND không có giá trị lẻ, nên không cần hiển thị `.0`

**Location:** `apps/hrm/api/views/recruitment_dashboard.py`

**Current Code:**
```python
avg_cost = total_cost / total_hires if total_hires > 0 else 0.0
```

**Proposed Fix:**
```python
avg_cost = round(total_cost / total_hires) if total_hires > 0 else 0
```

**Priority:** 🟢 Low (cosmetic improvement)

---

### Issue 2: 86ew3h4bh - Số liệu tuyển mới theo nguồn/kênh

**Description:**
> Chọn thời gian tháng trước (12/2025) => Check dữ liệu
> Bug: Dữ liệu lấy lên chưa chính xác

**✅ VERIFIED: BE is CORRECT!**

**Production DB Query:**
```sql
-- Candidates HIRED trong Dec 2025: 4 rows
SELECT id, code, status, onboard_date, recruitment_source_id
FROM hrm_recruitment_candidate
WHERE status = 'HIRED' AND onboard_date >= '2025-12-01' AND onboard_date <= '2025-12-31';
-- Result: 4 candidates (source_id=1)

-- RecruitmentSourceReport Dec 2025: 4 hires
SELECT recruitment_source_id, SUM(num_hires) as reported_hires
FROM hrm_recruitmentsourcereport
WHERE report_date >= '2025-12-01' AND report_date <= '2025-12-31'
GROUP BY recruitment_source_id;
-- Result: source_id=1, reported_hires=4 ✅ MATCHES!
```

**Conclusion:** Data đúng. Đã confirm với BA → Close issue

---

## 📁 Files to Review

| File | Purpose |
|------|---------|
| `apps/hrm/api/views/recruitment_dashboard.py` | Dashboard chart endpoints |
| `apps/hrm/api/views/recruitment_reports.py` | Report aggregation logic |
| `apps/hrm/models/recruitment_reports.py` | Report models |
| `apps/hrm/signals/recruitment_reports.py` | Report generation signals |

---

## 🔧 Investigation Tasks

### Task 3.1: Verify Chi phí bình quân calculation

**Goal:** Confirm if avg_cost is calculated correctly in API response

**Steps:**
1. Add debug logging to `_get_average_cost_breakdown_by_branches()`
2. Query both reports with same date range
3. Verify month_key conversion is correct
4. Check if FE is using correct field from response

**Code to add for debugging:**

```python
def _get_average_cost_breakdown_by_branches(self, from_date, to_date):
    # ... existing code ...

    # DEBUG: Log lookup data
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Cost lookup keys: {list(cost_by_branches.values('month_key', 'branch'))}")
    logger.info(f"Hired lookup keys: {list(hired_lookup.keys())}")

    # ... rest of code ...
```

### Task 3.2: Verify Số liệu tuyển mới data

**Goal:** Confirm if report data matches actual candidate count

**Steps:**
1. Query RecruitmentCandidate for 12/2025
2. Query corresponding Report models
3. Compare counts by source/channel

### Task 3.3: Fix confirmed issues

Based on investigation results, implement fixes.

---

## ✅ Test Cases

### QA Test Table

| # | Test ID | Mô tả | Preconditions | Steps | Expected Result | Priority |
|---|---------|-------|---------------|-------|-----------------|----------|
| 1 | TC-PR3-001 | Chi phí bình quân = Total / Số người nhận việc | - Có data tuyển dụng tháng 12/2025<br>- Chi nhánh A: 10M, 2 người | 1. Mở Dashboard<br>2. Chọn tháng 12/2025<br>3. Xem biểu đồ chi phí | Chi nhánh A: 5M/người (10M ÷ 2) | 🔴 Critical |
| 2 | TC-PR3-002 | Chi phí bình quân = 0 khi không có người nhận việc | - Chi nhánh B: 5M, 0 người | 1. Xem biểu đồ chi phí | Chi nhánh B: 0 (không chia cho 0) | 🟠 High |
| 3 | TC-PR3-003 | Số liệu tuyển mới khớp với thực tế | - 5 ứng viên từ nguồn Referral<br>- 3 ứng viên từ nguồn Website | 1. Mở biểu đồ nguồn tuyển<br>2. Chọn tháng 12/2025 | Referral: 5, Website: 3 | 🔴 Critical |
| 4 | TC-PR3-004 | Filter theo thời gian hoạt động đúng | - Data có từ 01/12 đến 31/12 | 1. Chọn từ 01/12 đến 31/12 | Hiển thị đủ data tháng 12 | 🟠 High |
| 5 | TC-PR3-005 | Không có data → Hiển thị 0 | - Không có tuyển dụng tháng 11/2025 | 1. Chọn tháng 11/2025 | Tất cả giá trị = 0 | 🟢 Normal |

---

## 📊 Implementation Checklist

### Issue 1: 86ew3cqzd - Chi phí bình quân ✅ RESOLVED
- [x] Query RecruitmentCostReport và HiredCandidateReport với cùng date range
- [x] Verify month_key format conversion logic (`12/2025` → `2025-12`)
- [x] Test API endpoint và check response format
- [x] ✅ **Confirmed: BE is correct, FE đã fix trước đó**
- [ ] 🔧 **Enhancement:** Round avg_cost to integer (optional)

### Issue 2: 86ew3h4bh - Số liệu tuyển mới ✅ RESOLVED
- [x] Query RecruitmentCandidate for 12/2025 (4 candidates HIRED)
- [x] Query corresponding Report models (4 hires reported)
- [x] Compare counts by source/channel → ✅ MATCH
- [x] ✅ **Confirmed: BE is correct, False alarm**

### Validation Phase
- [ ] Run tests: `ENVIRONMENT=test poetry run pytest apps/hrm/tests/test_recruitment_dashboard.py`
- [ ] Pre-commit: `pre-commit run --all-files`
- [ ] Manual QA with test data

---

## 📝 Notes

1. **Need more info từ QA:**
   - Issue 86ew3h4bh cần clarify: FE đang gọi API nào? Data cụ thể nào sai?
   - Screenshots cho thấy chart nhưng không rõ expected vs actual

2. **FE Collaboration:**
   - Cần verify FE đang hiển thị field nào từ API response
   - Có thể là bug FE (hiển thị total_cost thay vì avg_cost)

3. **Data Verification:**
   - Cần access production DB để verify data consistency
   - Hoặc reproduce với test data

---

## 🔗 Related Files

- [86ew3cqzd-chi-phi-tuyen-dung-binh-quan.md](./86ew3cqzd-chi-phi-tuyen-dung-binh-quan.md)
- [86ew3h4bh-bieu-do-so-lieu-tuyen-moi.md](./86ew3h4bh-bieu-do-so-lieu-tuyen-moi.md)
