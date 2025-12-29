# Master Plan: Timesheet Business Logic Alignment

Based on `docs/TÀI LIỆU QUY TẮC NGHIỆP VỤ_ TÍNH TOÁN VÀ LƯU TRỮ NGÀY CÔNG.md`.

## Step 1: Refactor `TimeSheetEntry` Model
**File:** `apps/hrm/models/timesheet.py`
**Goal:** Add missing snapshot fields to store static values at calculation time.

### Changes
*   **Add New Fields:**
    *   `contract_id` (Integer/FK): Snapshot of the active contract ID.
    *   `wage_rate` (Integer): Snapshot of salary percentage (85 or 100).
    *   `compensation_value` (Decimal): For compensatory days logic (Real Working Days - Target).
    *   `paid_leave_hours` (Decimal): Total approved paid leave hours (snapshot).
    *   `ot_tc1_hours` (Decimal): Overtime hours with factor 1.5 (Weekdays).
    *   `ot_tc2_hours` (Decimal): Overtime hours with factor 2.0 (Sundays).
    *   `ot_tc3_hours` (Decimal): Overtime hours with factor 3.0 (Holidays).
    *   `late_minutes` (Integer): Raw late minutes (no grace period applied).
    *   `early_minutes` (Integer): Raw early leave minutes (no grace period applied).
    *   `is_punished` (Boolean): Penalty flag. True if `(late + early) > grace_period`.
    *   `is_exempt` (Boolean): True if employee is exempt from check-in (e.g., BoD).

## Step 2: Refactor `EmployeeMonthlyTimesheet` Model
**File:** `apps/hrm/models/monthly_timesheet.py`
**Goal:** Update aggregation table to support payroll inputs.

### Changes
*   **Add New Fields:**
    *   `tc1_overtime_hours`, `tc2_overtime_hours`, `tc3_overtime_hours` (Sum of respective daily fields).
    *   `late_coming_minutes`, `early_leaving_minutes` (Sum of daily raw minutes).
    *   `total_penalty_count` (Count of days where `is_punished=True`).
*   **Logic Update in `compute_aggregates`:**
    *   Sum the new fields above.
    *   **Fix:** Change `paid_leave_days` calculation logic. Instead of `Count(AbsenceReason.PAID_LEAVE)`, use `Sum(paid_leave_hours) / 8` to support partial leave days.

## Step 3: Rewrite `TimesheetCalculator` Service
**File:** `apps/hrm/services/timesheet_calculator.py`
**Goal:** Implement the "Complex Calculation" rules from Section 3 of the Business Specs.

### Logic Changes
1.  **Official Hours Calculation (Section 3.1):**
    *   Implement precise Morning/Afternoon segment calculation.
    *   Morning: `Max(start, 08:00)` to `Min(end, 12:00)`.
    *   Afternoon: `Max(start, 13:30)` to `Min(end, 17:30)`.
    *   Sum = `official_hours`.

2.  **Single Check-in Logic (Section 3.2):**
    *   If only In or only Out exists:
        *   **Force Set** `working_days` = 0.5 (if 2 shifts) or 0.25 (if 1 shift).
        *   **Hard Rule:** `overtime_hours` = 0 (and all sub-types = 0).

3.  **Penalty & Grace Period (Section 3.3):**
    *   Calculate `late_minutes` and `early_minutes` strictly against schedule.
    *   Determine `grace_period`:
        *   Standard: 5 minutes.
        *   Post-Maternity: 65 minutes.
    *   Set `is_punished = (late + early > grace_period)`.

4.  **Overtime Breakdown (Section 4.2):**
    *   Calculate intersection of `[Log_Start, Log_End]` vs `[OT_Proposal_Start, OT_Proposal_End]`.
    *   Categorize into TC1, TC2, TC3 based on `day_type` (Official/Compensatory vs Sunday vs Holiday).

5.  **Working Days Finalization:**
    *   Base: `official_hours / 8`.
    *   Add: `paid_leave_hours / 8`.
    *   Add: `0.125` (1 hour) if **Post-Maternity** mode active.
    *   Cap: `Min(Total, Max_Day_Target)` (1.0 or 0.5).

6.  **Snapshot Data:**
    *   Retrieve and save `contract_id` and `wage_rate` based on `date`.
