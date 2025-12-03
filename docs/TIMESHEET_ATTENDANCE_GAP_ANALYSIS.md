# Timesheet & Attendance Gap Analysis
**Date:** December 3, 2025
**Status:** Analysis Complete / Ready for Implementation

This document summarizes the findings from the review of the HRM system, specifically focusing on the **Timesheet**, **Attendance**, **Contract**, and **Proposal** modules. It serves as a context handover for future development sessions.

**Note:** The **Payroll** module (SRS 8) is explicitly **out of scope** for the current phase. Focus strictly on Attendance and Timesheet logic.

## 1. Executive Summary
The current system successfully collects raw attendance data and generates basic timesheet entries. However, it lacks the **business logic layer** required to process this data into accurate payroll information. Critical gaps exist in status calculation (Late/On-time), overtime processing, and the execution of approved administrative proposals (Leave, Corrections).

## 2. Detailed Gap Analysis

### A. Timesheet Logic (`apps/hrm/models/timesheet.py`)
*   **Status Calculation Missing**:
    *   The method `calculate_status(self)` is currently empty (`pass`).
    *   **Impact**: Employees are never marked as `LATE` or `ON_TIME` automatically. The system cannot distinguish between a valid workday and an absence unless manually edited.
*   **Overtime Logic Missing**:
    *   In `calculate_hours_from_schedule`, `overtime_hours` is hardcoded to `Decimal("0.00")`.
    *   **Impact**: No overtime is recorded, regardless of how long an employee works.
*   **Incomplete Hour Calculation**:
    *   If `end_time` is missing (forgot to checkout), `morning_hours` and `afternoon_hours` are set to `0`.
    *   **Impact**: Employees lose credit for the entire day if they miss one punch.
*   **Rigid Scheduling**:
    *   `WorkSchedule` is tied strictly to days of the week (Mon-Sun).
    *   **Impact**: Cannot support rotating shifts, night shifts crossing midnight, or special holiday schedules.

### B. Contract Integration (`apps/hrm/models/contract.py`)
*   **Probation Logic Missing**:
    *   `TimesheetEntry.is_full_salary` defaults to `True`.
    *   The system does not check `Contract.net_percentage` (e.g., "85%" for probation).
    *   **Impact**: Probation employees are calculated at full salary rate in reports.
*   **Leave Accrual**:
    *   `create_monthly_timesheet_for_employee` hardcodes leave increment to `1.0` day.
    *   **Impact**: Ignores `Contract.annual_leave_days` (max 12) and eligibility rules.
*   **Working Time Type Ignored**:
    *   `Contract.working_time_type` (Full-time/Part-time) is not checked when calculating hours.

### C. Proposal Integration (`apps/hrm/models/proposal.py`)
*   **No Execution Logic**:
    *   The `Proposal` model captures intent (`PAID_LEAVE`, `TIMESHEET_ENTRY_COMPLAINT`, `OVERTIME_WORK`) and now includes fields for approved values (`approved_check_in_time`, `approved_check_out_time`).
    *   However, the `approve` action in `ProposalViewSet` **only updates the Proposal status**. It does **not** propagate these changes to the `TimeSheetEntry`.
    *   **Impact**:
        *   Approved **Leave** does not mark the day as `ABSENT` (Authorized) or `ON_LEAVE`.
        *   Approved **Timesheet Complaints** (Correction) do not update the `start_time`/`end_time` on the timesheet, even though the Proposal stores the approved times.
        *   Approved **Overtime** requests do not credit the hours to the timesheet.
*   **Timesheet Complaint Handling**:
    *   **Linkage Exists**: `ProposalTimeSheetEntry` model correctly links complaints to timesheets (1-1).
    *   **Case 1: Cannot Attend (Missing Data)**: Requires creating an `AttendanceRecord` with type `OTHER`. This is currently unimplemented.
    *   **Case 2: Correction (Wrong Data)**: Requires copying `approved_check_in_time`/`approved_check_out_time` from Proposal to `TimeSheetEntry`.
    *   **Constraint**: Automated updates (from new attendance logs) must not overwrite manual corrections from approved proposals.
*   **Overtime Handling**:
    *   **Data Structure Exists**: `ProposalOvertimeEntry` model correctly captures date-specific overtime requests.
    *   **Requirement**: When approving, the system must iterate through `proposal.overtime_entries` and update the corresponding `TimesheetEntry` for each date.

## 3. Implementation Plan

### Phase 1: Core Timesheet Logic
1.  **Implement `calculate_status`**:
    *   Compare `start_time` with `WorkSchedule.morning_start_time` + `WorkSchedule.allowed_late_minutes`.
    *   **Note**: `allowed_late_minutes` is a field in `WorkSchedule` model.
    *   Set status to `ON_TIME`, `NOT_ON_TIME` (Late), or `ABSENT`.
2.  **Fix Hour Calculation**:
    *   Implement basic overtime: `(Actual End - Actual Start) - (Schedule End - Schedule Start)`.
    *   Handle missing `end_time`: Mark as `MISSING_CHECKOUT` instead of 0 hours.
3.  **Performance Optimization**:
    *   When processing multiple employees (e.g., monthly generation), **prefetch active contracts** to minimize database queries.

### Phase 2: Contract Integration
1.  **Probation Flag**:
    *   In `TimesheetEntry.save()`, fetch active contract.
    *   Set `is_full_salary = False` if `Contract.net_percentage == "85"`.
    *   *Note*: Keep current generation logic (based on Employee status).

### Phase 3: Proposal Execution Service
1.  **Create `ProposalService`**:
    *   Implement `approve_proposal(proposal)` method.
2.  **Handle Proposal Types**:
    *   **Leave**: Find `TimesheetEntry` -> Set `status=ABSENT`, `absent_reason=proposal.type`.
    *   **Complaint (Cannot Attend)**: Create `AttendanceRecord` (type=`OTHER`). This will trigger `post_save` signal to update `TimesheetEntry`.
    *   **Complaint (Correction)**: Update `TimesheetEntry.start_time/end_time` using `proposal.approved_check_in_time` and `proposal.approved_check_out_time`. Ensure `TimesheetEntry` has a flag (e.g., `is_manually_corrected`) to prevent overwrite by future signals.
    *   **Overtime**: Iterate through `proposal.overtime_entries`. For each entry, find the `TimesheetEntry` (by date) and update `overtime_hours` using `entry.duration_hours`.
3.  **Connect to API**:
    *   Call this service from the `approve` action in `ProposalViewSet`.

## 4. Relevant Files
*   `apps/hrm/models/timesheet.py`: Core logic for hours and status.
*   `apps/hrm/models/work_schedule.py`: Schedule definitions (including `allowed_late_minutes`).
*   `apps/hrm/models/contract.py`: Contract definitions.
*   `apps/hrm/models/proposal.py`: Proposal definitions.
*   `apps/hrm/services/timesheets.py`: Generation logic.
*   `apps/hrm/tasks/timesheets.py`: Celery tasks.
*   `apps/hrm/api/views/proposal.py`: API endpoints for proposals.
