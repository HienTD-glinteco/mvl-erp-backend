# PR1: Timesheet Calculator - Fix Plan

> **Branch name:** `fix/timesheet-calculator-working-days-status`
> **Sprint:** Sprint 8 (7/1 - 20/1)
> **Estimated effort:** 3-5 days
> **Files affected:** 4-6 files

---

## ⚠️ CRITICAL: Business Logic Priority

### Thứ tự ưu tiên khi tính toán ngày công (Thấp → Cao)

```
Đề xuất (Proposal) < Sự kiện (Events) < Lịch sử chấm công (Attendance)
     ↓                    ↓                      ↓
  Kế hoạch            Thực tế xảy ra        Thực tế đi làm
  (thấp nhất)         (trung bình)          (cao nhất)
```

| Layer | Ví dụ | Ý nghĩa |
|-------|-------|---------|
| **Đề xuất** | Xin nghỉ phép, WFH, OT | Kế hoạch - có thể thay đổi |
| **Sự kiện** | Thay đổi HĐ, miễn CC, bổ nhiệm | Thực tế đã xảy ra |
| **Chấm công** | Log check-in/out | Bằng chứng thực tế đi làm |

### Quy tắc ưu tiên

1. **Attendance > Leave Proposal**: Nhân sự xin nghỉ nhưng vẫn có log chấm công → **tính như đi làm bình thường**
2. **Nghỉ có lương + đi làm → hoàn ngày nghỉ**: Nếu đã duyệt nghỉ phép có lương nhưng NV vẫn đi làm → **cần hoàn lại ngày phép**
3. **Sự kiện > Đề xuất**: Thay đổi hợp đồng, miễn chấm công ghi đè lên đề xuất

---

## 📌 Leave Balance Flow Analysis

### Khi nào phép được trừ?

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LEAVE BALANCE FLOW                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. Proposal APPROVED                                                        │
│     └─► ProposalService._execute_leave_proposal()                           │
│         └─► Set entry.absent_reason = PAID_LEAVE                            │
│             (KHÔNG trừ phép trực tiếp ở đây)                                │
│                                                                              │
│  2. Monthly Timesheet Refresh (cuối tháng hoặc on-demand)                   │
│     └─► EmployeeMonthlyTimesheet.refresh_for_employee_month()               │
│         └─► compute_aggregates()                                             │
│             └─► Count entries WHERE absent_reason = PAID_LEAVE              │
│                 └─► paid_leave_days = COUNT(...)                            │
│                 └─► consumed_leave_days = paid_leave_days                   │
│                 └─► remaining = opening + generated - consumed              │
│                                                                              │
│  ═══════════════════════════════════════════════════════════════════════════│
│  KẾT LUẬN: Phép được TÍNH (không phải trừ trực tiếp) dựa trên               │
│            COUNT các ngày có absent_reason = PAID_LEAVE                      │
│            trong TimeSheetEntry                                              │
│                                                                              │
│  => Nếu entry có chấm công + absent_reason = PAID_LEAVE                     │
│     Và ta xóa absent_reason đi → phép tự động được "hoàn"                   │
│     vì consumed_leave_days sẽ giảm trong lần refresh tiếp theo              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Cách hoàn phép khi NV đi làm dù đã duyệt nghỉ

**Giải pháp đơn giản**: Xóa `absent_reason` khỏi entry khi có attendance

```python
# Trong TimesheetCalculator._handle_leave_status()
if has_attendance:
    # Clear absent_reason → phép tự động được hoàn khi monthly refresh
    self.entry.absent_reason = None
    return False  # Continue with normal attendance calculation
```

**Kết quả:**
- `TimeSheetEntry.absent_reason` = None (không phải PAID_LEAVE)
- Khi `EmployeeMonthlyTimesheet.refresh_for_employee_month()` chạy:
  - `paid_leave_days` = COUNT WHERE absent_reason = PAID_LEAVE → giảm 1
  - `consumed_leave_days` giảm → `remaining_leave_days` tăng
- **Phép tự động được hoàn** mà không cần service riêng!

---

## 📋 Issues Covered (12 bugs)

| # | Task ID | Title | Root Cause |
|---|---------|-------|------------|
| 1 | 86ew4zetx | NV nghỉ hưởng lương nhưng vẫn chấm công | `_handle_leave_status()` skip logic khi có attendance |
| 2 | 86ew50mhq | Ngày tương lai NV miễn CC | `handle_exemption()` không check future date |
| 3 | 86ew50tk2 | Xóa NV miễn chấm công | `snapshot_exemption_status()` không recalculate |
| 4 | 86ew54a72 | Ngày không có ca nhưng duyệt đề xuất | `_handle_leave_status()` không check schedule |
| 5 | 86ew54m1w | Số ngày công ngày làm bù | `compute_working_days()` không handle absent on comp day |
| 6 | 86ew56gt2 | Số ngày công ngày lễ | `compute_working_days()` không trả về value cho holiday |
| 7 | 86ew5cxen | Cập nhật trạng thái sang ngày mới | Celery task không trigger đúng |
| 8 | 86ew60rzf | Trạng thái 1 log + duyệt đề xuất | Leave logic override attendance logic |
| 9 | 86ew61yj8 | Công sau duyệt hậu thai sản | `_get_maternity_bonus()` điều kiện sai |
| 10 | 86ew614qt | Công thử việc/chính thức sau đổi HĐ | `snapshot_contract_info()` không recalculate past entries |
| **11** | **86evyq66n** | **[NEW] Nghỉ phép có lương → working_days sai** | `_execute_leave_proposal()` set status=None nhưng `compute_working_days()` check status==ABSENT |
| **12** | **86ew5yu1x** | **[NEW] Số ngày công rỗng sau duyệt hậu thai sản** | PostMaternityBenefits không trigger recalculate `working_days` |

---

## 🔍 Root Cause Analysis

### Category A: Leave vs Attendance Priority (Issues 1, 4, 8) ⚠️ VI PHẠM QUY TẮC ƯU TIÊN

**Problem:** Khi nhân viên được duyệt nghỉ phép nhưng vẫn đi làm (có log chấm công), hệ thống hiện tại:
- Skip leave logic nếu có attendance (`_handle_leave_status()` return False)
- Nhưng không xử lý case nghỉ phép có lương → cần hoàn trả ngày phép

**Current Code:**
```python
# _handle_leave_status() - Line 377-380
has_attendance = self.entry.start_time or self.entry.end_time
if has_attendance:
    return False  # Skip leave logic entirely
```

**Expected Logic theo Priority Rule:**
1. **Có log CC → Attendance wins** → tính như đi làm (status = ON_TIME/NOT_ON_TIME)
2. **Nếu leave là PAID_LEAVE → trigger hoàn trả ngày phép** (business logic riêng)
3. **Ngày không có ca (CN) + có đề xuất → working_days = 0, status = None**

---

### Category B: Future Date & Exemption Logic (Issues 2, 3)

**Problem:** Nhân viên miễn chấm công được tính công đầy đủ ngay cả cho ngày tương lai.

**Current Code:**
```python
# handle_exemption() - Line 84-93
if self.entry.is_exempt:
    self.entry.status = TimesheetStatus.ON_TIME
    self.entry.working_days = self._get_max_working_days()  # Always 1.0
    return True
```

**Expected Logic:**
1. Ngày tương lai + miễn CC → status = None, working_days = None
2. Ngày quá khứ + miễn CC → status = ON_TIME, working_days = max
3. Xóa khỏi danh sách miễn CC → recalculate các ngày sau ngày xóa

---

### Category C: Compensatory & Holiday Working Days (Issues 5, 6)

**Problem:** Số ngày công của ngày làm bù và ngày lễ không được tính đúng.

**Issue 5 - Ngày làm bù mà vắng:**
- Reality: working_days = 0
- Expected: working_days = -0.5 hoặc -1.0 (nợ công)

**Issue 6 - Ngày lễ:**
- Reality: working_days = None (không hiển thị)
- Expected: working_days = 1.0 (hưởng nguyên lương)

**Root Cause:** `compute_working_days()` không handle đặc biệt cho HOLIDAY và COMPENSATORY day_type.

---

### Category D: Single Punch + Leave Combination (Issue 8)

**Problem:** Khi có 1 log CC + được duyệt đề xuất → trạng thái sai.

**Current Logic:**
- Single punch → SINGLE_PUNCH status
- Leave → ABSENT status

**Expected:**
- 1 log + bất kỳ đề xuất nào → "Quên check-in/out" (SINGLE_PUNCH)
- working_days = 1/2 max days (theo rule single punch)

---

### Category E: Maternity Bonus (Issue 9)

**Problem:** Bonus 1 giờ (0.125 công) không được cộng cho một số nhân viên.

**Current Code:**
```python
# _get_maternity_bonus() - Line 509-517
if (
    self.entry.allowed_late_minutes_reason == AllowedLateMinutesReason.MATERNITY
    and self.entry.start_time
    and self.entry.end_time
):
    return Decimal("0.125")
```

**Possible Issue:** `allowed_late_minutes_reason` không được snapshot đúng từ proposal POST_MATERNITY_BENEFITS.

---

### Category F: Contract Change Retroactive (Issue 10)

**Problem:** Khi ban hành HĐ mới với ngày hiệu lực trong quá khứ, các entry cũ không được recalculate.

**Root Cause:** `snapshot_contract_info()` chỉ chạy khi entry được create/update, không có signal để recalculate khi Contract thay đổi.

---

### Category G: Daily Status Update Job (Issue 7)

**Problem:** Một số nhân viên không được update trạng thái "Vắng" khi sang ngày mới.

**Root Cause:** Celery task `finalize_yesterday_timesheets` có thể bỏ sót một số entries.

---

### Category H: Leave Proposal Execute (Issues 11, 12) ⚠️ NEW

**Issue 11 - 86evyq66n:** Nghỉ phép có lương → `working_days` không đúng

**Problem:** Sau khi duyệt đề xuất nghỉ phép có lương, `working_days` không được set = giá trị max của ngày.

**Root Cause:** Mismatch giữa `_execute_leave_proposal()` và `compute_working_days()`:

```python
# proposal_service.py - _execute_leave_proposal()
entry.status = None  # ← Sets status to None

# timesheet_calculator.py - compute_working_days()
if self.entry.status == TimesheetStatus.ABSENT:  # ← Checks for ABSENT
    if self.entry.absent_reason == TimesheetReason.PAID_LEAVE:
        self.entry.working_days = Decimal("1.00")
    return
# ↑ NEVER ENTERS because status = None ≠ ABSENT
```

**Solution:**
- Option A: Change `_execute_leave_proposal()` to set `status = ABSENT`
- Option B: Add new condition in `compute_working_days()` to check `absent_reason` directly

**Issue 12 - 86ew5yu1x:** Số ngày công rỗng sau duyệt hậu thai sản

**Problem:** Sau khi duyệt đề xuất hậu thai sản, `working_days` hiển thị rỗng.

**Root Cause:** `PostMaternityBenefits` proposal không trigger recalculate của TimeSheetEntry.

```python
# proposal_service.py - handler_map
handler_map = {
    ProposalType.PAID_LEAVE: ProposalService._execute_leave_proposal,
    ProposalType.UNPAID_LEAVE: ProposalService._execute_leave_proposal,
    ProposalType.MATERNITY_LEAVE: ProposalService._execute_leave_proposal,
    ProposalType.TIMESHEET_ENTRY_COMPLAINT: ProposalService._execute_complaint_proposal,
    ProposalType.OVERTIME_WORK: ProposalService._execute_overtime_proposal,
    ProposalType.DEVICE_CHANGE: ProposalService._execute_device_change_proposal,
    # ⚠️ POST_MATERNITY_BENEFITS is NOT handled!
}
```

**Solution:** Add handler for `POST_MATERNITY_BENEFITS` to recalculate affected TimeSheetEntries.

---

## 🛠️ Implementation Plan

### Phase 1: Core Calculator Fixes

#### Task 1.1: Fix Future Date Handling for Exemption
**File:** `apps/hrm/services/timesheet_calculator.py`

```python
def handle_exemption(self) -> bool:
    """Check if employee is exempt. If so, grant full credit and exit."""
    if not self.entry.is_exempt:
        return False

    # NEW: Don't finalize future dates
    from datetime import date
    if self.entry.date > date.today():
        self.entry.status = None
        self.entry.working_days = None
        return True

    self.entry.status = TimesheetStatus.ON_TIME
    self.entry.working_days = self._get_max_working_days()
    # Reset penalties
    self.entry.late_minutes = 0
    self.entry.early_minutes = 0
    self.entry.is_punished = False
    self.entry.absent_reason = None
    return True
```

#### Task 1.2: Fix Leave + Attendance Priority (CRITICAL - Áp dụng Priority Rule)
**File:** `apps/hrm/services/timesheet_calculator.py`

**Priority Flow:**
```
                    ┌─────────────────────┐
                    │   Has Attendance?   │
                    └─────────┬───────────┘
                              │
             ┌────────────────┴────────────────┐
             │ YES                              │ NO
             ▼                                  ▼
    ┌─────────────────────┐          ┌─────────────────────┐
    │ Tính công bình thường│          │ Check Leave Proposal│
    │ + CLEAR absent_reason│          │                     │
    │ (Attendance WINS)    │          └─────────────────────┘
    └─────────────────────┘
              │
              ▼
    ┌─────────────────────┐
    │ Phép tự động hoàn   │
    │ khi monthly refresh │
    └─────────────────────┘
```

Modify `_handle_leave_status()`:
```python
def _handle_leave_status(self, is_finalizing: bool) -> bool:
    """
    Return True if status was set due to leave.

    PRIORITY RULE: Attendance > Events > Proposals
    - If employee has attendance logs, their leave proposal is OVERRIDDEN
    - They should be calculated as normal working day
    - Clear absent_reason so leave balance is automatically refunded on monthly refresh
    """
    has_attendance = self.entry.start_time or self.entry.end_time

    # PRIORITY RULE: Attendance wins over leave proposal
    if has_attendance:
        # Clear absent_reason → leave will be automatically refunded
        # when EmployeeMonthlyTimesheet.refresh_for_employee_month() runs
        # because consumed_leave_days = COUNT(absent_reason=PAID_LEAVE)
        if self.entry.absent_reason in [
            TimesheetReason.PAID_LEAVE,
            TimesheetReason.UNPAID_LEAVE,
        ]:
            self.entry.absent_reason = None

        # Continue with NORMAL attendance calculation
        return False

    # Check if day has no work schedule (e.g., Sunday)
    if self._get_schedule_max_days() == 0:
        # No schedule = no working days regardless of leave
        self.entry.working_days = Decimal("0.00")
        self.entry.status = None
        return True

    # No attendance + has leave → apply leave logic
    leave_reasons = [
        TimesheetReason.PAID_LEAVE,
        TimesheetReason.UNPAID_LEAVE,
        TimesheetReason.MATERNITY_LEAVE,
    ]
    if self.entry.absent_reason in leave_reasons:
        if is_finalizing:
            self.entry.status = TimesheetStatus.ABSENT
        else:
            self.entry.status = None
        return True
    return False
```

**Lưu ý quan trọng:**
- KHÔNG cần LeaveRefundService riêng
- Chỉ cần xóa `absent_reason` → phép tự động được hoàn khi monthly refresh
- Flow đơn giản và tận dụng logic hiện có

#### Task 1.3: Fix Compensatory Day Working Days
**File:** `apps/hrm/services/timesheet_calculator.py`

Modify `compute_working_days()`:
```python
def compute_working_days(self, is_finalizing: bool = False) -> None:
    """Compute working_days according to business rules."""
    if not is_finalizing:
        self.entry.working_days = None
        return

    self.entry.working_days = Decimal("0.00")

    # NEW: Handle Holiday - always get full credit
    if self.entry.day_type == TimesheetDayType.HOLIDAY:
        self.entry.working_days = Decimal("1.00")
        return

    # Handle Absent
    if self.entry.status == TimesheetStatus.ABSENT:
        if self.entry.absent_reason == TimesheetReason.PAID_LEAVE:
            self.entry.working_days = Decimal("1.00")
        elif self.entry.day_type == TimesheetDayType.COMPENSATORY:
            # NEW: Absent on compensatory day = negative (debt)
            max_days = self._get_schedule_max_days()
            self.entry.working_days = -max_days
        return

    # ... rest of existing logic ...
```

#### Task 1.4: Fix Single Punch + Leave Combination
**File:** `apps/hrm/services/timesheet_calculator.py`

Ensure single punch takes precedence:
```python
def compute_status(self, is_finalizing: bool = False) -> None:
    """Compute status: ABSENT, SINGLE_PUNCH, ON_TIME, NOT_ON_TIME."""
    # ... existing setup ...

    # Single Punch should take precedence over leave
    if self._is_single_punch():
        self._handle_single_punch_status(is_finalizing)
        return

    # Then check leave
    if self._handle_leave_status(is_finalizing):
        return

    # ... rest of logic ...
```

#### Task 1.5: Fix Maternity Bonus Snapshot
**File:** `apps/hrm/services/timesheet_snapshot_service.py`

Verify `snapshot_allowed_late_minutes()` correctly sets reason:
```python
def snapshot_allowed_late_minutes(self, entry: TimeSheetEntry) -> None:
    # ... existing code ...

    for p in proposals:
        if p.proposal_type == ProposalType.POST_MATERNITY_BENEFITS:
            # VERIFY: This should set MATERNITY reason
            if allowed_minutes < 65:
                allowed_minutes = 65
                reason = AllowedLateMinutesReason.MATERNITY
            # BUG FIX: Even if already >= 65, still set reason
            else:
                reason = AllowedLateMinutesReason.MATERNITY
```

---

### Phase 2: Signal & Recalculation

#### Task 2.1: Add Signal for AttendanceExemption Delete
**File:** `apps/hrm/signals/exemption_triggers.py` (NEW)

```python
from django.db.models.signals import post_delete
from django.dispatch import receiver

from apps.hrm.models import AttendanceExemption, TimeSheetEntry
from apps.hrm.services.timesheet_calculator import TimesheetCalculator

@receiver(post_delete, sender=AttendanceExemption)
def recalculate_on_exemption_delete(sender, instance, **kwargs):
    """Recalculate timesheets after exemption is removed."""
    from datetime import date

    # Recalculate all entries from exemption effective_date onwards
    entries = TimeSheetEntry.objects.filter(
        employee_id=instance.employee_id,
        date__gte=instance.effective_date,
        date__lte=date.today(),
    )

    for entry in entries:
        entry.is_exempt = False  # Remove exemption flag
        calculator = TimesheetCalculator(entry)
        calculator.compute_all(is_finalizing=entry.date < date.today())
        entry.save()
```

#### Task 2.2: Add Signal for Contract Change
**File:** `apps/hrm/signals/contract_triggers.py` (NEW or UPDATE)

```python
@receiver(post_save, sender=Contract)
def recalculate_on_contract_change(sender, instance, **kwargs):
    """Recalculate timesheets when contract effective_date is in past."""
    from datetime import date

    if instance.effective_date < date.today():
        entries = TimeSheetEntry.objects.filter(
            employee_id=instance.employee_id,
            date__gte=instance.effective_date,
            date__lte=date.today(),
        )

        for entry in entries:
            snapshot_service = TimesheetSnapshotService()
            snapshot_service.snapshot_contract_info(entry)
            entry.save()
```

---

### Phase 3: Celery Task Fixes

#### Task 3.1: Review & Fix finalize_yesterday_timesheets
**File:** `apps/hrm/tasks/timesheet_triggers.py`

```python
@shared_task
def finalize_yesterday_timesheets():
    """Finalize all timesheet entries for yesterday."""
    from datetime import date, timedelta

    yesterday = date.today() - timedelta(days=1)

    # Get ALL active employees, not just those with entries
    from apps.hrm.models import Employee
    active_employees = Employee.objects.filter(
        status=Employee.Status.ACTIVE
    ).values_list('id', flat=True)

    for emp_id in active_employees:
        entry, created = TimeSheetEntry.objects.get_or_create(
            employee_id=emp_id,
            date=yesterday,
        )

        calculator = TimesheetCalculator(entry)
        calculator.compute_all(is_finalizing=True)
        entry.save()
```

---

## 📝 Test Cases

### Test Case Summary for QA/Tester

#### Bug Reproduction Tests (12 cases)

| # | Test ID | Mô tả | Preconditions | Steps | Expected Result | Priority |
|---|---------|-------|---------------|-------|-----------------|----------|
| 1 | TC-PR1-001 | NV nghỉ phép có lương nhưng vẫn chấm công | - NV có đề xuất PAID_LEAVE đã duyệt<br>- Ngày nghỉ = 10/01/2026 | 1. NV chấm công vào 08:00<br>2. NV chấm công ra 17:30<br>3. Kiểm tra TimeSheetEntry | - status = ON_TIME<br>- working_days = 1.0<br>- absent_reason = NULL<br>- Phép được hoàn tự động | 🔴 Critical |
| 2 | TC-PR1-002 | Ngày tương lai NV miễn chấm công | - NV thuộc diện miễn CC<br>- Entry cho ngày mai | 1. Xem TimeSheetEntry ngày mai<br>2. Kiểm tra working_days, status | - working_days = NULL<br>- status = NULL<br>- Chưa finalize | 🔴 Critical |
| 3 | TC-PR1-003 | Xóa NV khỏi danh sách miễn CC | - NV có AttendanceExemption từ 01/01<br>- Có entries từ 01/01-10/01 | 1. Xóa AttendanceExemption<br>2. Kiểm tra tất cả entries | - Entries được recalculate<br>- Ngày không CC → ABSENT<br>- working_days = 0 | 🟠 High |
| 4 | TC-PR1-004 | Ngày CN không có ca + duyệt đề xuất | - Ngày Chủ nhật (không có schedule)<br>- Có đề xuất PAID_LEAVE duyệt | 1. Kiểm tra TimeSheetEntry ngày CN | - working_days = 0<br>- status = NULL<br>- Không tính công | 🟠 High |
| 5 | TC-PR1-005 | Ngày làm bù mà vắng | - Ngày có day_type = COMPENSATORY<br>- NV không có log CC | 1. Finalize entry<br>2. Kiểm tra working_days | - status = ABSENT<br>- working_days = -1.0 (nợ công) | 🔴 Critical |
| 6 | TC-PR1-006 | Số ngày công ngày lễ | - Ngày có day_type = HOLIDAY<br>- NV không cần CC | 1. Kiểm tra TimeSheetEntry ngày lễ | - working_days = 1.0<br>- Hưởng nguyên lương | 🔴 Critical |
| 7 | TC-PR1-007 | Cập nhật trạng thái sang ngày mới | - NV ACTIVE không có entry ngày hôm qua<br>- Celery task chạy lúc 00:00 | 1. Chờ task chạy<br>2. Kiểm tra entry mới | - Entry được tạo mới<br>- status = ABSENT<br>- working_days = 0 | 🟠 High |
| 8 | TC-PR1-008 | 1 log CC + duyệt đề xuất nghỉ | - NV chỉ có 1 log CC (check-in)<br>- Có đề xuất PAID_LEAVE duyệt | 1. Finalize entry<br>2. Kiểm tra status | - status = SINGLE_PUNCH<br>- working_days = 0.5<br>- absent_reason = NULL | 🔴 Critical |
| 9 | TC-PR1-009 | Công sau duyệt hậu thai sản | - NV có đề xuất POST_MATERNITY duyệt<br>- Có đủ 2 log CC | 1. NV CC vào 08:30 (trễ 30p)<br>2. NV CC ra 17:30<br>3. Kiểm tra working_days | - working_days ≥ 0.875 + 0.125<br>- is_punished = FALSE<br>- Ân hạn 65 phút | 🟠 High |
| 10 | TC-PR1-010 | Công sau đổi HĐ retroactive | - NV có entries từ 01/01 (net=85%)<br>- Ngày 10/01 tạo HĐ mới effective 01/01 | 1. Tạo Contract mới<br>2. Kiểm tra entries từ 01/01 | - Tất cả entries được recalculate<br>- net_percentage = 100<br>- is_full_salary = TRUE | 🟠 High |
| **11** | **TC-PR1-011** | **[NEW] Nghỉ phép có lương → working_days** | - Đề xuất PAID_LEAVE đã duyệt<br>- Không có log CC | 1. Kiểm tra TimeSheetEntry | - **working_days = 1.0**<br>- absent_reason = PAID_LEAVE<br>- status = None | 🔴 **Critical** |
| **12** | **TC-PR1-012** | **[NEW] Số ngày công sau duyệt hậu thai sản** | - Đề xuất POST_MATERNITY duyệt<br>- Có entries trong kỳ | 1. Duyệt đề xuất<br>2. Kiểm tra entries | - working_days ≠ NULL<br>- allowed_late_reason = MATERNITY<br>- Entries recalculated | 🔴 **Critical** |

#### Happy Path Tests (5 cases)

| # | Test ID | Mô tả | Preconditions | Steps | Expected Result | Priority |
|---|---------|-------|---------------|-------|-----------------|----------|
| 11 | TC-PR1-011 | Đi làm đúng giờ, đủ ca | - Ngày làm việc bình thường (T2-T6)<br>- NV có schedule 2 ca | 1. CC vào 08:00<br>2. CC ra 17:30 | - status = ON_TIME<br>- working_days = 1.0<br>- is_punished = FALSE | 🟢 Normal |
| 12 | TC-PR1-012 | Thứ 7 làm nửa ngày | - Ngày thứ 7<br>- NV có schedule 1 ca sáng | 1. CC vào 08:00<br>2. CC ra 12:00 | - working_days = 0.5<br>- official_hours = 4.0 | 🟢 Normal |
| 13 | TC-PR1-013 | Nghỉ phép có lương, không CC | - Có đề xuất PAID_LEAVE duyệt<br>- Không có log CC | 1. Finalize entry | - status = ABSENT<br>- working_days = 1.0<br>- absent_reason = PAID_LEAVE | 🟢 Normal |
| 14 | TC-PR1-014 | NV miễn CC, ngày đã qua | - NV thuộc diện miễn CC<br>- Entry cho ngày hôm qua | 1. Finalize entry | - status = ON_TIME<br>- working_days = 1.0 | 🟢 Normal |
| 15 | TC-PR1-015 | Trễ trong ân hạn 5 phút | - Ngày làm việc bình thường | 1. CC vào 08:04<br>2. CC ra 17:30 | - late_minutes = 4<br>- is_punished = FALSE | 🟢 Normal |

#### Corner Case Tests (12 cases)

| # | Test ID | Mô tả | Preconditions | Steps | Expected Result | Priority |
|---|---------|-------|---------------|-------|-----------------|----------|
| 16 | TC-PR1-016 | CC lúc 00:00 (midnight) | - Entry ngày 10/01 | 1. CC vào 00:00<br>2. CC ra 08:00 | - Không crash<br>- official_hours tính đúng schedule | 🟡 Medium |
| 17 | TC-PR1-017 | end_time < start_time (overnight) | - Entry ngày 10/01 | 1. CC vào 22:00<br>2. CC ra 06:00 | - Không crash<br>- Handle gracefully | 🟡 Medium |
| 18 | TC-PR1-018 | Có cả leave + attendance | - Có đề xuất PAID_LEAVE<br>- Có log CC nửa ngày | 1. CC vào 08:00<br>2. CC ra 12:00 | - absent_reason = NULL<br>- working_days > 0<br>- Attendance wins | 🟠 High |
| 19 | TC-PR1-019 | Ngày lễ trùng CN | - Ngày 01/01 là CN và HOLIDAY | 1. Kiểm tra entry | - day_type = HOLIDAY<br>- working_days = 1.0 | 🟡 Medium |
| 20 | TC-PR1-020 | Ngày làm bù + đi làm đủ | - day_type = COMPENSATORY<br>- Có đủ CC | 1. CC vào 08:00<br>2. CC ra 17:30 | - compensation_value = 0<br>- Đã bù xong | 🟡 Medium |
| 21 | TC-PR1-021 | Trễ đúng 5 phút (boundary) | - Ngày làm việc bình thường | 1. CC vào 08:05<br>2. CC ra 17:30 | - late_minutes = 5<br>- is_punished = FALSE | 🟡 Medium |
| 22 | TC-PR1-022 | Trễ 6 phút (vượt ân hạn) | - Ngày làm việc bình thường | 1. CC vào 08:06<br>2. CC ra 17:30 | - late_minutes = 6<br>- is_punished = TRUE | 🟡 Medium |
| 23 | TC-PR1-023 | Entry trống hoàn toàn | - Entry mới tạo, không có data | 1. Finalize entry | - status = ABSENT<br>- working_days = 0 | 🟢 Normal |
| 24 | TC-PR1-024 | Hậu thai sản + single punch | - Có POST_MATERNITY duyệt<br>- Chỉ có 1 log CC | 1. CC vào 08:00 | - status = SINGLE_PUNCH<br>- working_days = 0.5<br>- Không có bonus | 🟠 High |
| 25 | TC-PR1-025 | Verify phép hoàn trong monthly | - 1 entry có CC + cleared reason<br>- 1 entry có PAID_LEAVE thực | 1. Refresh monthly timesheet | - consumed_leave_days = 1.0<br>- Chỉ count entry thực nghỉ | 🟠 High |
| 26 | TC-PR1-026 | Về sớm 10 phút | - Ngày làm việc bình thường | 1. CC vào 08:00<br>2. CC ra 17:20 | - early_minutes = 10<br>- is_punished = TRUE | 🟡 Medium |
| 27 | TC-PR1-027 | Cả trễ và về sớm | - Ngày làm việc bình thường | 1. CC vào 08:03<br>2. CC ra 17:28 | - late_minutes = 3<br>- early_minutes = 2<br>- is_punished = FALSE (tổng 5) | 🟡 Medium |

**Legend:**
- 🔴 Critical: Must pass before release
- 🟠 High: Important, blocks major features
- 🟡 Medium: Should pass, minor impact if fails
- 🟢 Normal: Nice to have, regression tests

---

### 1. Bug Reproduction Tests (10 reported issues)

#### Issue #1: 86ew4zetx - NV nghỉ hưởng lương nhưng vẫn chấm công

```python
def test_paid_leave_with_attendance_calculates_normally(self, employee):
    """
    BUG: NV được duyệt nghỉ phép có lương nhưng vẫn đi làm, hệ thống
         vẫn tính là nghỉ phép thay vì đi làm.

    Setup:
    - Employee có đề xuất PAID_LEAVE được duyệt cho ngày X
    - ProposalService đã set entry.absent_reason = PAID_LEAVE
    - Nhưng employee vẫn có log chấm công (start_time, end_time)

    Expected:
    - status = ON_TIME hoặc NOT_ON_TIME (tính như đi làm)
    - working_days > 0 (tính công bình thường)
    - absent_reason = None (xóa để hoàn phép tự động)
    """
    entry = TimeSheetEntry.objects.create(
        employee=employee,
        date=date(2026, 1, 10),
        start_time=time(8, 0),
        end_time=time(17, 30),
        absent_reason=TimesheetReason.PAID_LEAVE,
    )

    calculator = TimesheetCalculator(entry)
    calculator.compute_all(is_finalizing=True)

    assert entry.status == TimesheetStatus.ON_TIME
    assert entry.working_days == Decimal("1.00")
    assert entry.absent_reason is None  # Cleared for auto refund
```

#### Issue #2: 86ew50mhq - Ngày tương lai NV miễn chấm công

```python
def test_exempt_employee_future_date_no_finalization(self, employee):
    """
    BUG: NV miễn chấm công được tính đủ công cho ngày tương lai,
         dẫn đến hiển thị sai trên dashboard.

    Setup:
    - Employee thuộc diện miễn chấm công (is_exempt = True)
    - Entry cho ngày mai (future date)

    Expected:
    - working_days = None (chưa finalize)
    - status = None (chưa xác định)
    """
    tomorrow = date.today() + timedelta(days=1)
    entry = TimeSheetEntry.objects.create(
        employee=employee,
        date=tomorrow,
        is_exempt=True,
    )

    calculator = TimesheetCalculator(entry)
    calculator.compute_all(is_finalizing=False)

    assert entry.working_days is None
    assert entry.status is None
```

#### Issue #3: 86ew50tk2 - Xóa NV khỏi danh sách miễn chấm công

```python
def test_exemption_delete_triggers_recalculation(self, employee):
    """
    BUG: Khi xóa NV khỏi danh sách miễn CC, các ngày công cũ vẫn
         giữ nguyên giá trị như khi còn miễn CC.

    Setup:
    - Employee có AttendanceExemption từ ngày 1/1
    - Các entry từ 1/1 đến nay đều có is_exempt=True, working_days=1.0
    - Xóa AttendanceExemption

    Expected:
    - Signal trigger recalculate tất cả entries
    - Entries không có log CC → status = ABSENT, working_days = 0
    """
    # Create exemption and entries
    exemption = AttendanceExemption.objects.create(
        employee=employee,
        effective_date=date(2026, 1, 1),
    )

    entry = TimeSheetEntry.objects.create(
        employee=employee,
        date=date(2026, 1, 5),
        is_exempt=True,
        working_days=Decimal("1.00"),
        status=TimesheetStatus.ON_TIME,
    )

    # Delete exemption - should trigger signal
    exemption.delete()

    entry.refresh_from_db()
    assert entry.is_exempt is False
    assert entry.status == TimesheetStatus.ABSENT
    assert entry.working_days == Decimal("0.00")
```

#### Issue #4: 86ew54a72 - Ngày không có ca nhưng duyệt đề xuất

```python
def test_no_schedule_day_with_leave_proposal(self, employee):
    """
    BUG: Ngày CN không có ca làm việc, nhưng có đề xuất nghỉ phép
         được duyệt → hệ thống vẫn tính 1 ngày công.

    Setup:
    - Ngày Chủ nhật (không có work schedule)
    - Employee có đề xuất PAID_LEAVE được duyệt

    Expected:
    - working_days = 0 (không có ca = không tính công)
    - status = None
    """
    sunday = date(2026, 1, 12)  # A Sunday
    entry = TimeSheetEntry.objects.create(
        employee=employee,
        date=sunday,
        absent_reason=TimesheetReason.PAID_LEAVE,
    )
    # Mock: _get_schedule_max_days() returns 0 for Sunday

    calculator = TimesheetCalculator(entry)
    calculator.compute_all(is_finalizing=True)

    assert entry.working_days == Decimal("0.00")
    assert entry.status is None
```

#### Issue #5: 86ew54m1w - Số ngày công ngày làm bù

```python
def test_compensatory_day_absent_negative_working_days(self, employee):
    """
    BUG: Ngày làm bù mà NV vắng, working_days = 0 thay vì giá trị âm
         (nợ công).

    Setup:
    - Ngày làm bù (day_type = COMPENSATORY)
    - Employee không có log chấm công (vắng)

    Expected:
    - working_days = -1.0 hoặc -0.5 (nợ công)
    - status = ABSENT
    """
    entry = TimeSheetEntry.objects.create(
        employee=employee,
        date=date(2026, 1, 11),  # Saturday - compensatory
        day_type=TimesheetDayType.COMPENSATORY,
        start_time=None,
        end_time=None,
    )

    calculator = TimesheetCalculator(entry)
    calculator.compute_all(is_finalizing=True)

    assert entry.status == TimesheetStatus.ABSENT
    assert entry.working_days == Decimal("-1.00")  # Debt
```

#### Issue #6: 86ew56gt2 - Số ngày công ngày lễ

```python
def test_holiday_full_working_days(self, employee):
    """
    BUG: Ngày lễ không hiển thị giá trị working_days (None),
         làm tổng công tháng bị thiếu.

    Setup:
    - Ngày lễ (day_type = HOLIDAY)
    - NV không cần chấm công

    Expected:
    - working_days = 1.0 (hưởng nguyên lương)
    - status = ON_TIME hoặc None
    """
    entry = TimeSheetEntry.objects.create(
        employee=employee,
        date=date(2026, 1, 1),  # New Year - Holiday
        day_type=TimesheetDayType.HOLIDAY,
    )

    calculator = TimesheetCalculator(entry)
    calculator.compute_all(is_finalizing=True)

    assert entry.working_days == Decimal("1.00")
```

#### Issue #7: 86ew5cxen - Cập nhật trạng thái sang ngày mới

```python
def test_finalize_yesterday_creates_missing_entries(self):
    """
    BUG: Một số NV không được update trạng thái "Vắng" khi sang ngày mới,
         do celery task bỏ sót employees chưa có entry.

    Setup:
    - Employee ACTIVE nhưng chưa có TimeSheetEntry cho ngày hôm qua
    - Celery task finalize_yesterday_timesheets chạy

    Expected:
    - Entry được tạo mới cho employee
    - status = ABSENT (không có log CC)
    - working_days = 0
    """
    # Employee without entry for yesterday
    employee = Employee.objects.create(status=Employee.Status.ACTIVE)
    yesterday = date.today() - timedelta(days=1)

    assert not TimeSheetEntry.objects.filter(employee=employee, date=yesterday).exists()

    # Run task
    finalize_yesterday_timesheets()

    entry = TimeSheetEntry.objects.get(employee=employee, date=yesterday)
    assert entry.status == TimesheetStatus.ABSENT
    assert entry.working_days == Decimal("0.00")
```

#### Issue #8: 86ew60rzf - Trạng thái 1 log + duyệt đề xuất

**Clarification:**
- **Các đề xuất ảnh hưởng:** Miễn trừ trễ, Chế độ làm việc hậu thai sản, Nghỉ thai sản, Nghỉ không lương, Nghỉ có lương
- **Rule ưu tiên:** `Attendance > Events > Proposals` (Thấp → Cao)
- Khi có 1 log chấm công + đề xuất được duyệt → **tính như ngày không có đề xuất**

```python
def test_single_punch_with_leave_shows_single_punch_status(self, employee):
    """
    BUG: Có 1 log CC + được duyệt đề xuất → trạng thái bị set là ABSENT
         thay vì SINGLE_PUNCH.

    Clarification:
    - Các đề xuất ảnh hưởng: Miễn trừ trễ, Hậu thai sản, Nghỉ thai sản,
      Nghỉ không lương, Nghỉ có lương
    - Rule: Attendance > Events > Proposals (có log CC thì ưu tiên attendance)

    Setup:
    - Employee có 1 log chấm công (chỉ check-in hoặc check-out)
    - Có đề xuất nghỉ phép được duyệt (1 trong 5 loại trên)

    Expected (giống như ngày không có đề xuất):
    - status = SINGLE_PUNCH (ưu tiên attendance)
    - working_days = 0.5 (half day)
    - absent_reason = None (clear leave vì có attendance)
    """
    entry = TimeSheetEntry.objects.create(
        employee=employee,
        date=date(2026, 1, 10),
        start_time=time(8, 0),
        end_time=None,  # Only check-in
        absent_reason=TimesheetReason.PAID_LEAVE,
    )

    calculator = TimesheetCalculator(entry)
    calculator.compute_all(is_finalizing=True)

    assert entry.status == TimesheetStatus.SINGLE_PUNCH
    assert entry.working_days == Decimal("0.50")
    assert entry.absent_reason is None
```

#### Issue #9: 86ew61yj8 - Công sau duyệt hậu thai sản

```python
def test_maternity_bonus_applied_correctly(self, employee):
    """
    BUG: Bonus 1 giờ (0.125 công) không được cộng cho NV hậu thai sản,
         dù đã có đề xuất POST_MATERNITY_BENEFITS được duyệt.

    Setup:
    - Employee có đề xuất POST_MATERNITY_BENEFITS được duyệt
    - allowed_late_minutes_reason = MATERNITY
    - Có đủ 2 log chấm công

    Expected:
    - working_days được cộng thêm 0.125
    - Ân hạn 65 phút được áp dụng (is_punished = False nếu trễ < 65p)
    """
    entry = TimeSheetEntry.objects.create(
        employee=employee,
        date=date(2026, 1, 10),
        start_time=time(8, 30),  # 30 phút trễ
        end_time=time(17, 30),
        allowed_late_minutes=65,
        allowed_late_minutes_reason=AllowedLateMinutesReason.MATERNITY,
    )

    calculator = TimesheetCalculator(entry)
    calculator.compute_all(is_finalizing=True)

    # Should get maternity bonus
    assert entry.working_days >= Decimal("0.875") + Decimal("0.125")
    assert entry.is_punished is False  # 30 < 65
```

#### Issue #10: 86ew614qt - Công thử việc/chính thức sau đổi HĐ

```python
def test_contract_change_retroactive_recalculation(self, employee):
    """
    BUG: Khi ban hành HĐ mới với ngày hiệu lực trong quá khứ,
         các entry cũ không được recalculate (net_percentage sai).

    Setup:
    - Employee có entries từ 1/1 với net_percentage = 85 (thử việc)
    - Ngày 10/1 ban hành HĐ chính thức, effective_date = 1/1

    Expected:
    - Signal trigger recalculate entries từ 1/1
    - Tất cả entries từ 1/1 có net_percentage = 100
    """
    # Create entries with probation contract
    for day in range(1, 10):
        TimeSheetEntry.objects.create(
            employee=employee,
            date=date(2026, 1, day),
            net_percentage=85,
            is_full_salary=False,
        )

    # Create new contract with retroactive effective_date
    contract = Contract.objects.create(
        employee=employee,
        effective_date=date(2026, 1, 1),
        net_percentage=100,
    )

    # Signal should recalculate
    entries = TimeSheetEntry.objects.filter(
        employee=employee,
        date__gte=date(2026, 1, 1),
    )

    for entry in entries:
        assert entry.net_percentage == 100
        assert entry.is_full_salary is True
```

#### Issue #11: 86evyq66n - Nghỉ phép có lương → working_days sai (NEW)

```python
def test_paid_leave_approved_working_days_equals_max(self, employee):
    """
    BUG: Sau khi duyệt đề xuất nghỉ phép có lương, working_days không được set = max.

    Root Cause:
    - _execute_leave_proposal() set status = None
    - compute_working_days() check status == ABSENT
    - MISMATCH → working_days không đúng

    Setup:
    - Employee có đề xuất PAID_LEAVE được duyệt
    - Entry có absent_reason = PAID_LEAVE
    - Không có log chấm công

    Expected:
    - working_days = 1.00 (giá trị max cho ngày làm việc có lương)
    - status = None hoặc ABSENT
    """
    entry = TimeSheetEntry.objects.create(
        employee=employee,
        date=date(2026, 1, 10),
        absent_reason=TimesheetReason.PAID_LEAVE,
        status=None,  # Set by _execute_leave_proposal
        start_time=None,
        end_time=None,
    )

    calculator = TimesheetCalculator(entry)
    calculator.compute_all(is_finalizing=True)

    # Nghỉ phép có lương → công = max
    assert entry.working_days == Decimal("1.00")


def test_unpaid_leave_approved_working_days_equals_zero(self, employee):
    """
    Verify nghỉ phép KHÔNG lương → working_days = 0
    """
    entry = TimeSheetEntry.objects.create(
        employee=employee,
        date=date(2026, 1, 10),
        absent_reason=TimesheetReason.UNPAID_LEAVE,
        status=None,
        start_time=None,
        end_time=None,
    )

    calculator = TimesheetCalculator(entry)
    calculator.compute_all(is_finalizing=True)

    # Nghỉ không lương → công = 0
    assert entry.working_days == Decimal("0.00")
```

#### Issue #12: 86ew5yu1x - Số ngày công rỗng sau duyệt hậu thai sản (NEW)

```python
def test_post_maternity_approval_recalculates_entries(self, employee):
    """
    BUG: Sau khi duyệt đề xuất hậu thai sản, working_days hiển thị rỗng.

    Root Cause:
    - POST_MATERNITY_BENEFITS không có handler trong ProposalService
    - TimeSheetEntry không được recalculate sau khi duyệt

    Setup:
    - Employee có đề xuất POST_MATERNITY_BENEFITS được duyệt
    - Có entries trong khoảng thời gian hậu thai sản

    Expected:
    - allowed_late_minutes_reason = MATERNITY
    - working_days được recalculate
    - Entries có maternity bonus nếu đủ điều kiện
    """
    # Create proposal
    proposal = Proposal.objects.create(
        created_by=employee,
        proposal_type=ProposalType.POST_MATERNITY_BENEFITS,
        proposal_status=ProposalStatus.APPROVED,
        post_maternity_benefits_start_date=date(2026, 1, 1),
        post_maternity_benefits_end_date=date(2026, 3, 31),
    )

    # Create entry with attendance
    entry = TimeSheetEntry.objects.create(
        employee=employee,
        date=date(2026, 1, 10),
        start_time=time(8, 30),  # 30 phút trễ
        end_time=time(17, 30),
    )

    # Execute proposal (this should recalculate entries)
    ProposalService.execute_approved_proposal(proposal)

    entry.refresh_from_db()

    # Verify entry has maternity benefits applied
    assert entry.allowed_late_minutes_reason == AllowedLateMinutesReason.MATERNITY
    assert entry.working_days is not None  # Not empty!
    assert entry.working_days >= Decimal("1.00")  # With maternity bonus
    assert entry.is_punished is False  # 30 < 65 minute grace
```

---

### 2. Happy Path Tests

```python
@pytest.mark.django_db
class TestHappyPath:
    """Normal flow tests - verify basic functionality works correctly."""

    def test_normal_working_day_on_time(self, employee):
        """NV chấm công đúng giờ, đủ ca → full working day."""
        entry = TimeSheetEntry.objects.create(
            employee=employee,
            date=date(2026, 1, 10),  # Friday
            start_time=time(8, 0),
            end_time=time(17, 30),
        )

        calculator = TimesheetCalculator(entry)
        calculator.compute_all(is_finalizing=True)

        assert entry.status == TimesheetStatus.ON_TIME
        assert entry.working_days == Decimal("1.00")
        assert entry.official_hours == Decimal("8.00")
        assert entry.is_punished is False

    def test_half_day_saturday(self, employee):
        """Thứ 7 chỉ làm sáng → 0.5 working day."""
        entry = TimeSheetEntry.objects.create(
            employee=employee,
            date=date(2026, 1, 11),  # Saturday
            start_time=time(8, 0),
            end_time=time(12, 0),
        )

        calculator = TimesheetCalculator(entry)
        calculator.compute_all(is_finalizing=True)

        assert entry.working_days == Decimal("0.50")
        assert entry.official_hours == Decimal("4.00")

    def test_paid_leave_no_attendance(self, employee):
        """Nghỉ phép có lương, không có CC → ABSENT với full day."""
        entry = TimeSheetEntry.objects.create(
            employee=employee,
            date=date(2026, 1, 10),
            absent_reason=TimesheetReason.PAID_LEAVE,
        )

        calculator = TimesheetCalculator(entry)
        calculator.compute_all(is_finalizing=True)

        assert entry.status == TimesheetStatus.ABSENT
        assert entry.working_days == Decimal("1.00")

    def test_exempt_employee_past_date(self, employee):
        """NV miễn CC, ngày đã qua → full working day."""
        yesterday = date.today() - timedelta(days=1)
        entry = TimeSheetEntry.objects.create(
            employee=employee,
            date=yesterday,
            is_exempt=True,
        )

        calculator = TimesheetCalculator(entry)
        calculator.compute_all(is_finalizing=True)

        assert entry.status == TimesheetStatus.ON_TIME
        assert entry.working_days == Decimal("1.00")

    def test_late_within_grace_period(self, employee):
        """Trễ trong ân hạn 5 phút → không bị phạt."""
        entry = TimeSheetEntry.objects.create(
            employee=employee,
            date=date(2026, 1, 10),
            start_time=time(8, 4),  # 4 minutes late
            end_time=time(17, 30),
        )

        calculator = TimesheetCalculator(entry)
        calculator.compute_all(is_finalizing=True)

        assert entry.late_minutes == 4
        assert entry.is_punished is False  # Within 5-min grace
```

---

### 3. Corner Case Tests

```python
@pytest.mark.django_db
class TestCornerCases:
    """Edge cases and boundary conditions."""

    def test_attendance_at_midnight(self, employee):
        """CC lúc 00:00 → vẫn tính đúng ngày."""
        entry = TimeSheetEntry.objects.create(
            employee=employee,
            date=date(2026, 1, 10),
            start_time=time(0, 0),  # Midnight
            end_time=time(8, 0),
        )

        calculator = TimesheetCalculator(entry)
        calculator.compute_all(is_finalizing=True)

        # Should not crash, but likely 0 official hours (outside schedule)
        assert entry.official_hours is not None

    def test_end_time_before_start_time(self, employee):
        """end_time < start_time (overnight?) → handle gracefully."""
        entry = TimeSheetEntry.objects.create(
            employee=employee,
            date=date(2026, 1, 10),
            start_time=time(22, 0),
            end_time=time(6, 0),  # Next day
        )

        calculator = TimesheetCalculator(entry)
        calculator.compute_all(is_finalizing=True)

        # Should not crash
        assert entry.status is not None

    def test_multiple_leave_types_same_day(self, employee):
        """Có cả PAID_LEAVE và attendance → attendance wins."""
        entry = TimeSheetEntry.objects.create(
            employee=employee,
            date=date(2026, 1, 10),
            start_time=time(8, 0),
            end_time=time(12, 0),  # Half day
            absent_reason=TimesheetReason.PAID_LEAVE,
        )

        calculator = TimesheetCalculator(entry)
        calculator.compute_all(is_finalizing=True)

        assert entry.absent_reason is None  # Cleared
        assert entry.working_days > 0

    def test_holiday_falls_on_sunday(self, employee):
        """Ngày lễ trùng CN → day_type vẫn là HOLIDAY, working_days=1."""
        entry = TimeSheetEntry.objects.create(
            employee=employee,
            date=date(2026, 1, 1),  # Assume it's Sunday and Holiday
            day_type=TimesheetDayType.HOLIDAY,
        )

        calculator = TimesheetCalculator(entry)
        calculator.compute_all(is_finalizing=True)

        assert entry.working_days == Decimal("1.00")

    def test_compensatory_day_with_full_attendance(self, employee):
        """Ngày làm bù + đi làm đủ → working_days = 0 (đã bù xong)."""
        entry = TimeSheetEntry.objects.create(
            employee=employee,
            date=date(2026, 1, 11),
            day_type=TimesheetDayType.COMPENSATORY,
            start_time=time(8, 0),
            end_time=time(17, 30),
        )

        calculator = TimesheetCalculator(entry)
        calculator.compute_all(is_finalizing=True)

        # compensation_value = actual - expected = 1.0 - 1.0 = 0
        assert entry.compensation_value == Decimal("0.00")

    def test_exact_grace_period_boundary(self, employee):
        """Trễ đúng 5 phút → không phạt (boundary)."""
        entry = TimeSheetEntry.objects.create(
            employee=employee,
            date=date(2026, 1, 10),
            start_time=time(8, 5),  # Exactly 5 minutes
            end_time=time(17, 30),
        )

        calculator = TimesheetCalculator(entry)
        calculator.compute_all(is_finalizing=True)

        assert entry.late_minutes == 5
        assert entry.is_punished is False  # 5 <= 5, not punished

    def test_one_minute_over_grace_period(self, employee):
        """Trễ 6 phút → bị phạt (vượt ân hạn)."""
        entry = TimeSheetEntry.objects.create(
            employee=employee,
            date=date(2026, 1, 10),
            start_time=time(8, 6),  # 6 minutes late
            end_time=time(17, 30),
        )

        calculator = TimesheetCalculator(entry)
        calculator.compute_all(is_finalizing=True)

        assert entry.late_minutes == 6
        assert entry.is_punished is True  # 6 > 5

    def test_entry_with_no_data(self, employee):
        """Entry trống hoàn toàn → ABSENT."""
        entry = TimeSheetEntry.objects.create(
            employee=employee,
            date=date(2026, 1, 10),
        )

        calculator = TimesheetCalculator(entry)
        calculator.compute_all(is_finalizing=True)

        assert entry.status == TimesheetStatus.ABSENT
        assert entry.working_days == Decimal("0.00")

    def test_maternity_with_single_punch(self, employee):
        """Hậu thai sản + single punch → không được bonus."""
        entry = TimeSheetEntry.objects.create(
            employee=employee,
            date=date(2026, 1, 10),
            start_time=time(8, 0),
            end_time=None,  # Single punch
            allowed_late_minutes_reason=AllowedLateMinutesReason.MATERNITY,
        )

        calculator = TimesheetCalculator(entry)
        calculator.compute_all(is_finalizing=True)

        # Single punch = half day, no maternity bonus (requires 2 punches)
        assert entry.status == TimesheetStatus.SINGLE_PUNCH
        assert entry.working_days == Decimal("0.50")

    def test_leave_refund_reflected_in_monthly(self, employee):
        """Verify phép được hoàn khi monthly refresh."""
        today = date.today()

        # Entry had leave but attended
        entry = TimeSheetEntry.objects.create(
            employee=employee,
            date=today,
            start_time=time(8, 0),
            end_time=time(17, 30),
            absent_reason=None,  # Already cleared
        )

        # Another entry with actual leave
        leave_entry = TimeSheetEntry.objects.create(
            employee=employee,
            date=today - timedelta(days=1),
            absent_reason=TimesheetReason.PAID_LEAVE,
        )

        monthly = EmployeeMonthlyTimesheet.refresh_for_employee_month(
            employee.id, today.year, today.month
        )

        # Only the actual leave day should be counted
        assert monthly.consumed_leave_days == Decimal("1.00")
```

---

## 📁 Files to Modify

| File | Changes |
|------|---------|
| `apps/hrm/services/timesheet_calculator.py` | Core logic fixes (Tasks 1.1-1.4), Priority Rule + auto leave refund |
| `apps/hrm/services/timesheet_snapshot_service.py` | Maternity bonus fix (Task 1.5) |
| `apps/hrm/signals/exemption_triggers.py` | **NEW**: Recalculate on exemption delete |
| `apps/hrm/signals/contract_triggers.py` | NEW/UPDATE: Recalculate on contract change |
| `apps/hrm/tasks/timesheet_triggers.py` | Fix finalize task (Task 3.1) |
| `apps/hrm/apps.py` | Register new signals |
| `docs/TÀI LIỆU QUY TẮC NGHIỆP VỤ_ TÍNH TOÁN VÀ LƯU TRỮ NGÀY CÔNG.md` | **UPDATE**: Cập nhật Priority Rule & logic hoàn phép |

---

## 📚 Phase 4: Documentation Update

### Task 4.1: Update Business Rules Document
**File:** `docs/TÀI LIỆU QUY TẮC NGHIỆP VỤ_ TÍNH TOÁN VÀ LƯU TRỮ NGÀY CÔNG.md`

**Sections cần cập nhật:**

#### 1. Thêm mục "Thứ tự ưu tiên dữ liệu" (Section 5)

Cập nhật Ma Trận Ưu Tiên để làm rõ:

```markdown
## 5. Thứ Tự Ưu Tiên Dữ Liệu (Priority Rule)

### 5.1. Nguyên tắc chung
```
Đề xuất (Proposal) < Sự kiện (Events) < Lịch sử chấm công (Attendance)
```

| Layer | Ví dụ | Ý nghĩa |
|-------|-------|---------|
| Đề xuất | Xin nghỉ phép, WFH, OT | Kế hoạch - có thể thay đổi |
| Sự kiện | Thay đổi HĐ, miễn CC | Thực tế đã xảy ra |
| Chấm công | Log check-in/out | Bằng chứng đi làm |

### 5.2. Quy tắc xử lý xung đột

| Trường hợp | Xử lý | Kết quả |
|------------|-------|---------|
| Nghỉ phép + Có chấm công | Attendance wins | Tính công bình thường |
| Nghỉ phép CÓ LƯƠNG + Có CC | Clear absent_reason | Phép tự động hoàn |
| Nghỉ phép KHÔNG lương + Có CC | Clear absent_reason | Tính công bình thường |
```

#### 2. Cập nhật dòng trong bảng Section 5 hiện tại

Thay đổi dòng:
```
| Đi làm trùng ngày Phép | Nghỉ phép | `paid_leave_hours` được ưu tiên... |
```

Thành:
```
| Đi làm trùng ngày Phép | Chấm công | Tính công bình thường, xóa absent_reason, phép tự động hoàn |
```

#### 3. Thêm giải thích về Leave Balance Flow

```markdown
### 5.3. Cơ chế hoàn phép tự động

Khi nhân viên có đề xuất nghỉ phép được duyệt nhưng vẫn đi làm:

1. `TimesheetCalculator` phát hiện có attendance logs
2. Xóa `absent_reason` khỏi entry
3. Khi `EmployeeMonthlyTimesheet.refresh_for_employee_month()` chạy:
   - `consumed_leave_days` = COUNT(absent_reason = PAID_LEAVE)
   - Entry không còn PAID_LEAVE → không bị count
   - `remaining_leave_days` tự động tăng
4. **Kết quả:** Phép được hoàn mà không cần xử lý riêng
```

---

## 🚀 Deployment Steps

1. **Database:** No migrations required
2. **Code:** Deploy all changes
3. **Post-deploy script:** Run one-time recalculation for affected entries

```python
# management command: recalculate_timesheets
from datetime import date, timedelta

# Recalculate last 30 days for all employees
start_date = date.today() - timedelta(days=30)
entries = TimeSheetEntry.objects.filter(date__gte=start_date)

for entry in entries:
    calculator = TimesheetCalculator(entry)
    calculator.compute_all(is_finalizing=entry.date < date.today())
    entry.save()
```

---

## ⚠️ Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Performance khi recalculate nhiều entries | Batch processing với chunk size 100 |
| Side effects với payroll đã tính | Chỉ recalculate entries chưa count_for_payroll |
| Signal loops | Add flag `_skip_signal` để tránh recursive |

---

*Created: 2026-01-13*
*Author: GitHub Copilot*
*Status: Draft*
