# Known Issues - Report Aggregation System

## Issue: Deleted Records Cannot Be Tracked by Batch Tasks

### Problem Description

The current batch reconciliation system has a critical limitation: when a work history or recruitment candidate record is deleted, the batch task cannot detect which dates and organizational units need to be recalculated.

### Why This Happens

1. **Event Task Failure**: If an event-driven task fails or is delayed, the deletion is not reflected in reports
2. **Batch Task Blind Spot**: Batch tasks query existing records to find affected dates/org units
3. **Information Loss**: Once a record is deleted, there's no trace of which reports it contributed to

### Example Scenario

```
Day 1: Employee work history created for Branch A, Block B, Dept C, Date 2024-01-15
       - Event task updates StaffGrowthReport for that date/org unit
       
Day 2: Work history is deleted (but event task fails/delayed)
       - Deletion should decrement the report counters
       - But event task failed, so reports are now incorrect
       
Day 3: Batch task runs at midnight
       - Queries EmployeeWorkHistory.objects.filter(updated_at__date=Day3)
       - Finds no records (deleted record doesn't appear in query)
       - Cannot determine which report needs fixing
       - Reports remain incorrect permanently
```

### Impact

- Reports can become permanently incorrect if event tasks fail during deletions
- Batch reconciliation cannot fix these errors
- Data integrity depends entirely on event task reliability

### Potential Solutions

#### Option 1: Soft Deletes
- Never actually delete records, just mark as `deleted=True`
- Batch tasks can still query soft-deleted records
- **Pros**: Simple, maintains full history
- **Cons**: Database grows indefinitely, queries more complex

#### Option 2: Reconciliation Audit Table
- Create a separate table: `ReportReconciliationQueue`
- Whenever any report-affecting record changes, log: `(date, branch_id, block_id, department_id, report_type, needs_reconciliation=True)`
- Event tasks mark as `needs_reconciliation=False` when successful
- Batch tasks process all records where `needs_reconciliation=True`
- Delete reconciliation records after successful batch processing
- **Pros**: Comprehensive tracking, survives deletions, explicit queue
- **Cons**: Additional table, more write operations

#### Option 3: Event Sourcing / Change Data Capture
- Log all changes to a separate audit trail
- Batch tasks replay the audit trail to detect what needs recalculation
- **Pros**: Complete history, time-travel debugging
- **Cons**: Complex implementation, storage overhead

### Recommended Solution

**Option 2** (Reconciliation Audit Table) is recommended because:
- Explicitly tracks what needs recalculation
- Survives record deletions
- Can be cleaned up after successful processing
- Provides visibility into reconciliation queue status
- Minimal complexity compared to event sourcing

### Implementation Plan (For Future Discussion)

1. Create model: `ReportReconciliationQueue(date, branch_id, block_id, department_id, report_type, created_at, processed=False)`
2. Modify signals to always log to this table before triggering event tasks
3. Event tasks mark records as `processed=True` on success
4. Batch tasks query this table instead of modified records
5. Add cleanup job to delete old processed records (e.g., > 7 days old)

### Current Workaround

For now, the system assumes:
- Event tasks have high reliability (3 retries with exponential backoff)
- Deletions are rare compared to creates/updates
- Manual intervention available if reports become incorrect

**NOTE**: This issue should be addressed before production deployment for critical reporting.

---
Last Updated: 2025-11-09
Status: Documented, awaiting decision on solution approach
