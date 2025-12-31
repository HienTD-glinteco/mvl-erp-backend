# Fix Timesheet Single Punch Bugs

## Problem Description

### Bug 1: Incorrect Status for Single Punch During Work Hours
When an employee checks in once (single punch) during working hours, the status is incorrectly set to `SINGLE_PUNCH` instead of `NOT_ON_TIME`.

**Current behavior:**
- Employee "nhungnt" checks in once at 16:47 on 31/12
- Status = `SINGLE_PUNCH` (Chấm công 1 lần)

**Expected behavior:**
- During working hours (before end of day): Status = `NOT_ON_TIME` (không đúng giờ)
- After end of day (`is_finalizing=True`): Status = `SINGLE_PUNCH`

### Bug 2: Working Days Calculated Before End of Day
When an employee has single punch during working hours, `working_days` is calculated as 0.5 instead of being null/empty.

**Current behavior:**
- Single punch during work hours → `working_days = 0.5`

**Expected behavior:**
- During working hours (before end of day): `working_days = None` (rỗng)
- After end of day (`is_finalizing=True`): `working_days = 0.5`

---

## Root Cause Analysis

### Bug 1 Root Cause
In `TimesheetCalculator.compute_status()` (line 383-386), the single punch check does not consider the `is_finalizing` flag. It always returns `SINGLE_PUNCH` regardless of whether it's real-time or finalization.

### Bug 2 Root Cause
In `TimesheetCalculator.compute_working_days()` (line 413-428), when `status == SINGLE_PUNCH`, it always sets `working_days = max_cap / 2`. However:
1. After fixing Bug 1, during real-time (`is_finalizing=False`), status will be `NOT_ON_TIME` instead of `SINGLE_PUNCH`
2. The method needs to detect single punch condition **independently** and check `is_finalizing`
3. Currently `compute_working_days()` doesn't receive `is_finalizing` parameter

---

## Proposed Changes

### [MODIFY] [timesheet_calculator.py](file:///home/dev/Projects/Work/maivietland/backend/apps/hrm/services/timesheet_calculator.py)

#### Change 1: Update `compute_status()` method (Bug 1 Fix)

```diff
-        # 3. Single Punch -> SINGLE_PUNCH
+        # 3. Single Punch Logic
         if (self.entry.start_time and not self.entry.end_time) or (not self.entry.start_time and self.entry.end_time):
-            self.entry.status = TimesheetStatus.SINGLE_PUNCH
+            # Real-time: NOT_ON_TIME (incomplete attendance is a violation)
+            # Finalization: SINGLE_PUNCH (confirmed single check at end of day)
+            if is_finalizing:
+                self.entry.status = TimesheetStatus.SINGLE_PUNCH
+            else:
+                self.entry.status = TimesheetStatus.NOT_ON_TIME
             return
```

#### Change 2: Update `compute_working_days()` signature and logic (Bug 2 Fix)

Add `is_finalizing` parameter and update single punch handling:

```diff
-    def compute_working_days(self) -> None:
+    def compute_working_days(self, is_finalizing: bool = False) -> None:
         """Compute working_days according to business rules."""
-        self.entry.working_days = Decimal("0.00")
+        # Check for single punch BEFORE setting default
+        is_single_punch = (self.entry.start_time and not self.entry.end_time) or (
+            not self.entry.start_time and self.entry.end_time
+        )
+
+        # Real-time single punch: leave working_days as None
+        if is_single_punch and not is_finalizing:
+            self.entry.working_days = None
+            return
+
+        self.entry.working_days = Decimal("0.00")
```

#### Change 3: Update `compute_all()` to pass `is_finalizing` to `compute_working_days()`

```diff
         # 5. Compute Status & Working Days
         self.compute_status(is_finalizing=is_finalizing)
-        self.compute_working_days()
+        self.compute_working_days(is_finalizing=is_finalizing)
```

---

### [MODIFY] [timesheet.py](file:///home/dev/Projects/Work/maivietland/backend/apps/hrm/models/timesheet.py)

Update `clean()` method to pass `is_finalizing=False` (real-time mode):

```diff
         # Calculate status
-        calculator.compute_status()
+        calculator.compute_status(is_finalizing=False)

         # Compute working_days according to business rules
-        calculator.compute_working_days()
+        calculator.compute_working_days(is_finalizing=False)
```

---

### [MODIFY] [test_timesheet_calculator_v2.py](file:///home/dev/Projects/Work/maivietland/backend/apps/hrm/tests/test_timesheet_calculator_v2.py)

Update `test_single_punch_logic` to test both real-time and finalization modes:

```python
def test_single_punch_logic(self, employee, work_schedule):
    d = date(2023, 1, 2)  # Monday
    entry = TimeSheetEntry.objects.create(
        employee=employee,
        date=d,
        check_in_time=combine_datetime(d, time(8, 0)),
        is_manually_corrected=True,
        start_time=combine_datetime(d, time(8, 0)),
    )

    calc = TimesheetCalculator(entry)

    # Real-time mode (is_finalizing=False)
    calc.compute_all(is_finalizing=False)
    assert entry.status == TimesheetStatus.NOT_ON_TIME
    assert entry.working_days is None  # Bug 2 fix

    # Finalization mode (is_finalizing=True)
    calc.compute_all(is_finalizing=True)
    assert entry.status == TimesheetStatus.SINGLE_PUNCH
    assert entry.working_days == Decimal("0.50")
```

---

### [MODIFY] [test_timesheet_day_type_and_single_attendance.py](file:///home/dev/Projects/Work/maivietland/backend/apps/hrm/tests/test_timesheet_day_type_and_single_attendance.py)

Update tests to use `is_finalizing=True` when expecting `SINGLE_PUNCH` status:

```diff
 def test_single_attendance_status_for_single_punch():
     emp = _create_employee()
     d = date(2025, 3, 3)

     # Single punch: only start_time
     ts = TimeSheetEntry.objects.create(employee=emp, date=d, check_in_time=combine_datetime(d, time(8, 0)))
+    # After save/clean, real-time mode sets NOT_ON_TIME
+    assert ts.status == TimesheetStatus.NOT_ON_TIME
+    assert ts.working_days is None
+
+    # Finalization mode
+    from apps.hrm.services.timesheet_calculator import TimesheetCalculator
+    TimesheetCalculator(ts).compute_all(is_finalizing=True)
     assert ts.status == TimesheetStatus.SINGLE_PUNCH
+    assert ts.working_days == Decimal("0.50")
```

---

## Verification Plan

### Automated Tests

```bash
cd /home/dev/Projects/Work/maivietland/backend

# Run specific single punch tests
pytest apps/hrm/tests/test_timesheet_calculator_v2.py::TestTimesheetCalculatorV2::test_single_punch_logic -v
pytest apps/hrm/tests/test_timesheet_day_type_and_single_attendance.py -v

# Run all timesheet tests
pytest apps/hrm/tests/ -v -k "timesheet" --tb=short
```

### Manual Verification

Test via Django shell:
```python
from apps.hrm.models import Employee, TimeSheetEntry
from datetime import date, time
from libs.datetimes import combine_datetime

emp = Employee.objects.first()
d = date.today()

# Create single punch entry
ts = TimeSheetEntry.objects.create(
    employee=emp,
    date=d,
    check_in_time=combine_datetime(d, time(16, 47))
)

# Real-time: should be NOT_ON_TIME with working_days=None
print(f"Status: {ts.status}")  # Expected: not_on_time
print(f"Working days: {ts.working_days}")  # Expected: None

# Finalization
from apps.hrm.services.timesheet_calculator import TimesheetCalculator
calc = TimesheetCalculator(ts)
calc.compute_all(is_finalizing=True)

print(f"Status: {ts.status}")  # Expected: single_punch
print(f"Working days: {ts.working_days}")  # Expected: 0.50
```
