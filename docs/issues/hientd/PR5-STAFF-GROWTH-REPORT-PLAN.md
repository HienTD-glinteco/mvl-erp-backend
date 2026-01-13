# PR5: Staff Growth Report - Fix Plan

> **Branch name:** `fix/staff-growth-report-duplicate-count`
> **Sprint:** Sprint 8
> **Estimated effort:** 2-3 days
> **Priority:** 🟠 High

---

## 📋 Issue Summary

| # | Task ID | Title | Status | Module |
|---|---------|-------|--------|--------|
| 1 | [86ew457ta](./86ew457ta-bc-tang-truong-ns-nghi-nhieu-lan.md) | BC tăng trưởng NS_Nhân sự nghỉ nhiều lần đang đếm nhiều lần | 🟢 OPEN | 4.8. Báo cáo |

---

## 🔍 Root Cause Analysis

### Issue Description

> Nhân viên MV000000102 (Nguyen Van An) có 2 lần nghỉ việc trong tháng 1/2026
> Bug: BC đang đếm lên 2 lần nghỉ cho NV này
> Expected: Trong thời gian truy vấn, nếu nhân viên phát sinh nhiều lần nghỉ việc => Chỉ đếm 1 lần

### Current Logic (BROKEN)

**Step 1: Event Tracking** (`apps/hrm/tasks/reports_hr/helpers.py`)

Mỗi khi có event RESIGNATION, hệ thống tạo/update record theo **ngày**:
```python
StaffGrowthReport.objects.update_or_create(
    report_date=report_date,  # ← Daily granularity
    branch=branch,
    block=block,
    department=department,
    defaults={
        "month_key": month_key,
        "week_key": week_key,
        "num_resignations": num_resignations,  # Count all events
    },
)
```

**Step 2: API Aggregation** (`apps/hrm/api/views/recruitment_reports.py`)

API aggregate theo `Sum("num_resignations")`:
```python
aggregated = queryset.values(period_field).annotate(
    num_resignations=Sum("num_resignations"),  # ← Cộng dồn events
)
```

**Example:**
```
| report_date | department_id | num_resignations |
|-------------|---------------|------------------|
| 2026-01-05  | 8             | 1                | ← NV nghỉ lần 1
| 2026-01-10  | 8             | 1                | ← NV nghỉ lần 2 (CÙNG NV!)
```
→ API Sum = 2 ← **BUG!** (Expected = 1)

### Root Cause

1. **Data granularity quá nhỏ (daily)** → phải aggregate lên week/month → cộng dồn duplicate
2. **Không track employee đã được đếm** → cùng 1 NV có nhiều events → đếm nhiều lần
3. **Logic đếm số EVENT** thay vì **số DISTINCT EMPLOYEE**

---

## 🔧 Solution: Refactor Model & Event Tracking

### Architecture Change

| Aspect | Current | New |
|--------|---------|-----|
| **Granularity** | Daily (`report_date`) | Weekly + Monthly (`timeframe_type`) |
| **Unique constraint** | `report_date + branch + block + dept` | `timeframe_key + timeframe_type + branch + block + dept` |
| **Event tracking** | Count all events → sum later | Check if employee already counted in timeframe |
| **API** | Aggregate (Sum) by period | **Direct query by timeframe** - no aggregate |

### Key Principles

1. **Mỗi record độc lập** - lưu giá trị thực tế (distinct employees) cho timeframe đó
2. **Event deduplication** - khi có event, check đã ghi nhận employee này chưa
3. **No aggregation at API level** - data đã pre-calculated đúng

---

## 📐 New Model Design

### Option A: Single Model with Timeframe Type (Recommended)

```python
class StaffGrowthReport(BaseReportModel):
    """Staff growth statistics by timeframe (week/month).
    
    Each record stores DISTINCT employee counts for a specific timeframe.
    No aggregation needed at query time.
    """
    
    class TimeframeType(models.TextChoices):
        WEEK = "week", "Week"
        MONTH = "month", "Month"
    
    timeframe_type = models.CharField(
        max_length=10,
        choices=TimeframeType.choices,
        verbose_name="Timeframe type",
    )
    timeframe_key = models.CharField(
        max_length=20,
        verbose_name="Timeframe key",
        help_text="Format: 'W01-2026' for week or '01/2026' for month",
        db_index=True,
    )
    
    # Organizational structure
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, null=True, blank=True)
    block = models.ForeignKey(Block, on_delete=models.CASCADE, null=True, blank=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, null=True, blank=True)
    
    # Statistics (DISTINCT employee counts)
    num_introductions = models.PositiveIntegerField(default=0)
    num_returns = models.PositiveIntegerField(default=0)
    num_recruitment_source = models.PositiveIntegerField(default=0)
    num_transfers = models.PositiveIntegerField(default=0)
    num_resignations = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [
            ["timeframe_type", "timeframe_key", "branch", "block", "department"]
        ]
```

### Deduplication Strategy: Use EmployeeWorkHistory

**Không cần tạo model mới** - sử dụng `EmployeeWorkHistory` để check duplicate:

```python
# Check if employee already has this event type in timeframe
def _employee_already_counted(
    employee: Employee,
    event_type: str,
    timeframe_start: date,
    timeframe_end: date,
    department: Department,
) -> bool:
    """Check if employee already has an event of this type in the timeframe."""
    from apps.hrm.models import EmployeeWorkHistory, Employee
    
    event_filter = _get_event_filter(event_type)  # Map to EmployeeWorkHistory filter
    
    return EmployeeWorkHistory.objects.filter(
        employee=employee,
        department=department,
        date__range=(timeframe_start, timeframe_end),
        **event_filter,
    ).exists()
```

---

## 🔧 Event Tracking Logic

### Current Flow (BROKEN)
```
Event occurs → Count events → Create/update daily record → API sums daily records
```

### New Flow
```
Event occurs 
    → Get timeframe (week_key, month_key)
    → For EACH timeframe (week + month):
        → Query EmployeeWorkHistory: Employee already has this event type in timeframe?
            → YES: Skip (no increment)
            → NO: Increment counter in StaffGrowthReport
```

### Implementation

**File:** `apps/hrm/tasks/reports_hr/helpers.py`

```python
from datetime import date, timedelta
from apps.hrm.models import EmployeeWorkHistory, Employee, StaffGrowthReport


def _get_timeframe_range(event_date: date, timeframe_type: str) -> tuple[date, date]:
    """Get start and end dates for a timeframe."""
    if timeframe_type == StaffGrowthReport.TimeframeType.WEEK:
        # ISO week: Monday to Sunday
        start = event_date - timedelta(days=event_date.weekday())
        end = start + timedelta(days=6)
    else:  # MONTH
        start = event_date.replace(day=1)
        # Last day of month
        if event_date.month == 12:
            end = date(event_date.year, 12, 31)
        else:
            end = date(event_date.year, event_date.month + 1, 1) - timedelta(days=1)
    return start, end


def _get_event_history_filter(event_type: str) -> dict:
    """Map event_type to EmployeeWorkHistory filter kwargs."""
    filters = {
        "resignation": {
            "name": EmployeeWorkHistory.EventType.CHANGE_STATUS,
            "status": Employee.Status.RESIGNED,
        },
        "transfer": {"name": EmployeeWorkHistory.EventType.TRANSFER},
        "return": {
            "name": EmployeeWorkHistory.EventType.CHANGE_STATUS,
            "status": Employee.Status.ACTIVE,
            # Additional filter: previous status was RESIGNED or ON_LEAVE
        },
        "introduction": {"name": EmployeeWorkHistory.EventType.INTRODUCTION},
        "recruitment_source": {"name": EmployeeWorkHistory.EventType.RECRUITMENT_SOURCE},
    }
    return filters.get(event_type, {})


def _employee_already_counted_in_timeframe(
    employee: Employee,
    event_type: str,
    current_event_id: int,  # ID of the EmployeeWorkHistory being processed
    timeframe_start: date,
    timeframe_end: date,
    department: Department,
) -> bool:
    """Check if employee already has this event type in timeframe (excluding current event).
    
    Returns True if there's ANOTHER event of same type for this employee
    in the same timeframe (meaning we should skip counting).
    
    Important: Excludes the current event being processed to handle:
    - New event creation: check if any OTHER event exists
    - Event update: check if any OTHER event exists (current one excluded)
    - Event delete: after deletion, recount should work correctly
    """
    event_filter = _get_event_history_filter(event_type)
    
    return EmployeeWorkHistory.objects.filter(
        employee=employee,
        department=department,
        date__range=(timeframe_start, timeframe_end),
        **event_filter,
    ).exclude(id=current_event_id).exists()  # Exclude current event


def _record_staff_growth_event(
    employee: Employee,
    event_type: str,  # "resignation", "transfer", "return", etc.
    event_date: date,
    event_id: int,  # EmployeeWorkHistory.id - for deduplication
    branch: Branch,
    block: Block,
    department: Department,
) -> None:
    """Record a staff growth event with deduplication via EmployeeWorkHistory.
    
    Updates BOTH weekly and monthly reports. Uses EmployeeWorkHistory to check
    if employee was already counted in the timeframe (excluding current event).
    """
    from apps.hrm.models import StaffGrowthReport
    
    # Calculate timeframe keys
    week_number = event_date.isocalendar()[1]
    year = event_date.isocalendar()[0]  # ISO year for week
    week_key = f"W{week_number:02d}-{year}"
    month_key = event_date.strftime("%m/%Y")
    
    # Map event_type to counter field
    counter_field_map = {
        "resignation": "num_resignations",
        "transfer": "num_transfers",
        "return": "num_returns",
        "introduction": "num_introductions",
        "recruitment_source": "num_recruitment_source",
    }
    counter_field = counter_field_map[event_type]
    
    # Process BOTH weekly and monthly timeframes
    timeframes = [
        (StaffGrowthReport.TimeframeType.WEEK, week_key),
        (StaffGrowthReport.TimeframeType.MONTH, month_key),
    ]
    
    for timeframe_type, timeframe_key in timeframes:
        # Get timeframe date range
        start_date, end_date = _get_timeframe_range(event_date, timeframe_type)
        
        # Check if employee already counted in this timeframe (excluding current event)
        if _employee_already_counted_in_timeframe(
            employee, event_type, event_id, start_date, end_date, department
        ):
            logger.debug(
                f"Skipped duplicate {event_type} for {employee.code} in {timeframe_key}"
            )
            continue
        
        # First event for this employee in timeframe → count it
        report, created = StaffGrowthReport.objects.get_or_create(
            timeframe_type=timeframe_type,
            timeframe_key=timeframe_key,
            branch=branch,
            block=block,
            department=department,
        )
        
        setattr(report, counter_field, getattr(report, counter_field) + 1)
        report.save(update_fields=[counter_field])
        logger.debug(
            f"Recorded {event_type} for {employee.code} in {timeframe_key}"
        )
```

### Decrement Logic (When Event is Deleted/Reverted)

```python
def _remove_staff_growth_event(
    employee: Employee,
    event_type: str,
    event_date: date,
    event_id: int,  # ID of the deleted/reverted EmployeeWorkHistory
    branch: Branch,
    block: Block,
    department: Department,
) -> None:
    """Remove a staff growth event (when deleted/reverted).
    
    Decrements counter only if no OTHER events of same type exist 
    for this employee in the timeframe.
    
    Called AFTER the EmployeeWorkHistory record is deleted.
    """
    week_key, month_key = _get_timeframe_keys(event_date)
    counter_field = _get_counter_field(event_type)
    
    timeframes = [
        (StaffGrowthReport.TimeframeType.WEEK, week_key),
        (StaffGrowthReport.TimeframeType.MONTH, month_key),
    ]
    
    for timeframe_type, timeframe_key in timeframes:
        start_date, end_date = _get_timeframe_range(event_date, timeframe_type)
        
        # Check if any OTHER events exist for this employee in timeframe
        # Note: The deleted event is already gone, so no need to exclude by ID
        event_filter = _get_event_history_filter(event_type)
        other_events_exist = EmployeeWorkHistory.objects.filter(
            employee=employee,
            department=department,
            date__range=(start_date, end_date),
            **event_filter,
        ).exists()
        
        if not other_events_exist:
            # No more events → decrement counter
            try:
                report = StaffGrowthReport.objects.get(
                    timeframe_type=timeframe_type,
                    timeframe_key=timeframe_key,
                    branch=branch,
                    block=block,
                    department=department,
                )
                current_value = getattr(report, counter_field)
                if current_value > 0:
                    setattr(report, counter_field, current_value - 1)
                    report.save(update_fields=[counter_field])
                    logger.debug(
                        f"Decremented {event_type} for {employee.code} in {timeframe_key}"
                    )
            except StaffGrowthReport.DoesNotExist:
                pass


def _update_staff_growth_event(
    employee: Employee,
    event_type: str,
    old_event_date: date,
    new_event_date: date,
    event_id: int,
    old_branch: Branch,
    new_branch: Branch,
    old_block: Block,
    new_block: Block,
    old_department: Department,
    new_department: Department,
) -> None:
    """Handle event update - may need to move count between timeframes.
    
    Called when an EmployeeWorkHistory record is updated (date or org changed).
    """
    old_week_key, old_month_key = _get_timeframe_keys(old_event_date)
    new_week_key, new_month_key = _get_timeframe_keys(new_event_date)
    
    # Check if timeframe changed
    timeframe_changed = (
        old_week_key != new_week_key or 
        old_month_key != new_month_key or
        old_department_id != new_department_id
    )
    
    if timeframe_changed:
        # Remove from old timeframe (if was the only event there)
        _remove_staff_growth_event(
            employee, event_type, old_event_date, event_id,
            old_branch, old_block, old_department
        )
        # Add to new timeframe (with dedup check)
        _record_staff_growth_event(
            employee, event_type, new_event_date, event_id,
            new_branch, new_block, new_department
        )
```

### Signal Handler Integration

```python
# In apps/hrm/signals/hr_reports.py

@receiver(post_save, sender=EmployeeWorkHistory)
def handle_work_history_save(sender, instance, created, **kwargs):
    """Handle EmployeeWorkHistory create/update for staff growth reports."""
    event_type = _map_to_staff_growth_event_type(instance)
    if not event_type:
        return
    
    if created:
        # New event → record it
        _record_staff_growth_event(
            employee=instance.employee,
            event_type=event_type,
            event_date=instance.date,
            event_id=instance.id,
            branch=instance.branch,
            block=instance.block,
            department=instance.department,
        )
    else:
        # Update → check if relevant fields changed
        # Use django-dirtyfields or manual tracking
        _update_staff_growth_event(...)


@receiver(post_delete, sender=EmployeeWorkHistory)
def handle_work_history_delete(sender, instance, **kwargs):
    """Handle EmployeeWorkHistory deletion for staff growth reports."""
    event_type = _map_to_staff_growth_event_type(instance)
    if not event_type:
        return
    
    _remove_staff_growth_event(
        employee=instance.employee,
        event_type=event_type,
        event_date=instance.date,
        event_id=instance.id,  # Already deleted, but ID still available
        branch=instance.branch,
        block=instance.block,
        department=instance.department,
    )

---

## 🔧 API Changes

### Current API (BROKEN)
```python
@action(detail=False, methods=["get"], url_path="staff-growth")
def staff_growth(self, request):
    # Aggregate from daily records → SUM causes duplicates!
    aggregated = queryset.values(period_field).annotate(
        num_resignations=Sum("num_resignations"),
    )
```

### New API (Direct Query)

```python
@extend_schema(
    summary="Staff Growth Report",
    tags=["4.8: Recruitment Reports"],
    parameters=[StaffGrowthReportParametersSerializer],
    responses={200: StaffGrowthReportAggregatedSerializer(many=True)},
)
@action(detail=False, methods=["get"], url_path="staff-growth")
def staff_growth(self, request):
    """Get staff growth data by timeframe.
    
    Returns pre-calculated distinct employee counts.
    No aggregation needed - data is already correct.
    """
    serializer = StaffGrowthReportParametersSerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    
    from_date = serializer.validated_data["from_date"]
    to_date = serializer.validated_data["to_date"]
    period_type = serializer.validated_data.get("period_type", ReportPeriodType.MONTH.value)
    
    # Map period_type to timeframe_type
    if period_type == ReportPeriodType.WEEK.value:
        timeframe_type = StaffGrowthReport.TimeframeType.WEEK
    else:
        timeframe_type = StaffGrowthReport.TimeframeType.MONTH
    
    # Calculate timeframe keys for the date range
    timeframe_keys = self._get_timeframe_keys(from_date, to_date, timeframe_type)
    
    # Direct query - NO aggregation needed!
    queryset = StaffGrowthReport.objects.filter(
        timeframe_type=timeframe_type,
        timeframe_key__in=timeframe_keys,
    )
    
    # Apply data scope filters
    queryset = self._apply_data_scope_filter(queryset, request)
    
    # Group by timeframe_key (org structure filtering already applied)
    results = (
        queryset
        .values("timeframe_key")
        .annotate(
            # Sum across departments within same timeframe
            # This is correct because each employee is only counted ONCE per timeframe
            num_introductions=Sum("num_introductions"),
            num_returns=Sum("num_returns"),
            num_recruitment_source=Sum("num_recruitment_source"),
            num_transfers=Sum("num_transfers"),
            num_resignations=Sum("num_resignations"),
        )
        .order_by("timeframe_key")
    )
    
    # Build response
    response_data = []
    for item in results:
        if timeframe_type == StaffGrowthReport.TimeframeType.WEEK:
            label = item["timeframe_key"]  # "W01-2026"
        else:
            label = f"{_('Month')} {item['timeframe_key']}"  # "Month 01/2026"
        
        response_data.append({
            "period_type": period_type,
            "label": label,
            "num_introductions": item["num_introductions"] or 0,
            "num_returns": item["num_returns"] or 0,
            "num_recruitment_source": item["num_recruitment_source"] or 0,
            "num_transfers": item["num_transfers"] or 0,
            "num_resignations": item["num_resignations"] or 0,
        })
    
    serializer = StaffGrowthReportAggregatedSerializer(response_data, many=True)
    return Response(serializer.data)


def _get_timeframe_keys(
    self, from_date: date, to_date: date, timeframe_type: str
) -> list[str]:
    """Generate list of timeframe keys for date range."""
    keys = []
    current = from_date
    
    if timeframe_type == StaffGrowthReport.TimeframeType.WEEK:
        while current <= to_date:
            week_number = current.isocalendar()[1]
            year = current.isocalendar()[0]  # ISO year
            keys.append(f"W{week_number:02d}-{year}")
            current += timedelta(days=7)
    else:  # MONTH
        while current <= to_date:
            keys.append(current.strftime("%m/%Y"))
            # Move to next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1, day=1)
            else:
                current = current.replace(month=current.month + 1, day=1)
    
    return list(set(keys))  # Remove duplicates
```

---

## 📁 Files to Modify

| File | Change |
|------|--------|
| `apps/hrm/models/recruitment_reports.py` | Refactor `StaffGrowthReport` model (add `timeframe_type`, `timeframe_key`) |
| `apps/hrm/tasks/reports_hr/helpers.py` | Replace `_aggregate_staff_growth_for_date()` with new event tracking using `EmployeeWorkHistory` |
| `apps/hrm/signals/hr_reports.py` | Update signal handlers to use new event recording |
| `apps/hrm/api/views/recruitment_reports.py` | Update `staff_growth()` action - direct query |

---

## 🔄 Data Rebuild Strategy

### Approach: Manual Script (No Complex Migration)

Thay vì migration phức tạp, sử dụng script đơn giản để rebuild data:

1. **Truncate old data** - Xóa toàn bộ `StaffGrowthReport` cũ
2. **Run rebuild script** - Tính lại từ `EmployeeWorkHistory`
3. **Verify data** - Kiểm tra kết quả

### Script Location

**File:** `scripts/rebuild_staff_growth_reports.py`

```python
#!/usr/bin/env python
"""Rebuild StaffGrowthReport data with deduplication logic.

Usage:
    poetry run python scripts/rebuild_staff_growth_reports.py [--from-date YYYY-MM-DD] [--to-date YYYY-MM-DD]

Example:
    poetry run python scripts/rebuild_staff_growth_reports.py --from-date 2025-01-01 --to-date 2026-01-31
"""
import argparse
import os
import sys
from datetime import date

import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
django.setup()

from django.db import transaction
from django.db.models import Q

from apps.hrm.models import (
    Employee,
    EmployeeWorkHistory,
    StaffGrowthReport,
)


def get_timeframe_keys(event_date: date) -> tuple[str, str]:
    """Calculate week_key and month_key from date."""
    week_number = event_date.isocalendar()[1]
    year = event_date.isocalendar()[0]
    week_key = f"W{week_number:02d}-{year}"
    month_key = event_date.strftime("%m/%Y")
    return week_key, month_key


def get_timeframe_range(event_date: date, timeframe_type: str) -> tuple[date, date]:
    """Get start and end dates for a timeframe."""
    from datetime import timedelta
    
    if timeframe_type == "week":
        start = event_date - timedelta(days=event_date.weekday())
        end = start + timedelta(days=6)
    else:  # month
        start = event_date.replace(day=1)
        if event_date.month == 12:
            end = date(event_date.year, 12, 31)
        else:
            end = date(event_date.year, event_date.month + 1, 1) - timedelta(days=1)
    return start, end


def rebuild_reports(from_date: date, to_date: date, dry_run: bool = False):
    """Rebuild StaffGrowthReport from EmployeeWorkHistory."""
    print(f"Rebuilding StaffGrowthReport from {from_date} to {to_date}")
    
    if not dry_run:
        print("Clearing existing data...")
        StaffGrowthReport.objects.all().delete()
    
    # Query all relevant work history events
    events = EmployeeWorkHistory.objects.filter(
        date__range=(from_date, to_date),
    ).select_related("employee", "branch", "block", "department").order_by("date")
    
    print(f"Processing {events.count()} events...")
    
    # Event type mappings: (filter_kwargs, event_type, counter_field)
    event_mappings = [
        (
            {"name": EmployeeWorkHistory.EventType.CHANGE_STATUS, "status": Employee.Status.RESIGNED},
            "resignation",
            "num_resignations",
        ),
        (
            {"name": EmployeeWorkHistory.EventType.TRANSFER},
            "transfer",
            "num_transfers",
        ),
        # Add more event types as needed
    ]
    
    for filter_kwargs, event_type, counter_field in event_mappings:
        filtered_events = events.filter(**filter_kwargs)
        print(f"  Processing {filtered_events.count()} {event_type} events...")
        
        # Track employees already counted per timeframe
        counted_employees: dict[str, set] = {}  # {timeframe_key: set(employee_ids)}
        
        for event in filtered_events:
            week_key, month_key = get_timeframe_keys(event.date)
            
            timeframes = [
                ("week", week_key),
                ("month", month_key),
            ]
            
            for timeframe_type, timeframe_key in timeframes:
                # Create unique key for tracking
                tracking_key = f"{timeframe_type}:{timeframe_key}:{event.department_id}"
                
                if tracking_key not in counted_employees:
                    counted_employees[tracking_key] = set()
                
                # Check if employee already counted
                if event.employee_id in counted_employees[tracking_key]:
                    continue
                
                # Mark as counted
                counted_employees[tracking_key].add(event.employee_id)
                
                if dry_run:
                    print(f"    Would record: {event.employee.code} - {event_type} - {timeframe_key}")
                else:
                    # Get or create report and increment
                    report, _ = StaffGrowthReport.objects.get_or_create(
                        timeframe_type=timeframe_type,
                        timeframe_key=timeframe_key,
                        branch=event.branch,
                        block=event.block,
                        department=event.department,
                    )
                    setattr(report, counter_field, getattr(report, counter_field) + 1)
                    report.save(update_fields=[counter_field])
    
    print("Done!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rebuild StaffGrowthReport data")
    parser.add_argument("--from-date", type=str, default="2025-01-01")
    parser.add_argument("--to-date", type=str, default="2026-12-31")
    parser.add_argument("--dry-run", action="store_true", help="Preview without changes")
    
    args = parser.parse_args()
    
    from_date = date.fromisoformat(args.from_date)
    to_date = date.fromisoformat(args.to_date)
    
    with transaction.atomic():
        rebuild_reports(from_date, to_date, dry_run=args.dry_run)
```

### Execution Steps

```bash
# 1. After model changes, run migrations
poetry run python manage.py makemigrations hrm
poetry run python manage.py migrate

# 2. Preview rebuild (dry run)
poetry run python scripts/rebuild_staff_growth_reports.py --dry-run

# 3. Execute rebuild
poetry run python scripts/rebuild_staff_growth_reports.py --from-date 2025-01-01 --to-date 2026-12-31

# 4. Verify data
poetry run python manage.py shell -c "from apps.hrm.models import StaffGrowthReport; print(StaffGrowthReport.objects.count())"
```

---

## ✅ Test Cases

### Unit Tests

```python
@pytest.mark.django_db
class TestStaffGrowthReportDistinctCount:
    """Test that event counts are distinct per employee per timeframe."""

    def test_same_employee_multiple_resignations_counted_once(self):
        """Employee with 2 resignations in same month counted once."""
        employee = EmployeeFactory()
        department = DepartmentFactory()
        
        # Create 2 resignation events in same month via EmployeeWorkHistory
        EmployeeWorkHistoryFactory(
            employee=employee,
            department=department,
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.RESIGNED,
            date=date(2026, 1, 5),
        )
        EmployeeWorkHistoryFactory(
            employee=employee,
            department=department,
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.RESIGNED,
            date=date(2026, 1, 10),
        )
        
        # Trigger report rebuild or signal processing
        # ...
        
        # Check monthly report
        report = StaffGrowthReport.objects.get(
            timeframe_type="month",
            timeframe_key="01/2026",
            department=department,
        )
        assert report.num_resignations == 1  # Not 2!

    def test_different_employees_counted_separately(self):
        """Different employees counted separately."""
        emp1 = EmployeeFactory()
        emp2 = EmployeeFactory()
        department = DepartmentFactory()
        
        EmployeeWorkHistoryFactory(
            employee=emp1, department=department,
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.RESIGNED,
            date=date(2026, 1, 5),
        )
        EmployeeWorkHistoryFactory(
            employee=emp2, department=department,
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.RESIGNED,
            date=date(2026, 1, 10),
        )
        
        # Trigger rebuild...
        
        report = StaffGrowthReport.objects.get(
            timeframe_type="month",
            timeframe_key="01/2026",
            department=department,
        )
        assert report.num_resignations == 2

    def test_same_employee_different_months_counted_separately(self):
        """Same employee in different months counted in each month."""
        employee = EmployeeFactory()
        department = DepartmentFactory()
        
        EmployeeWorkHistoryFactory(
            employee=employee, department=department,
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.RESIGNED,
            date=date(2026, 1, 5),
        )
        EmployeeWorkHistoryFactory(
            employee=employee, department=department,
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.RESIGNED,
            date=date(2026, 2, 5),
        )
        
        jan_report = StaffGrowthReport.objects.get(
            timeframe_type="month", timeframe_key="01/2026", department=department
        )
        feb_report = StaffGrowthReport.objects.get(
            timeframe_type="month", timeframe_key="02/2026", department=department
        )
        
        assert jan_report.num_resignations == 1
        assert feb_report.num_resignations == 1

    def test_weekly_and_monthly_updated_together(self):
        """Both weekly and monthly reports updated for each event."""
        employee = EmployeeFactory()
        department = DepartmentFactory()
        
        EmployeeWorkHistoryFactory(
            employee=employee, department=department,
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            status=Employee.Status.RESIGNED,
            date=date(2026, 1, 5),
        )
        
        # Trigger rebuild...
        
        weekly = StaffGrowthReport.objects.filter(
            timeframe_type="week", department=department
        )
        monthly = StaffGrowthReport.objects.filter(
            timeframe_type="month", department=department
        )
        
        assert weekly.exists()
        assert monthly.exists()
```

### QA Test Table

| # | Test ID | Mô tả | Expected Result | Priority |
|---|---------|-------|-----------------|----------|
| 1 | TC-PR5-001 | NV nghỉ 2 lần cùng tháng | num_resignations = 1 | 🔴 Critical |
| 2 | TC-PR5-002 | 2 NV khác nhau nghỉ cùng tháng | num_resignations = 2 | 🔴 Critical |
| 3 | TC-PR5-003 | NV nghỉ 2 tháng khác nhau | Mỗi tháng đếm 1 | 🟠 High |
| 4 | TC-PR5-004 | Query theo week | Weekly data correct | 🟠 High |
| 5 | TC-PR5-005 | Query theo month | Monthly data correct | 🟠 High |
| 6 | TC-PR5-006 | NV cùng tuần khác tháng | Đếm đúng cho cả week và month | 🟡 Medium |

---

## 📊 Implementation Checklist

### Model Changes
- [ ] Add `TimeframeType` enum to `StaffGrowthReport`
- [ ] Add `timeframe_type` and `timeframe_key` fields
- [ ] Update unique constraint
- [ ] Create migration

### Task/Signal Changes
- [ ] Implement `_record_staff_growth_event()` helper (using `EmployeeWorkHistory` for dedup)
- [ ] Implement `_remove_staff_growth_event()` helper
- [ ] Update signal handlers to use new functions
- [ ] Remove/deprecate old daily aggregation logic

### API Changes
- [ ] Update `staff_growth()` action to direct query
- [ ] Add `_get_timeframe_keys()` helper
- [ ] Update serializers if needed

### Testing
- [ ] Add unit tests for deduplication logic
- [ ] Add integration tests for API
- [ ] Manual QA with test data (MV000000102)

### Validation
- [ ] Run: `ENVIRONMENT=test poetry run pytest apps/hrm/tests/ -v -k staff_growth`
- [ ] Pre-commit: `pre-commit run --all-files`
- [ ] Data migration verification

---

## 📝 Notes

1. **Same logic applies to all metrics:** `num_transfers`, `num_returns`, `num_introductions` - all need deduplication
2. **EmployeeWorkHistory as source of truth:** No separate event log needed - query existing data for deduplication
3. **Backward compatibility:** Keep old API response format, only internal logic changes
4. **Performance:** EmployeeWorkHistory query adds slight overhead, but avoids maintaining duplicate data

---

## 🔗 Related Files

- [86ew457ta-bc-tang-truong-ns-nghi-nhieu-lan.md](./86ew457ta-bc-tang-truong-ns-nghi-nhieu-lan.md)
