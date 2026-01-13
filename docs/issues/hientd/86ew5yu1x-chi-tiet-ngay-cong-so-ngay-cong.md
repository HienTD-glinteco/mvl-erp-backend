# Màn chi tiết ngày công: Sau khi xử lý đề xuất, chưa reload trạng thái

| Field | Value |
|-------|-------|
| **ID** | 86ew5yu1x |
| **Status** | RE-OPEN |
| **Priority** | - |
| **Sprint** | Sprint 8 |
| **SubModule** | - |
| **Points** | - |
| **Assignees** | Lê Sơn Duy, Hưng Lê, Nguyễn Việt Mạnh, TD Hien |
| **Creator** | Lê Sơn Duy |
| **Created** | 2025-01-12 |
| **URL** | https://app.clickup.com/t/86ew5yu1x |

## Description

**Flow:** Vào màn chi tiết ngày công → nhấn xem chi tiết 1 đề xuất → "Duyệt" đề xuất → quay lại màn chi tiết ngày công

**Reality:** Hệ thống chưa cập nhật "Số ngày công" mới của ngày công

**Expected Outcome:** Hệ thống cập nhật "Số ngày công" mới của ngày công

**Chi tiết lỗi:** BE chưa trả về thông tin "Số ngày công" sau khi duyệt đề xuất

## Attachments

- [86ew5yu1x-1.png](attachments/86ew5yu1x-1.png)

---

## Comments

### Comment 1 - Lê Sơn Duy (2025-01-12) ⚠️ CURRENT BUG
> Bug: Khi quay lại, số ngày công bị hiển thị rỗng (sau khi duyệt đề xuất "Chế độ làm việc hậu thai sản")
>
> **Root Cause Analysis:**
> - Liên quan đến tính công sau khi duyệt đề xuất hậu thai sản
> - `PostMaternityBenefits` proposal cần trigger recalculate `working_days`
> - Bug nằm trong `timesheet_calculator.py`
>
> **→ MOVE TO PR1 (Timesheet Calculator)**
