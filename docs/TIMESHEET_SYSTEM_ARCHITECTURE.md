# Timesheet System Architecture

This document provides a comprehensive overview of the timesheet management system within the HRM module. It details the data models, business logic, automated processes, and data flow, serving as a technical reference for developers.

## 1. Core Concepts

The timesheet system is designed to track employee work hours, calculate official and overtime hours, and aggregate this data into monthly summaries for payroll and reporting.

- **Attendance Records**: Raw check-in/check-out events from attendance devices.
- **Timesheet Entries**: Daily records (`TimeSheetEntry`) for each employee, storing calculated work hours.
- **Monthly Timesheets**: Aggregated monthly summaries (`EmployeeMonthlyTimesheet`) for each employee, including total work days, leave days, and other payroll-related metrics.
- **Work Schedules**: Defines the official working hours for different days of the week, used to calculate official vs. overtime hours.

## 2. Data Models

### 2.1. `TimeSheetEntry`

(`apps/hrm/models/timesheet.py`)

This model represents a single day's timesheet for an employee.

**Key Fields:**
- `employee`: ForeignKey to `Employee`.
- `date`: The specific date of the entry.
- `start_time`, `end_time`: The first check-in and last check-out time for the day.
- `morning_hours`, `afternoon_hours`: Hours worked during official morning and afternoon sessions, calculated based on the `WorkSchedule`.
- `official_hours`: Sum of `morning_hours` and `afternoon_hours`.
- `overtime_hours`: Hours worked outside of the official schedule (currently always 0, pending OT approval integration).
- `total_worked_hours`: Sum of `official_hours` and `overtime_hours`.
- `status`: `on_time`, `not_on_time`, `absent`. Default is `absent`. Manual calculation via `calculate_status()` is not yet implemented.
- `absent_reason`: Reason for absence, e.g., `paid_leave`, `unpaid_leave`.
- `count_for_payroll`: Boolean indicating whether this entry should be counted for payroll calculations. Can be filtered by employee_salary_type in API.
- `is_full_salary`: Boolean indicating whether this entry counts as full salary (affects probation vs. official working days aggregation).

### 2.2. `EmployeeMonthlyTimesheet`

(`apps/hrm/models/monthly_timesheet.py`)

This model stores the aggregated timesheet data for an employee for a specific month.

**Key Fields:**
- `employee`: ForeignKey to `Employee`.
- `report_date`: The first day of the month this summary represents.
- `month_key`: A string key `YYYYMM` for easy lookup.
- `probation_working_days`, `official_working_days`, `total_working_days`: Aggregated day counts.
- `official_hours`, `overtime_hours`, `total_worked_hours`: Aggregated hour counts.
- `paid_leave_days`, `unpaid_leave_days`, etc.: Counts of different leave types.
- `opening_balance_leave_days`, `consumed_leave_days`, `remaining_leave_days`: Leave balance tracking.
- `need_refresh`: A boolean flag that triggers an asynchronous update of the aggregated data.

## 3. Data Flow and Automation

The timesheet system is highly automated, relying on signals and Celery tasks to process data from raw attendance records to monthly summaries.

### 3.1. Attendance Record to Timesheet Entry

1.  **Signal Trigger**: When an `AttendanceRecord` is saved or deleted, the `handle_attendance_record_save` or `handle_attendance_record_delete` signal in `apps/hrm/signals/attendance.py` is triggered.
2.  **Find or Create `TimeSheetEntry`**: The signal handler finds or creates a `TimeSheetEntry` for the corresponding employee and date.
3.  **Update `start_time` and `end_time`**: It determines the earliest `start_time` and latest `end_time` from all `AttendanceRecord`s for that day. In the save handler, the logic compares the new timestamp with existing times and updates if necessary. In the delete handler, all remaining records are queried to recalculate the times.
4.  **Calculate Hours**: `entry.calculate_hours_from_schedule()` is called. This method:
    - Fetches the `WorkSchedule` for the weekday (if not provided)
    - If no `start_time` is set, sets all hours to 0 and returns early
    - If no `WorkSchedule` is found, sets `morning_hours` and `afternoon_hours` to 0 (graceful fallback)
    - If `WorkSchedule` exists, calculates hours by comparing attendance times against schedule boundaries
    - Sets `overtime_hours` to 0 (pending OT approval integration)
5.  **Mark for Refresh**: The corresponding `EmployeeMonthlyTimesheet` is marked with `need_refresh = True`.

### 3.2. Monthly Timesheet Aggregation

1.  **Celery Task**: The `update_monthly_timesheet_async` task runs periodically (e.g., every 30 seconds).
2.  **Find Refresh Targets**: The task queries for `EmployeeMonthlyTimesheet` instances where `need_refresh` is `True`.
3.  **Recalculate Aggregates**: For each instance, it calls `refresh_for_employee_month()` (which internally calls `compute_aggregates()`), summing up the data from all `TimeSheetEntry` records for that month.
4.  **Clear Flag**: After the update, `need_refresh` is set back to `False`.

### 3.3. Monthly Timesheet Preparation

1.  **On-Hire Signal**: When a new employee is hired (created with working status) or an existing employee's status changes from a leave status to a working status, the `prepare_timesheet_on_hire_post_save` signal in `apps/hrm/signals/employee.py` triggers the `prepare_monthly_timesheets` Celery task for that employee. When returning from leave, `increment_leave=False` is passed to skip leave increment.
2.  **Scheduled Task**: The `prepare_monthly_timesheets` task also runs on the 1st of every month at 00:01 for all employees with working statuses (Active, Onboarding).
3.  **Create Entries**: The task ensures that `TimeSheetEntry` and `EmployeeMonthlyTimesheet` rows exist for the entire month for the relevant employees, preventing gaps in data.
4.  **Leave Increment**: When processing all employees (not a single employee), the task increments `available_leave_days` by 1 for all employees with working statuses, unless `increment_leave=False` is explicitly passed.

## 4. Key Services and Logic

-   **`apps.hrm.services.timesheets`**: Contains the core business logic for creating and initializing timesheet entries and monthly summaries.
    -   `create_entries_for_employee_month`: Creates all daily `TimeSheetEntry` rows for a given employee and month.
    -   `create_monthly_timesheet_for_employee`: Creates or initializes the `EmployeeMonthlyTimesheet` row, including logic for carrying over leave balances from the previous month.
-   **`apps.hrm.models.timesheet.TimeSheetEntry.calculate_hours_from_schedule()`**: The heart of the hour calculation logic. It:
    - Fetches the appropriate `WorkSchedule` for the weekday from cache
    - Handles missing `start_time` by setting all hours to 0
    - Gracefully handles missing `WorkSchedule` by setting morning/afternoon hours to 0
    - When schedule exists, compares `start_time`/`end_time` against schedule boundaries to calculate morning and afternoon hours
    - Currently sets `overtime_hours` to 0 (pending OT approval integration)
-   **`apps.hrm.models.monthly_timesheet.EmployeeMonthlyTimesheet.compute_aggregates()`**: Handles the aggregation of data from daily entries into the monthly summary, including:
    - Summing official_hours, overtime_hours, total_worked_hours
    - Calculating probation_working_days (from entries with `is_full_salary=False`)
    - Calculating official_working_days (from entries with `is_full_salary=True`)
    - Aggregating leave days by type (paid, unpaid, maternity, public holiday)
    - Computing leave balance (opening + accrued - consumed = remaining)

## 5. API Endpoints

The timesheet system exposes a read-only API via `EmployeeTimesheetViewSet` (`apps/hrm/api/views/timesheet.py`).

### 5.1. Endpoints

-   **List Timesheets**: `GET /api/hrm/employee-timesheets/`
    -   Returns paginated list of employees with their timesheet data for the specified month
    -   Includes both daily entries and monthly aggregates
-   **Retrieve Timesheet**: `GET /api/hrm/employee-timesheets/{employee_id}/`
    -   Returns detailed timesheet data for a specific employee for the specified month

### 5.2. Filtering

Via `EmployeeTimesheetFilterSet` (`apps/hrm/api/filtersets/timesheet.py`):

-   `month`: Month in MM/YYYY format (e.g., "03/2025"). Defaults to current month if not provided.
-   `employee`: Filter by employee ID
-   `branch`, `block`, `department`, `position`: Filter by organizational structure
-   `employee_salary_type`: Filter by employee salary type (SALARIED/HOURLY). This affects which entries are included:
    -   `SALARIED`: Only entries where `count_for_payroll=True`
    -   `HOURLY`: Only entries where `count_for_payroll=False`

### 5.3. Search and Ordering

-   **Search**: By employee `code` or `fullname`
-   **Ordering**: By `code` or `fullname`. Default is `fullname`.

### 5.4. Response Structure

Each employee's timesheet includes:
-   `employee`: Employee details (id, code, fullname, branch, department, etc.)
-   `dates`: Array of daily entries with date, status, times, and hours
-   Monthly aggregates: `probation_days`, `official_work_days`, `total_work_days`, `unexcused_absence_days`, `holiday_days`, `unpaid_leave_days`, `maternity_leave_days`, `annual_leave_days`, `initial_leave_balance`, `remaining_leave_balance`

## 6. Testing

The timesheet system includes comprehensive test coverage:

-   **`apps/hrm/tests/test_timesheet_enhancements.py`**: Tests for new fields and calculations
    -   Tests for hour calculations (official, overtime, total)
    -   Tests for monthly aggregations (probation vs. official days)
    -   Tests for WorkSchedule caching
    -   Tests for Celery task behavior (leave increment logic)
-   **`apps/hrm/tests/test_timesheet_api.py`**: API endpoint tests
    -   Tests for list/retrieve endpoints
    -   Tests for month filtering
    -   Tests for service layer (entry creation, monthly aggregation)
-   **`apps/hrm/tests/test_attendance_signals.py`**: Signal handler tests
    -   Tests for attendance record → timesheet entry updates
    -   Tests for monthly timesheet refresh flagging

### 6.1. Test Fixtures

-   **`work_schedules`** (in `conftest.py`): Creates standard Monday-Friday schedules:
    -   Morning: 08:00-12:00
    -   Noon: 12:00-13:00
    -   Afternoon: 13:00-17:00

## 7. TODOs and Future Work

This section lists the outstanding `TODO` items found in the codebase and suggests areas for future improvement.

### 7.1. Existing TODOs

-   **Overtime Calculation**:
    -   **Location**: `apps/hrm/models/timesheet.py` in `calculate_hours_from_schedule()`
    -   **TODO**: `Calculate overtime hours - complex business logic pending clarification.`
    -   **Recommendation**: The current implementation sets `overtime_hours` to zero. A detailed specification is needed to implement rules for overtime, including different rates, break times, and weekend/holiday policies.

-   **Missing `end_time` Handling**:
    -   **Location**: `apps/hrm/models/timesheet.py` in `calculate_hours_from_schedule()`
    -   **TODO**: `implement case missing end time, that means employee doesn't make enough attendance, at least 2 must be considered as valid.`
    -   **Recommendation**: Currently, this raises a `NotImplementedError`. A policy needs to be defined. Should the day be marked as an unexcused absence? Or should hours be calculated up to a default time?

-   **`calculate_status` Method**:
    -   **Location**: `apps/hrm/models/timesheet.py`
    -   **TODO**: `implement this method`
    -   **Recommendation**: This method is crucial for determining if an employee was `on_time`, `not_on_time`, or `absent`. The logic should be based on comparing actual hours worked against expected hours, and considering `absent_reason` if present. Until implemented, `status` defaults to `absent` and must be manually set if needed.

-   **Leave Day Validation**:
    -   **Location**: `apps/hrm/services/timesheets.py` in `create_monthly_timesheet_for_employee()`
    -   **TODO**: `need to fetch maximum number of available leave days from current employee's contract to use it for validation.`
    -   **Recommendation**: When calculating leave balances, the system should validate against the employee's contract to prevent consuming more leave than allocated. This requires integration with the (currently unimplemented) `Contract` model.

-   **Leave Day Logic**:
    -   **Location**: `apps/hrm/tasks/timesheets.py`
    -   **TODO**: `rework on this after SRS for available leave day is clear.`
    -   **Recommendation**: The logic for incrementing `available_leave_days` needs to be finalized based on a clear Software Requirements Specification (SRS).

-   **Timesheet Complaint Feature**:
    -   **Location**: `apps/hrm/api/views/timesheet.py`
    -   **TODO**: `correct this field after implementing timesheet complaint feature`
    -   **Recommendation**: The API currently has a placeholder for a `has_complaint` field. This feature needs to be designed and implemented, allowing employees to flag and comment on incorrect timesheet entries.

-   **Overtime (OT) Approval Integration**:
    -   **Location**: `apps/hrm/models/timesheet.py` in `calculate_hours_from_schedule()`
    -   **TODO**: Overtime should only be recorded when there is an approved OT request form. When recording OT hours, only the hours specified in the approved request should be counted.
    -   **Recommendation**: Implement an OT request model with approval workflow. Modify `calculate_hours_from_schedule()` to check for approved OT requests before calculating `overtime_hours`. The system should validate that the actual worked hours match or are within the approved OT request period.

-   **Leave Request Integration with Timesheet Status**:
    -   **Location**: `apps/hrm/models/timesheet.py` and signal handlers
    -   **TODO**: When an employee takes leave for any reason, the corresponding `TimeSheetEntry` status needs to be updated for the affected dates. The specific handling approach is pending, but the idea is to use approved leave request forms as the basis for determining and triggering the updates.
    -   **Recommendation**: Implement a leave request model with approval workflow. Create signal handlers that listen to leave request approvals and automatically update the `status` and `absent_reason` fields of the corresponding `TimeSheetEntry` records. Consider adding a reference from `TimeSheetEntry` to the leave request for audit purposes.

### 7.2. General Recommendations

-   **Contract Model Integration**: Several `TODOs` depend on a `Contract` model. Implementing this model is a prerequisite for features like leave day validation.
-   **Testing**: Increase test coverage, especially for the complex logic in `calculate_hours_from_schedule` and `create_monthly_timesheet_for_employee`, to cover edge cases like holidays, leave, and different work schedules.
-   **Configuration**: Consider making some hardcoded values, like the monthly leave day increment, configurable in the settings.
