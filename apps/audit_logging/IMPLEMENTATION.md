# Audit Logging Implementation Summary

## Overview

This implementation refactors the audit logging system from Athena to OpenSearch, addressing all review comments from PR #3.

## Changes Made

### 1. Removed Athena Dependencies (Review Comment #1)

**Files Modified:**
- `.env.tpl`: Removed all Athena-related environment variables
- `settings/base/aws.py`: Removed Athena settings (AWS_ATHENA_DATABASE, AWS_ATHENA_TABLE, AWS_ATHENA_OUTPUT)

**What was removed:**
- AWS_ATHENA_DATABASE
- AWS_ATHENA_TABLE  
- AWS_ATHENA_OUTPUT
- Any references to Glue Crawler or Athena queries

### 2. Updated README for OpenSearch (Review Comment #2)

**File:** `apps/audit_logging/README.md`

**Changes:**
- Removed all mentions of Athena and Glue Crawler
- Added comprehensive OpenSearch setup instructions
- Added Docker setup for local development
- Added AWS OpenSearch Service setup instructions
- Updated architecture documentation to reflect: S3 for persistent storage, OpenSearch for serving/filtering
- Added API usage examples with curl commands

### 3. Removed StreamOffset Model (Review Comment #3)

**File:** `apps/audit_logging/models.py`

**Changes:**
- Model file now empty with just a comment: "No models needed - using RabbitMQ server-side offset tracking"
- The consumer uses RabbitMQ Stream's built-in server-side offset tracking via the `consumer_name` parameter
- No database migrations needed for offset tracking

**Technical Details:**
- RabbitMQ Stream supports server-side offset tracking when you provide a `consumer_name`
- The consumer calls: `await consumer.subscribe(..., consumer_name=consumer_name)`
- RabbitMQ automatically tracks and resumes from the last processed offset

### 4. Deleted snippets.py (Review Comment #4)

**File:** `apps/audit_logging/snippets.py`

**Status:** Not created (file doesn't exist in this implementation)

### 5. Replaced Celery Task with Django Management Command (Review Comment #5)

**Files:**
- `apps/audit_logging/tasks.py`: NOT CREATED (obsolete)
- `apps/audit_logging/management/commands/consume_audit_logs.py`: NEW

**Changes:**
- Removed Celery task approach entirely
- Created Django management command: `python manage.py consume_audit_logs`
- Added OpenSearch indexing logic directly in the command
- Consumer now:
  1. Reads messages from RabbitMQ Stream
  2. Indexes each log to OpenSearch immediately (real-time)
  3. Batches logs and uploads to S3 (archival)

**Command Usage:**
```bash
# Default settings
python manage.py consume_audit_logs

# Custom batch size
python manage.py consume_audit_logs --batch-size 500

# Custom consumer name (for multiple workers)
python manage.py consume_audit_logs --consumer-name worker-01
```

## New Implementation Details

### Architecture

```
Producer (producer.py)
    ↓
RabbitMQ Stream
    ↓
Consumer (Django management command)
    ├─→ OpenSearch (real-time indexing)
    └─→ S3 (batch archival in Parquet format)
    
API (views.py)
    ↓
OpenSearch (query/filter/search)
```

### Key Components

1. **Producer** (`producer.py`):
   - Logs events to RabbitMQ Stream
   - Async operation using `rstream` library
   - Auto-generates log_id and timestamp

2. **Consumer** (`management/commands/consume_audit_logs.py`):
   - Django management command
   - Reads from RabbitMQ Stream continuously
   - Indexes to OpenSearch immediately for real-time search
   - Batches logs for S3 upload
   - Uses RabbitMQ server-side offset tracking

3. **OpenSearch Client** (`opensearch_client.py`):
   - Singleton pattern for client instance
   - Automatic index creation with proper mappings
   - Monthly index rotation (audit-logs-YYYY-MM)
   - Search across all indices with wildcard pattern
   - Bulk indexing support

4. **S3 Uploader** (`s3_uploader.py`):
   - Uploads logs in Parquet format
   - Partitioned by: object_type, year, month, day
   - No Glue or Athena integration
   - Pure S3 storage for archival

5. **API** (`views.py`, `serializers.py`, `urls.py`):
   - REST endpoint: `/api/audit-logs/search/`
   - Filters: start_time, end_time, user_id, username, action, object_type, object_id
   - Free text search across object_repr and change_message
   - Pagination support
   - Authenticated access only

### Settings

**New Settings Files:**
- `settings/base/audit_logging.py`: Batch size and flush interval
- `settings/base/rabbitmq.py`: RabbitMQ Stream connection settings

**Updated Settings Files:**
- `settings/base/aws.py`: Added OpenSearch settings, removed Athena settings
- `settings/base/__init__.py`: Import new settings files
- `settings/base/apps.py`: Added audit_logging to INTERNAL_APPS
- `settings/base/sentry.py`: Fixed to not initialize in testing environment

### Dependencies Added

Added to `pyproject.toml`:
- `pyarrow = "^21.0.0"` - For Parquet file format
- `rstream = "^0.31.0"` - For RabbitMQ Stream protocol
- `opensearch-py = "^2.8.0"` - For OpenSearch client

### URL Routing

Added to `urls.py`:
```python
path("api/audit-logs/", include("apps.audit_logging.urls"))
```

### Tests

Created test files:
- `tests/test_opensearch_client.py`: Tests for OpenSearch client functionality
- `tests/test_api_views.py`: Tests for API endpoints

## Deployment

### Production Setup

1. **RabbitMQ Stream**: Enable stream plugin
2. **OpenSearch**: Deploy cluster (AWS or self-hosted)
3. **S3**: Create bucket with appropriate permissions
4. **Consumer**: Run as systemd service

Example systemd service:
```ini
[Unit]
Description=Audit Log Consumer
After=network.target

[Service]
Type=simple
User=backend
WorkingDirectory=/path/to/backend
Environment="ENVIRONMENT=production"
ExecStart=/path/to/venv/bin/python manage.py consume_audit_logs
Restart=always

[Install]
WantedBy=multi-user.target
```

## Benefits of New Approach

1. **Real-time Search**: OpenSearch provides instant querying (vs Athena's query delays)
2. **No Database Overhead**: RabbitMQ handles offset tracking
3. **Simpler Deployment**: Management command instead of Celery workers
4. **Better Separation**: S3 for archival, OpenSearch for search
5. **Scalable**: Can run multiple consumers with different names
6. **Cost Effective**: No Athena query costs

## Migration Path

For existing systems:
1. Deploy new code
2. Start consumer command
3. Producer will work immediately (no changes needed)
4. Old logs in S3 remain accessible for archival purposes
5. New logs flow to both S3 and OpenSearch

## Testing

To test the implementation:
1. Start RabbitMQ with stream plugin
2. Start OpenSearch
3. Configure .env with connection details
4. Run consumer: `python manage.py consume_audit_logs`
5. Log an event using producer
6. Query via API: `curl http://localhost:8000/api/audit-logs/search/`

## Future Enhancements

- [ ] Add bulk producer for high-volume scenarios
- [ ] Add log retention policies (delete old indices)
- [ ] Add Grafana dashboards for OpenSearch data
- [ ] Add alerting based on audit log patterns
- [ ] Add user organization fields when Org feature is ready
