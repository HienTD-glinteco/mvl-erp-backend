# HR and Recruitment Reports Aggregation

This document describes the Celery task-based architecture for aggregating HR and recruitment reporting data.

## Overview

The system implements automated report aggregation using two approaches:

1. **Event-driven tasks**: Triggered immediately when relevant model changes occur via Django signals
2. **Scheduled batch tasks**: Run at midnight to reconcile data and ensure consistency

This dual approach ensures:
- Real-time data updates for immediate reporting needs
- Data consistency through daily batch reconciliation
- Resilience against missed or failed event-driven updates

## Architecture

### HR Reports Aggregation

**Models Updated:**
- `StaffGrowthReport`: Monthly/weekly growth, resignations, transfers
- `EmployeeStatusBreakdownReport`: Daily employee status counts by organizational unit

**Trigger Source:**
- Model: `EmployeeWorkHistory`
- Signals: `post_save`, `post_delete`

**Tasks:**
- `aggregate_hr_reports_for_work_history(work_history_id)`: Event-driven task
- `aggregate_hr_reports_batch(target_date=None)`: Scheduled batch task (00:05 daily)

**Workflow:**

```
EmployeeWorkHistory.save() 
    → post_save signal
    → aggregate_hr_reports_for_work_history.delay(work_history_id)
    → Update StaffGrowthReport and EmployeeStatusBreakdownReport
```

```
Daily at 00:05
    → aggregate_hr_reports_batch.delay()
    → Re-aggregate all reports for previous day
    → Ensures data consistency
```

### Recruitment Reports Aggregation

**Models Updated:**
- `RecruitmentSourceReport`: Daily hires by recruitment source
- `RecruitmentChannelReport`: Daily hires by recruitment channel
- `RecruitmentCostReport`: Daily recruitment costs by source type
- `HiredCandidateReport`: Statistics of hired candidates by source type

**Trigger Source:**
- Model: `RecruitmentCandidate`
- Signals: `post_save`, `post_delete`

**Tasks:**
- `aggregate_recruitment_reports_for_candidate(candidate_id)`: Event-driven task
- `aggregate_recruitment_reports_batch(target_date=None)`: Scheduled batch task (00:10 daily)

**Workflow:**

```
RecruitmentCandidate.save() 
    → post_save signal
    → aggregate_recruitment_reports_for_candidate.delay(candidate_id)
    → Update all recruitment reports (only for HIRED status)
```

```
Daily at 00:10
    → aggregate_recruitment_reports_batch.delay()
    → Re-aggregate all reports for previous day
    → Ensures data consistency
```

## Implementation Details

### Event-Driven Tasks

**Location:**
- `apps/hrm/tasks/reports_hr.py`
- `apps/hrm/tasks/reports_recruitment.py`

**Features:**
- Bound tasks (`bind=True`) for retry support
- Maximum 3 retries with exponential backoff (60s, 120s, 240s)
- Graceful handling of deleted records
- Transactional updates to ensure consistency
- Detailed logging of all operations

**Example Usage:**

```python
from apps.hrm.tasks import aggregate_hr_reports_for_work_history

# Trigger manually
aggregate_hr_reports_for_work_history.delay(work_history_id=123)

# Or triggered automatically by signal when EmployeeWorkHistory is saved
```

### Batch Tasks

**Schedule:**
- HR reports: Daily at 00:05
- Recruitment reports: Daily at 00:10
- Configured in `settings/base/celery.py` using Celery Beat

**Features:**
- Defaults to aggregating previous day's data
- Can specify custom date via `target_date` parameter
- Processes all unique organizational units with activity
- Transactional batch updates
- Returns summary of processed units

**Example Usage:**

```python
from apps.hrm.tasks import aggregate_hr_reports_batch

# Run for yesterday (default)
aggregate_hr_reports_batch.delay()

# Run for specific date
aggregate_hr_reports_batch.delay(target_date="2025-11-05")
```

### Signal Handlers

**Location:** `apps/hrm/signals.py`

**Handlers:**

1. `trigger_hr_reports_aggregation_on_save`: Fires on `EmployeeWorkHistory.post_save`
2. `trigger_hr_reports_aggregation_on_delete`: Fires on `EmployeeWorkHistory.post_delete`
3. `trigger_recruitment_reports_aggregation_on_save`: Fires on `RecruitmentCandidate.post_save`
4. `trigger_recruitment_reports_aggregation_on_delete`: Fires on `RecruitmentCandidate.post_delete`

**Conditional Triggering:**
- Only triggers if required organizational fields are present (branch, block, department)
- Delete handlers trigger batch aggregation to re-process the entire day

## Data Aggregation Logic

### Staff Growth Report

Aggregates from `EmployeeWorkHistory`:
- `num_transfers`: Count of TRANSFER events
- `num_resignations`: Count of status changes to RESIGNED
- `num_returns`: Count of status changes from ONBOARDING/UNPAID_LEAVE to ACTIVE
- Includes `month_key` (MM/YYYY) and `week_key` (Week W - MM/YYYY) for grouping

### Employee Status Breakdown Report

Aggregates from `Employee`:
- Counts by status: ACTIVE, ONBOARDING, MATERNITY_LEAVE, UNPAID_LEAVE, RESIGNED
- `total_not_resigned`: Sum of all statuses except RESIGNED
- `count_resigned_reasons`: JSON breakdown of resignation reasons

### Recruitment Source Report

Aggregates from hired `RecruitmentCandidate`:
- `num_hires`: Count of hired candidates per recruitment source

### Recruitment Channel Report

Aggregates from hired `RecruitmentCandidate`:
- `num_hires`: Count of hired candidates per recruitment channel

### Recruitment Cost Report

Aggregates from hired `RecruitmentCandidate` and `RecruitmentExpense`:
- Groups candidates by source type (REFERRAL_SOURCE, MARKETING_CHANNEL, etc.)
- Calculates total cost from `RecruitmentExpense` distributed among hired candidates
- Computes average cost per hire

### Hired Candidate Report

Aggregates from hired `RecruitmentCandidate`:
- Groups by source type
- Counts total hired and experienced candidates
- Tracks referrer employee for REFERRAL_SOURCE type
- Includes `month_key` and `week_key` for grouping

## Source Type Classification

Candidates are classified into source types based on:

1. **REFERRAL_SOURCE**: `recruitment_source.allow_referral == True`
2. **MARKETING_CHANNEL**: `recruitment_channel.belong_to == "marketing"`
3. **JOB_WEBSITE_CHANNEL**: `recruitment_channel.belong_to == "job_website"`
4. **RECRUITMENT_DEPARTMENT_SOURCE**: Default for internal recruitment
5. **RETURNING_EMPLOYEE**: Former employees returning (requires additional logic/field)

## Testing

**Test Location:** `apps/hrm/tests/test_reports_aggregation.py`

**Coverage:**
- Event-driven task success cases
- Batch task success cases
- Deleted record handling
- Different event type counting
- Status breakdown aggregation
- Source/channel grouping
- Cost calculation
- Signal integration

**Run Tests:**

```bash
# Run all report aggregation tests
pytest apps/hrm/tests/test_reports_aggregation.py -v

# Run specific test class
pytest apps/hrm/tests/test_reports_aggregation.py::TestHRReportsAggregationTasks -v

# Run with coverage
pytest apps/hrm/tests/test_reports_aggregation.py --cov=apps.hrm.tasks
```

## Monitoring and Logging

All tasks include comprehensive logging:

- Task start/completion with execution details
- Affected records and aggregation summaries
- Warning logs for missing records
- Error logs with full exception details
- Retry attempts are logged

**Log Levels:**
- `INFO`: Normal operation, task completion
- `DEBUG`: Detailed aggregation counts and intermediate results
- `WARNING`: Missing records, skipped operations
- `ERROR`: Failures, exceptions
- `EXCEPTION`: Full stack traces for unexpected errors

**Example Log Output:**

```
INFO: Aggregating HR reports for work history 123 (employee: EMP001, date: 2025-11-06)
DEBUG: Aggregated staff growth for 2025-11-06 - Branch1/Block1/Dept1: transfers=2, resignations=1, returns=0
DEBUG: Aggregated employee status for 2025-11-06 - Branch1/Block1/Dept1: active=10, resigned=2, total_not_resigned=15
INFO: Successfully aggregated HR reports for work history 123
```

## Error Handling

### Retry Strategy

- Maximum retries: 3
- Retry delay: 60 seconds with exponential backoff
- Retries on all exceptions except `MaxRetriesExceededError`

### Transactional Safety

All aggregation operations are wrapped in `transaction.atomic()` to ensure:
- All-or-nothing updates
- Data consistency on failures
- Automatic rollback on errors

### Graceful Degradation

- Handles deleted records by skipping aggregation
- Validates required fields before processing
- Returns success/failure status in task result

## Performance Considerations

### Event-Driven Tasks

- Triggered individually for each model change
- Lightweight: Only processes single date and org unit
- Asynchronous execution prevents blocking user requests

### Batch Tasks

- Processes all organizational units with activity
- Uses Django ORM efficiently with select_related and iterator
- Bulk operations minimize database queries
- Scheduled during low-traffic hours (midnight)

### Optimization Tips

1. **Database Indexes**: Ensure indexes on:
   - `EmployeeWorkHistory.date`
   - `RecruitmentCandidate.onboard_date`
   - Organizational unit foreign keys

2. **Query Optimization**: Tasks use:
   - `select_related()` for ForeignKey lookups
   - `values()` with `distinct()` for org unit discovery
   - Aggregate functions for counting

3. **Celery Configuration**:
   - Use Redis for broker (fast in-memory queue)
   - Configure appropriate concurrency for workers
   - Monitor task queue depth

## Troubleshooting

### Tasks Not Triggering

**Check:**
1. Signals are connected (verify in Django shell)
2. Celery worker is running
3. Redis/broker is accessible
4. Required fields (branch, block, department) are set

```bash
# Check Celery worker status
celery -A celery_tasks inspect active

# Check scheduled tasks
celery -A celery_tasks inspect scheduled
```

### Missing or Incorrect Data

**Check:**
1. Review task logs for errors
2. Verify source data in `EmployeeWorkHistory` or `RecruitmentCandidate`
3. Run batch task manually for specific date
4. Check database transactions didn't rollback

```python
# Manual batch run for specific date
from apps.hrm.tasks import aggregate_hr_reports_batch
result = aggregate_hr_reports_batch("2025-11-06")
print(result)
```

### Performance Issues

**Check:**
1. Database query performance (use Django Debug Toolbar)
2. Celery worker concurrency settings
3. Task queue backlog
4. Database indexes

```bash
# Monitor task queue
celery -A celery_tasks inspect active_queues
```

## Future Enhancements

Potential improvements:

1. **Incremental Updates**: Track last aggregation timestamp to avoid re-processing
2. **Parallel Processing**: Use Celery groups for parallel org unit processing
3. **Caching**: Cache frequently accessed organizational structures
4. **Notifications**: Alert on aggregation failures
5. **Metrics**: Expose task metrics to monitoring systems (Prometheus, Datadog)
6. **Archive Old Data**: Implement data retention policy for old reports

## References

- Celery Documentation: https://docs.celeryproject.org/
- Django Signals: https://docs.djangoproject.com/en/stable/topics/signals/
- Project Settings: `settings/base/celery.py`
- Task Implementations: `apps/hrm/tasks/`
- Signal Handlers: `apps/hrm/signals.py`
- Tests: `apps/hrm/tests/test_reports_aggregation.py`
