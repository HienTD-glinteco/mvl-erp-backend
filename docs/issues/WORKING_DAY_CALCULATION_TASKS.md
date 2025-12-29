# Working Day Calculation Implementation Tasks

**Based on:**
- `docs/WORKING_DAY_CALCULATION_REVIEW_PLAN.md`
- `docs/TÀI LIỆU QUY TẮC NGHIỆP VỤ_ TÍNH TOÁN VÀ LƯU TRỮ NGÀY CÔNG.md`

**Goal:** Refactor timesheet calculation to ensure accuracy, proper snapshotting, and SRS compliance.

---

## Phase 1: Database Schema Updates

### Task 1.1: Update TimeSheetEntry Model (Snapshot Fields)
**Objective:** Add fields to `TimeSheetEntry` to store snapshot data (contract, wage rate, etc.) at the time of creation.
**File:** `apps/hrm/models/timesheet.py`
**Instructions:**
1.  Add `contract` field: `ForeignKey("Contract", null=True, on_delete=models.SET_NULL, ...)`
2.  Add `wage_rate` field: `IntegerField(default=100, ...)` (Snapshot of Contract.wage_rate)
3.  Add `is_exempt` field: `BooleanField(default=False, ...)` (For exemption cases)
4.  Ensure `day_type` field covers: `official`, `holiday`, `compensatory`.
5.  Generate and run migration: `python manage.py makemigrations` -> `python manage.py migrate`.

### Task 1.2: Update TimeSheetEntry Model (Calculated Metrics)
**Objective:** Add fields to `TimeSheetEntry` to store detailed calculated metrics (OT breakdown, penalties).
**File:** `apps/hrm/models/timesheet.py`
**Instructions:**
1.  Add `compensation_value`: `DecimalField(..., default=0)` (Stores diff for compensatory days)
2.  Add `paid_leave_hours`: `DecimalField(..., default=0)`
3.  Add `ot_tc1_hours`: `DecimalField(..., default=0)` (Weekday OT)
4.  Add `ot_tc2_hours`: `DecimalField(..., default=0)` (Weekend OT)
5.  Add `ot_tc3_hours`: `DecimalField(..., default=0)` (Holiday OT)
6.  Add `ot_start_time`: `DateTimeField(null=True, blank=True)` (Actual OT start)
7.  Add `ot_end_time`: `DateTimeField(null=True, blank=True)` (Actual OT end)
8.  Add `late_minutes`: `IntegerField(default=0)`
9.  Add `early_minutes`: `IntegerField(default=0)`
10. Add `is_punished`: `BooleanField(default=False)`
11. Generate and run migration.

### Task 1.3: Update EmployeeMonthlyTimesheet Model
**Objective:** Update monthly aggregate model to reflect new OT breakdown and penalty tracking.
**File:** `apps/hrm/models/monthly_timesheet.py`
**Instructions:**
1.  **Rename** fields using `RenameField` in migration (preserve data):
    *   `saturday_in_week_overtime_hours` -> `tc1_overtime_hours`
    *   `sunday_overtime_hours` -> `tc2_overtime_hours`
    *   `holiday_overtime_hours` -> `tc3_overtime_hours`
2.  **Add** new fields:
    *   `late_coming_minutes`: `IntegerField/DecimalField`
    *   `early_leaving_minutes`: `IntegerField/DecimalField`
    *   `total_penalty_count`: `IntegerField`
3.  Generate migration. Ensure migration file uses `migrations.RenameField`.

---

## Phase 2: Architecture & Logic Refactoring

### Task 2.1: Implement TimesheetSnapshotService
**Objective:** Create a service responsible for populating "Snapshot" fields on `TimeSheetEntry` creation.
**File:** `apps/hrm/services/timesheet_snapshot_service.py` (Create new)
**Instructions:**
1.  Create class `TimesheetSnapshotService`.
2.  Method `snapshot_data(entry)`:
    *   Determine `day_type` (Check `Holiday` and `CompensatoryWorkday` models).
    *   Fetch active `Contract` for `entry.employee` and `entry.date`.
    *   Populate `entry.contract`, `entry.wage_rate`, `entry.is_full_salary`, `entry.day_type`.
    *   Save entry.
3.  **Trigger:** Integrate this service into the `TimeSheetEntry` creation flow (e.g., in `TimeSheetEntry.save()` if creating, or in the batch job `apps/hrm/tasks/timesheets.py`).

### Task 2.2: Rewrite TimesheetCalculator (Skeleton & Hours)
**Objective:** Rewrite `TimesheetCalculator` to use the new Snapshot fields and standardize logic.
**File:** `apps/hrm/services/timesheet_calculator.py` (Rewrite)
**Instructions:**
1.  **Wipe existing logic** (backup if needed) and start fresh.
2.  **Input:** `entry` (Assume snapshot data is already present).
3.  Implement `calculate_hours()`:
    *   Get `WorkSchedule` (cached by weekday).
    *   Calculate `morning_hours`, `afternoon_hours` based on `check_in`/`check_out` intersection with Schedule.
    *   Do **NOT** calculate OT here yet (separate step).

### Task 2.3: Implement TimesheetCalculator (Overtime)
**Objective:** Add OT calculation logic with proper classification.
**File:** `apps/hrm/services/timesheet_calculator.py`
**Instructions:**
1.  Implement `calculate_overtime()`:
    *   Fetch **Approved** `Proposal` (OT type) for the employee/date.
    *   Calculate intersection: `[check_in, check_out]` AND `[proposal_start, proposal_end]`.
    *   Set `entry.ot_start_time`, `entry.ot_end_time` based on intersection.
    *   Calculate `total_ot_hours`.
2.  Implement `classify_overtime()`:
    *   If `entry.day_type == 'holiday'` -> Assign to `ot_tc3_hours`.
    *   Else if `entry.day_type == 'official'` (and it's Sunday/Weekend based on Schedule) -> Assign to `ot_tc2_hours`.
    *   Else -> Assign to `ot_tc1_hours`.

### Task 2.4: Implement TimesheetCalculator (Penalties)
**Objective:** Calculate late/early minutes and punishment flag.
**File:** `apps/hrm/services/timesheet_calculator.py`
**Instructions:**
1.  Implement `calculate_penalties()`:
    *   Compare `check_in` vs `Schedule.morning_start`.
    *   Compare `check_out` vs `Schedule.afternoon_end`.
    *   Sum `late_minutes` + `early_minutes`.
    *   Determine `grace_period`:
        *   Default: 5 mins.
        *   If `Post-Maternity` proposal active: 65 mins.
    *   Set `entry.is_punished = (late + early) > grace_period`.

### Task 2.5: Implement TimesheetCalculator (Status & Single Punch)
**Objective:** Set final status and handle single check-in hard rules.
**File:** `apps/hrm/services/timesheet_calculator.py`
**Instructions:**
1.  Implement `compute_status()`:
    *   If 1 log -> `SINGLE_PUNCH`.
        *   **Hard Rule:** `working_days` = Max / 2. `overtime` = 0.
    *   If 2 logs -> `ON_TIME` or `NOT_ON_TIME` (based on `is_punished`).
    *   If No logs -> `ABSENT` (or empty if preview).
    *   *Note:* Ensure this logic aligns with the "Real-time" vs "Finalize" distinction.

---

## Phase 3: Signals & Triggers

### Task 3.1: Implement Reactive Signals
**Objective:** Trigger updates when foundational data changes.
**File:** `apps/hrm/signals/timesheet_triggers.py` (New or update existing)
**Instructions:**
1.  **WorkSchedule Change:** `post_save` on `WorkSchedule` -> Find affected employees -> Trigger Recalculate for future/current dates.
2.  **Holiday/Compensatory Change:** `post_save` -> Trigger `SnapshotService` (update `day_type`) -> Trigger Recalculate for affected dates.
3.  **Contract Change:** `post_save` -> Trigger `SnapshotService` (update `contract`, `wage_rate`) for affected dates.
4.  **Proposal Change:** `post_save` (Approved/Revoked) -> Trigger Recalculate.

---

## Phase 4: Aggregation & Finalization

### Task 4.1: Update Monthly Aggregation
**Objective:** Map new fields to monthly summary.
**File:** `apps/hrm/models/monthly_timesheet.py`
**Instructions:**
1.  Update `compute_aggregates`:
    *   Sum `ot_tc1_hours` -> `tc1_overtime_hours`.
    *   Sum `ot_tc2_hours` -> `tc2_overtime_hours`.
    *   Sum `ot_tc3_hours` -> `tc3_overtime_hours`.
    *   Sum `late_minutes`, `early_minutes`.
    *   Count `is_punished` -> `total_penalty_count`.

### Task 4.2: Implement End-of-Day Status Task
**Objective:** Create the 17:30 daily task to finalize statuses.
**File:** `apps/hrm/tasks/timesheets.py`
**Instructions:**
1.  Create celery task `finalize_daily_timesheets`.
2.  Schedule: 17:30 daily.
3.  Logic:
    *   Query all `TimeSheetEntry` for today.
    *   If `check_in` & `check_out` NULL -> Set `status = ABSENT`.
    *   If only 1 log -> Set `status = SINGLE_PUNCH`, `working_days = 0.5/0.25`, `overtime = 0`.
    *   Save entries.

---

## Phase 5: Testing

### Task 5.1: Unit Tests
**Objective:** Verify all scenarios.
**File:** `apps/hrm/tests/test_timesheet_calculator_v2.py`
**Instructions:**
1.  Test Single Punch (Hard Rule).
2.  Test Penalty (Grace period 5m vs 65m).
3.  Test OT Classification (TC1/2/3).
4.  Test Snapshotting (Change contract -> Recalculate).
