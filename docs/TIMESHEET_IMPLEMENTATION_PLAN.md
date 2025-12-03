# Timesheet & Attendance Implementation Plan

This plan breaks down the Gap Analysis into small, executable tasks for rapid implementation and review.

## Phase 1: Core Timesheet Logic (Models)
**Goal**: Ensure `TimesheetEntry` correctly calculates status and hours based on `WorkSchedule`.

- [ ] **Task 1.1: Add `is_manually_corrected` field**
    - **File**: `apps/hrm/models/timesheet.py`
    - **Action**: Add `is_manually_corrected = models.BooleanField(default=False)`
    - **Action**: Create migration.
- [ ] **Task 1.2: Implement `calculate_status`**
    - **File**: `apps/hrm/models/timesheet.py`
    - **Action**: Implement `calculate_status` method.
    - **Logic**:
        - Fetch `WorkSchedule` for the weekday.
        - Compare `start_time` with `morning_start_time` + `allowed_late_minutes`.
        - Set `status` to `ON_TIME`, `NOT_ON_TIME`, or `ABSENT`.
- [ ] **Task 1.3: Improve `calculate_hours_from_schedule`**
    - **File**: `apps/hrm/models/timesheet.py`
    - **Action**: Update `calculate_hours_from_schedule`.
    - **Logic**:
        - Calculate `actual_work_hours` = `(CheckOut - CheckIn) - BreakTime`.
        - **Overtime Policy**: By business rule, OT is only counted when an overtime proposal has been approved for that date/time.
            - Default: `overtime_hours = 0` when there is no approved `ProposalOvertimeEntry` for the date.
            - If there is an approved `ProposalOvertimeEntry` for the date:
                - `raw_ot = max(0, actual_work_hours - standard_work_hours)`
                - `overtime_hours = min(raw_ot, approved_ot_duration)`
        - Handle missing `end_time`: Do not zero out hours immediately; mark as `MISSING_CHECKOUT` (requires updating `TimesheetStatus` choices) or keep as is but ensure status reflects it.

## Phase 2: Contract Integration
**Goal**: Ensure payroll-relevant flags are set correctly based on Contract.

- [ ] **Task 2.1: Probation Logic**
    - **File**: `apps/hrm/models/timesheet.py`
    - **Action**: Update `save()` or `clean()` method.
    - **Logic**:
        - Fetch active `Contract` for `self.employee` and `self.date`.
        - If `Contract.net_percentage == "85"`, set `is_full_salary = False`.

## Phase 3: Proposal Execution (Service)
**Goal**: Make approved proposals actually update the timesheets.

- [ ] **Task 3.1: Create `ProposalService`**
    - **File**: `apps/hrm/services/proposal_service.py` (New File)
    - **Action**: Define class/module and `approve_proposal(proposal)` function.
- [ ] **Task 3.2: Implement Leave Logic**
    - **Logic**: Iterate `proposal.start_date` to `proposal.end_date`. Find `TimesheetEntry`. Set `status=ABSENT`, `absent_reason=proposal.type`.
- [ ] **Task 3.3: Implement Complaint Logic (Correction)**
    - **Logic**: Update `TimesheetEntry` with `proposal.approved_check_in_time` and `proposal.approved_check_out_time`. Set `is_manually_corrected=True`. Recalculate hours.
- [ ] **Task 3.4: Implement Complaint Logic (Cannot Attend)**
    - **Logic**: Create `AttendanceRecord` with `type=OTHER`, `time=proposal.proposed_check_in_time` (and out time). This triggers existing signals.
- [ ] **Task 3.5: Implement Overtime Logic**
    - **Logic**: The approval process creates `ProposalOvertimeEntry` records which declare approved OT durations for specific dates/times.
        - Do NOT blindly set `TimesheetEntry.overtime_hours` to the approved value.
        - After approval, for each `ProposalOvertimeEntry`:
            - Find the `TimesheetEntry` for the same date (create or update if needed).
            - Trigger `timesheet_entry.calculate_hours_from_schedule()` and save so Phase 1 logic computes `overtime_hours = min(actual_ot, approved_ot_duration)`.
        - This ensures OT is only counted when approved and capped by the approved duration; if an employee works less than the approved amount, only the actual worked OT is counted.
- [ ] **Task 3.6: API Integration**
    - **File**: `apps/hrm/api/views/proposal.py`
    - **Action**: Update `approve` action to call `ProposalService.approve_proposal`.
