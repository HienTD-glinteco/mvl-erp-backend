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
        - Calculate Overtime: `(Actual Work Duration) - (Scheduled Work Duration)`.
        - Handle missing `end_time`: Do not zero out hours immediately; consider marking as `MISSING_CHECKOUT` (requires updating `TimesheetStatus` choices) or keep as is but ensure status reflects it.

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
    - **Logic**: Iterate through `proposal.overtime_entries`. For each entry, find `TimesheetEntry` by `entry.date`. Update `overtime_hours` with `entry.duration_hours`.
- [ ] **Task 3.6: API Integration**
    - **File**: `apps/hrm/api/views/proposal.py`
    - **Action**: Update `approve` action to call `ProposalService.approve_proposal`.
