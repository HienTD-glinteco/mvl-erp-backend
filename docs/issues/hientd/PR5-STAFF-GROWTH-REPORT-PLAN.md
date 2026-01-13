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

### New Tracking Model for Deduplication

```python
class StaffGrowthEventLog(models.Model):
    """Track which employees have been counted in each timeframe.
    
    Used for deduplication - ensures each employee is counted only once
    per event type per timeframe.
    """
    
    class EventType(models.TextChoices):
        INTRODUCTION = "introduction", "Introduction"
        RETURN = "return", "Return"
        RECRUITMENT_SOURCE = "recruitment_source", "Recruitment Source"
        TRANSFER = "transfer", "Transfer"
        RESIGNATION = "resignation", "Resignation"
    
    report = models.ForeignKey(
        StaffGrowthReport,
        on_delete=models.CASCADE,
        related_name="event_logs",
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="staff_growth_events",
    )
    event_type = models.CharField(
        max_length=20,
        choices=EventType.choices,
    )
    event_date = models.DateField(
        help_text="Original date of the event",
    )

    class Meta:
        unique_together = [["report", "employee", "event_type"]]
        # Ensures each employee can only be counted ONCE per event type per report
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
        → Check: Employee already logged for this event type?
            → YES: Skip (no increment)
            → NO: 
                → Add to StaffGrowthEventLog
                → Increment counter in StaffGrowthReport
```

### Implementation

**File:** `apps/hrm/tasks/reports_hr/helpers.py`

```python
def _record_staff_growth_event(
    employee: Employee,
    event_type: str,  # "resignation", "transfer", "return", etc.
    event_date: date,
    branch: Branch,
    block: Block,
    department: Department,
) -> None:
    """Record a staff growth event with deduplication.
    
    Updates BOTH weekly and monthly reports. Ensures each employee
    is counted only once per event type per timeframe.
    """
    from apps.hrm.models import StaffGrowthReport, StaffGrowthEventLog
    
    # Calculate timeframe keys
    week_number = event_date.isocalendar()[1]
    year = event_date.year
    week_key = f"W{week_number:02d}-{year}"  # e.g., "W01-2026"
    month_key = event_date.strftime("%m/%Y")  # e.g., "01/2026"
    
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
        # Get or create the report
        report, created = StaffGrowthReport.objects.get_or_create(
            timeframe_type=timeframe_type,
            timeframe_key=timeframe_key,
            branch=branch,
            block=block,
            department=department,
        )
        
        # Check if employee already logged for this event type
        event_log, log_created = StaffGrowthEventLog.objects.get_or_create(
            report=report,
            employee=employee,
            event_type=event_type,
            defaults={"event_date": event_date},
        )
        
        if log_created:
            # First time counting this employee → increment counter
            setattr(report, counter_field, getattr(report, counter_field) + 1)
            report.save(update_fields=[counter_field])
            logger.debug(
                f"Recorded {event_type} for {employee.code} in {timeframe_key}"
            )
        else:
            # Employee already counted in this timeframe → skip
            logger.debug(
                f"Skipped duplicate {event_type} for {employee.code} in {timeframe_key}"
            )
```

### Decrement Logic (When Event is Reverted)

```python
def _remove_staff_growth_event(
    employee: Employee,
    event_type: str,
    event_date: date,
    branch: Branch,
    block: Block,
    department: Department,
) -> None:
    """Remove a staff growth event (when reverted/cancelled).
    
    Decrements counter if this was the only event of this type for the employee.
    """
    # ... similar logic but:
    # 1. Delete the StaffGrowthEventLog entry
    # 2. Check if any other events for same employee+type exist in timeframe
    # 3. If no more events → decrement counter
```

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
| `apps/hrm/models/recruitment_reports.py` | Refactor `StaffGrowthReport` model + add `StaffGrowthEventLog` |
| `apps/hrm/tasks/reports_hr/helpers.py` | Replace `_aggregate_staff_growth_for_date()` with new event tracking |
| `apps/hrm/signals/hr_reports.py` | Update signal handlers to use new event recording |
| `apps/hrm/api/views/recruitment_reports.py` | Update `staff_growth()` action - direct query |
| `apps/hrm/admin.py` | Register new `StaffGrowthEventLog` model (if needed) |

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
    StaffGrowthEventLog,
    StaffGrowthReport,
)


def get_timeframe_keys(event_date: date) -> tuple[str, str]:
    """Calculate week_key and month_key from date."""
    week_number = event_date.isocalendar()[1]
    year = event_date.isocalendar()[0]
    week_key = f"W{week_number:02d}-{year}"
    month_key = event_date.strftime("%m/%Y")
    return week_key, month_key


def rebuild_reports(from_date: date, to_date: date, dry_run: bool = False):
    """Rebuild StaffGrowthReport from EmployeeWorkHistory."""
    print(f"Rebuilding StaffGrowthReport from {from_date} to {to_date}")
    
    if not dry_run:
        # Clear existing data in date range
        print("Clearing existing data...")
        StaffGrowthReport.objects.all().delete()
        StaffGrowthEventLog.objects.all().delete()
    
    # Query all relevant work history events
    events = EmployeeWorkHistory.objects.filter(
        date__range=(from_date, to_date),
    ).select_related("employee", "branch", "block", "department")
    
    print(f"Processing {events.count()} events...")
    
    # Process each event type
    event_mappings = [
        # (filter_kwargs, event_type)
        ({"name": EmployeeWorkHistory.EventType.TRANSFER}, "transfer"),
        (
            {
                "name": EmployeeWorkHistory.EventType.CHANGE_STATUS,
                "status": Employee.Status.RESIGNED,
            },
            "resignation",
        ),
        # Add more event types as needed
    ]
    
    for filter_kwargs, event_type in event_mappings:
        filtered_events = events.filter(**filter_kwargs)
        print(f"  Processing {filtered_events.count()} {event_type} events...")
        
        for event in filtered_events:
            if dry_run:
                print(f"    Would record: {event.employee.code} - {event_type} - {event.date}")
            else:
                _record_staff_growth_event(
                    employee=event.employee,
                    event_type=event_type,
                    event_date=event.date,
                    branch=event.branch,
                    block=event.block,
                    department=event.department,
                )
    
    print("Done!")


def _record_staff_growth_event(employee, event_type, event_date, branch, block, department):
    """Record event with deduplication (same logic as helpers.py)."""
    week_key, month_key = get_timeframe_keys(event_date)
    
    counter_field_map = {
        "resignation": "num_resignations",
        "transfer": "num_transfers",
        "return": "num_returns",
        "introduction": "num_introductions",
        "recruitment_source": "num_recruitment_source",
    }
    counter_field = counter_field_map[event_type]
    
    timeframes = [
        (StaffGrowthReport.TimeframeType.WEEK, week_key),
        (StaffGrowthReport.TimeframeType.MONTH, month_key),
    ]
    
    for timeframe_type, timeframe_key in timeframes:
        report, _ = StaffGrowthReport.objects.get_or_create(
            timeframe_type=timeframe_type,
            timeframe_key=timeframe_key,
            branch=branch,
            block=block,
            department=department,
        )
        
        _, log_created = StaffGrowthEventLog.objects.get_or_create(
            report=report,
            employee=employee,
            event_type=event_type,
            defaults={"event_date": event_date},
        )
        
        if log_created:
            setattr(report, counter_field, getattr(report, counter_field) + 1)
            report.save(update_fields=[counter_field])


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

    def test_same_employee_multiple_resignations_counted_once(self, db):
        """Employee with 2 resignations in same month counted once."""
        employee = EmployeeFactory()
        
        # Simulate 2 resignation events in same month
        _record_staff_growth_event(
            employee, "resignation", date(2026, 1, 5),
            branch, block, department
        )
        _record_staff_growth_event(
            employee, "resignation", date(2026, 1, 10),
            branch, block, department
        )
        
        # Check monthly report
        report = StaffGrowthReport.objects.get(
            timeframe_type="month",
            timeframe_key="01/2026",
        )
        assert report.num_resignations == 1  # Not 2!

    def test_different_employees_counted_separately(self, db):
        """Different employees counted separately."""
        emp1 = EmployeeFactory()
        emp2 = EmployeeFactory()
        
        _record_staff_growth_event(emp1, "resignation", date(2026, 1, 5), ...)
        _record_staff_growth_event(emp2, "resignation", date(2026, 1, 10), ...)
        
        report = StaffGrowthReport.objects.get(
            timeframe_type="month",
            timeframe_key="01/2026",
        )
        assert report.num_resignations == 2

    def test_same_employee_different_months_counted_separately(self, db):
        """Same employee in different months counted in each month."""
        employee = EmployeeFactory()
        
        _record_staff_growth_event(employee, "resignation", date(2026, 1, 5), ...)
        _record_staff_growth_event(employee, "resignation", date(2026, 2, 5), ...)
        
        jan_report = StaffGrowthReport.objects.get(timeframe_key="01/2026")
        feb_report = StaffGrowthReport.objects.get(timeframe_key="02/2026")
        
        assert jan_report.num_resignations == 1
        assert feb_report.num_resignations == 1

    def test_weekly_and_monthly_updated_together(self, db):
        """Both weekly and monthly reports updated for each event."""
        employee = EmployeeFactory()
        
        _record_staff_growth_event(employee, "resignation", date(2026, 1, 5), ...)
        
        weekly = StaffGrowthReport.objects.filter(timeframe_type="week")
        monthly = StaffGrowthReport.objects.filter(timeframe_type="month")
        
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
- [ ] Create `StaffGrowthEventLog` model
- [ ] Update unique constraint
- [ ] Create migration

### Task/Signal Changes
- [ ] Implement `_record_staff_growth_event()` helper
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
2. **StaffGrowthEventLog can grow large:** Consider periodic cleanup of old records (e.g., > 2 years)
3. **Backward compatibility:** Keep old API response format, only internal logic changes
4. **Performance:** Event logging adds slight overhead, but prevents costly recalculation

---

## 🔗 Related Files

- [86ew457ta-bc-tang-truong-ns-nghi-nhieu-lan.md](./86ew457ta-bc-tang-truong-ns-nghi-nhieu-lan.md)
